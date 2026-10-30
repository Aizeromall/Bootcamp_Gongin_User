# 2026-10-26
# 작업자 : 양태건

"""게시글 수정 모델과 수정 router."""
import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path

from .insert import InsertBoardRequest

from ..database import connect
from ..team_match.lineup import unpack

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 실제 DB board_a_write 사용: comment_seq=0은 게시글, 양수는 댓글입니다.
# 모든 댓글 식별·변경은 게시글 번호와 댓글 번호의 복합 PK를 사용합니다.
router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 게시글 전체 수정은 작성과 동일한 길이·공백 검증을 적용합니다.
# 제목·내용·종목·게시판 분류는 필수이며 지정된 카테고리만 허용합니다.
class UpdateBoardRequest(InsertBoardRequest):
    """제목·내용·카테고리를 수정하고 작성일·조회 수·댓글 연결은 보존합니다."""


# 작성자만 수정할 수 있으며 검증 후 하나의 트랜잭션으로 저장합니다.
@router.put("/update/{bulletin_seq}", summary="본인 게시글 수정")
def update_board(payload: UpdateBoardRequest, bulletin_seq: int = Path(gt=0)):
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
            # 게시글 존재 확인 및 쓰기 충돌 방지를 위한 행 잠금입니다.
            cursor.execute('SELECT bulletin_seq, c_id_seq, board_content FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = 0 FOR UPDATE', (bulletin_seq,))
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
            if row["c_id_seq"] != payload.c_id_seq:
                raise HTTPException(status_code=403, detail="본인 게시글만 수정할 수 있습니다.")
            if unpack(row.get('board_content')):
                raise HTTPException(409, '출전 예약이 연결된 매칭 글은 일반 게시글 수정으로 변경할 수 없습니다.')
            cursor.execute(
                """UPDATE board_a_write SET event_category = %s, board_category = %s,
                   board_title = %s, board_content = %s WHERE bulletin_seq = %s AND comment_seq = 0""",
                (payload.event_category, payload.board_category, payload.board_title,
                 payload.board_content, bulletin_seq),
            )
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
    # 내용이 기존 값과 같아 rowcount가 0이어도 정상 수정으로 처리합니다.
    return {"result": "OK", "bulletin_seq": bulletin_seq}


# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
