# 2026-10-26
# 작업자 : 양태건

"""게시글 작성 모델과 작성 router."""
from typing import Literal

import logging

import pymysql
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field


from ..database import connect

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 실제 DB board_a_write 사용: comment_seq=0은 게시글, 양수는 댓글입니다.
# 모든 댓글 식별·변경은 게시글 번호와 댓글 번호의 복합 PK를 사용합니다.
router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 작성·수정·목록 필터에서 동일한 종목과 게시판 카테고리를 사용합니다.
EventCategory = Literal["축구", "배구", "야구", "농구"]
BoardCategory = Literal["팀원모집", "매칭신청", "후기", "자유"]

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 이 파일의 요청에서 사용하는 작성자 ID와 공백 검증 모델입니다.
class BoardTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    c_id_seq: str = Field(min_length=1, max_length=50, description="작성 회원의 종목별 ID")

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 게시글 작성에 필요한 값입니다. 조회 수와 작성일은 클라이언트가 지정하지 않습니다.
class InsertBoardRequest(BoardTextRequest):
    event_category: EventCategory = Field(description="축구 / 배구 / 야구 / 농구")
    board_category: BoardCategory = Field(description="팀원모집 / 매칭신청 / 후기 / 자유")
    board_title: str = Field(min_length=1, max_length=200)
    board_content: str = Field(min_length=1, max_length=10000)


# 3. 게시글 작성: 회원 확인 후 작성일은 NOW(), 조회 수는 0으로 저장합니다.
@router.post("/insert", status_code=status.HTTP_201_CREATED, summary="게시글 작성")
def insert_board(payload: InsertBoardRequest):
    if '[출전예약:' in payload.board_content or '[출전정보:' in payload.board_content:
        raise HTTPException(status_code=422, detail='게시글에 사용할 수 없는 문구입니다.')
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 작성 회원이 실제로 존재하는지 확인합니다.
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (payload.c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
            cursor.execute(
                """INSERT INTO board_a_write
                   (c_id_seq, event_category, board_category, board_title, board_content, board_date, board_views, comment_seq)
                   VALUES (%s, %s, %s, %s, %s, NOW(), 0, 0)""",
                (payload.c_id_seq, payload.event_category, payload.board_category,
                 payload.board_title, payload.board_content),
            )
            bulletin_seq = cursor.lastrowid
        connection.commit()
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("게시판 참조 관계 충돌")
        raise HTTPException(status_code=409, detail="연결된 게시글 또는 댓글 정보를 확인해 주세요.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("게시판 처리 실패")
        raise HTTPException(status_code=500, detail="게시판 처리 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()
    return {"result": "OK", "bulletin_seq": bulletin_seq}

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
