# 2026-10-26
# 작업자 : 양태건

"""댓글 요청 모델과 댓글·대댓글의 조회·작성·수정·삭제를 담당합니다."""

from typing import Optional

import logging

import pymysql
from fastapi import APIRouter, Body, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field


from ..database import connect
from ..team_match.team_match_connect import BOARD_CATEGORY_TEAM_MATCH, POST_RESERVATION_PATTERN
from ..team_match.lineup import unpack, visible

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 실제 DB board_a_write 사용: comment_seq=0은 게시글, 양수는 댓글입니다.
# 모든 댓글 식별·변경은 게시글 번호와 댓글 번호의 복합 PK를 사용합니다.
router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 이 파일의 요청에서 사용하는 작성자 ID와 공백 검증 모델입니다.
class BoardTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    c_id_seq: str = Field(min_length=1, max_length=50, description="작성 회원의 종목별 ID")

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 댓글 전용 모델과 깊이 계산을 별도 router로 분리하며 기존 경로를 유지합니다.
# 부모 댓글을 생략하면 일반 댓글, 지정하면 부모 depth + 1인 대댓글을 생성합니다.
class InsertCommentRequest(BoardTextRequest):
    comment_content: str = Field(min_length=1, max_length=5000)
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 최초 댓글은 생략 또는 null, 대댓글만 실제 부모 comment_seq를 전달합니다.
    reply_to_comment_seq: Optional[int] = Field(
        default=None, gt=0,
        description="일반 댓글: 생략 또는 null / 대댓글: 같은 게시글의 실제 부모 댓글 번호",
    )



# 5. 댓글 정렬: 재귀 호출 없이 부모 다음에 자식이 오는 순서로 펼칩니다.
# depth가 커져도 호출 스택을 사용하지 않으며, 삭제 댓글은 원문을 노출하지 않습니다.
def order_comments(rows: list[dict] | tuple[dict, ...]) -> list[dict]:
    # 수정 일 : 2026-10-28 / 작업자 : 양태건
    # PyMySQL의 빈 조회 결과(튜플)도 리스트로 통일하여 댓글 없는 글의 500 오류를 방지합니다.
    rows = list(rows)
    children = {}
    ids = {row["comment_seq"] for row in rows}
    roots = []
    for row in rows:
        row["comment_delete_state"] = bool(row["comment_delete_state"])
        if row["comment_delete_state"]:
            row["comment_content"] = "삭제된 댓글입니다."
        parent = row["reply_to_comment_seq"]
        if parent is None or parent not in ids:
            roots.append(row)
        else:
            children.setdefault(parent, []).append(row)
    ordered = []
    seen = set()
    # 잘못된 순환 참조 데이터도 중복 없이 한 번만 표시하도록 남은 행을 확인합니다.
    for start in roots + rows:
        stack = [start]
        while stack:
            row = stack.pop()
            if row["comment_seq"] in seen:
                continue
            seen.add(row["comment_seq"])
            ordered.append(row)
            stack.extend(reversed(children.get(row["comment_seq"], [])))
    return ordered


# 6. 댓글 조회: 일반 댓글부터 모든 깊이의 대댓글을 조회합니다.
@router.get("/comment/select/{bulletin_seq}", summary="댓글·대댓글 조회")
def select_comments(bulletin_seq: int = Path(gt=0)):
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 게시글 존재 확인입니다.
            cursor.execute('SELECT bulletin_seq, c_id_seq FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = 0', (bulletin_seq,))
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
            cursor.execute(
                """SELECT q.comment_seq, q.bulletin_seq, q.c_id_seq, c.c_name,
                          q.reply_to_comment_seq, q.depth, q.comment_content, q.comment_delete_state
                   FROM board_a_write q
                   LEFT JOIN customer c ON c.c_id_seq = q.c_id_seq
                   WHERE q.bulletin_seq = %s AND q.comment_seq > 0 ORDER BY q.comment_seq ASC""", (bulletin_seq,),
            )
            rows = order_comments(cursor.fetchall())
    except HTTPException:
        raise
    except pymysql.IntegrityError:
        logger.exception("게시판 참조 관계 충돌")
        raise HTTPException(status_code=409, detail="연결된 게시글 또는 댓글 정보를 확인해 주세요.")
    except Exception:
        logger.exception("게시판 처리 실패")
        raise HTTPException(status_code=500, detail="게시판 처리 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()
    for row in rows:
        row['comment_content'] = visible(row.get('comment_content'))
    return {"total": len(rows), "results": rows}


# 7. 댓글·대댓글 작성: 부모가 같은 게시글에 있는지 확인하고 depth를 서버에서 계산합니다.
# 삭제된 부모 댓글에도 답변할 수 있으므로 기존 대화 연결은 계속 유지됩니다.
@router.post("/comment/insert/{bulletin_seq}", status_code=status.HTTP_201_CREATED, summary="댓글·대댓글 작성")
# 수정 일 : 2026-10-26 / 작업자 : 양태건
# Swagger의 기본 예시는 부모가 필요 없는 일반 댓글이며, 대댓글 예시는 따로 선택합니다.
def insert_comment(
    payload: InsertCommentRequest = Body(openapi_examples={
        "comment": {
            "summary": "일반 댓글 (부모 댓글 없이 최초 작성)",
            "value": {"c_id_seq": "member_01", "comment_content": "첫 댓글입니다."},
        },
        "reply": {
            "summary": "대댓글 (작성 결과의 comment_seq를 부모 번호로 입력)",
            "value": {"c_id_seq": "member_01", "comment_content": "댓글에 대한 답변입니다.",
                      "reply_to_comment_seq": 1},
        },
    }),
    bulletin_seq: int = Path(gt=0),
):
    if '[출전예약:' in payload.comment_content or '[출전정보:' in payload.comment_content:
        raise HTTPException(status_code=422, detail='댓글에 사용할 수 없는 문구입니다.')
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 게시글을 먼저 잠가 게시글 삭제와 댓글 작성의 실행 순서를 맞춥니다.
            # 게시글 존재 확인 및 쓰기 충돌 방지를 위한 행 잠금입니다.
            cursor.execute('SELECT bulletin_seq, c_id_seq, board_category, board_content FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = 0 FOR UPDATE', (bulletin_seq,))
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
            # 작성 회원이 실제로 존재하는지 확인합니다.
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (payload.c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
            # 수정 일 : 2026-10-26 / 작업자 : 양태건
            # 팀 매칭 API와 같은 예약번호 표시와 r_check를 사용하여 성사 여부를 판단합니다.
            # 게시글·예약을 잠근 상태로 검사해 수락 처리와 댓글 등록의 충돌을 방지합니다.
            if row.get("board_category") == BOARD_CATEGORY_TEAM_MATCH:
                reservation_mark = POST_RESERVATION_PATTERN.match(row.get("board_content") or "")
                if reservation_mark:
                    cursor.execute(
                        "SELECT r_check FROM reservation WHERE r_seq = %s FOR UPDATE",
                        (int(reservation_mark.group(1)),),
                    )
                    reservation = cursor.fetchone()
                    if reservation is None:
                        raise HTTPException(status_code=409, detail="연결된 구장대여 예약을 확인해 주세요.")
                    if bool(reservation["r_check"]):
                        raise HTTPException(status_code=409, detail="매칭이 성사된 게시글에는 댓글을 작성할 수 없습니다.")
            depth = 0
            if payload.reply_to_comment_seq is not None:
                cursor.execute(
                    """SELECT comment_seq, bulletin_seq, depth FROM board_a_write
                       WHERE bulletin_seq = %s AND comment_seq = %s AND comment_seq > 0 FOR UPDATE""",
                    (bulletin_seq, payload.reply_to_comment_seq),
                )
                parent = cursor.fetchone()
                if parent is None:
                    raise HTTPException(status_code=404, detail="부모 댓글이 존재하지 않습니다.")
                if parent["bulletin_seq"] != bulletin_seq:
                    raise HTTPException(status_code=409, detail="같은 게시글의 댓글에만 답변할 수 있습니다.")
                if not 0 <= parent["depth"] < 2147483647:
                    raise HTTPException(status_code=409, detail="댓글 깊이 정보를 확인해 주세요.")
                depth = parent["depth"] + 1
            # 수정 일 : 2026-10-26 / 작업자 : 양태건
            # 게시글(댓글번호 0) 잠금 아래 해당 게시글의 다음 댓글번호를 계산합니다.
            # 복합 PK이므로 다른 게시글의 댓글번호와 같아도 정상입니다.
            cursor.execute(
                "SELECT COALESCE(MAX(comment_seq), 0) + 1 AS next_seq FROM board_a_write WHERE bulletin_seq = %s",
                (bulletin_seq,),
            )
            comment_seq = cursor.fetchone()["next_seq"]
            if not 0 < comment_seq <= 2147483647:
                raise HTTPException(status_code=409, detail="댓글 번호 범위를 확인해 주세요.")
            cursor.execute(
                """INSERT INTO board_a_write
                   (bulletin_seq, comment_seq, c_id_seq, reply_to_comment_seq, depth, comment_content, comment_delete_state)
                   VALUES (%s, %s, %s, %s, %s, %s, 0)""",
                (bulletin_seq, comment_seq, payload.c_id_seq, payload.reply_to_comment_seq, depth, payload.comment_content),
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
    return {"result": "OK", "bulletin_seq": bulletin_seq, "comment_seq": comment_seq,
            "reply_to_comment_seq": payload.reply_to_comment_seq, "depth": depth}

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 댓글 수정에는 내용과 작성자만 받고 부모 번호·깊이·삭제 상태 변경은 허용하지 않습니다.
class UpdateCommentRequest(BoardTextRequest):
    comment_content: str = Field(min_length=1, max_length=5000)


@router.put("/comment/update/{comment_seq}", summary="본인 댓글 수정")
def update_comment(
    payload: UpdateCommentRequest,
    comment_seq: int = Path(gt=0),
    bulletin_seq: int = Query(gt=0, description="댓글이 속한 게시글 번호 (복합 PK)"),
):
    if '[출전예약:' in payload.comment_content or '[출전정보:' in payload.comment_content:
        raise HTTPException(status_code=422, detail='댓글에 사용할 수 없는 문구입니다.')
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
                "SELECT comment_seq, c_id_seq, comment_delete_state, comment_content FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = %s AND comment_seq > 0 FOR UPDATE",
                (bulletin_seq, comment_seq),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 댓글입니다.")
            if row["c_id_seq"] != payload.c_id_seq:
                raise HTTPException(status_code=403, detail="본인 댓글만 수정할 수 있습니다.")
            if unpack(row.get('comment_content')):
                raise HTTPException(status_code=409, detail='출전 예약이 연결된 신청은 수정할 수 없습니다.')
            if row["comment_delete_state"]:
                raise HTTPException(status_code=409, detail="삭제된 댓글은 수정할 수 없습니다.")
            cursor.execute(
                "UPDATE board_a_write SET comment_content = %s WHERE bulletin_seq = %s AND comment_seq = %s AND comment_seq > 0",
                (payload.comment_content, bulletin_seq, comment_seq),
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
    return {"result": "OK", "bulletin_seq": bulletin_seq, "comment_seq": comment_seq}


# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 댓글 삭제 기능을 delete.py에서 옮겨 댓글 관련 처리를 이 파일에 모읍니다.
# 8. 댓글 삭제: 작성자만 삭제 표시할 수 있으며 자식 댓글과 부모 번호는 보존합니다.
@router.delete("/comment/delete/{comment_seq}", summary="본인 댓글 삭제")
def delete_comment(
    comment_seq: int = Path(gt=0),
    bulletin_seq: int = Query(gt=0, description="댓글이 속한 게시글 번호 (복합 PK)"),
    c_id_seq: str = Query(min_length=1, max_length=50),
):
    c_id_seq = c_id_seq.strip()
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 작성 회원이 실제로 존재하는지 확인합니다.
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
            cursor.execute(
                "SELECT comment_seq, c_id_seq, comment_delete_state, comment_content FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = %s AND comment_seq > 0 FOR UPDATE",
                (bulletin_seq, comment_seq),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 댓글입니다.")
            if row["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 댓글만 삭제할 수 있습니다.")
            if unpack(row.get('comment_content')):
                raise HTTPException(status_code=409, detail='출전 예약이 연결된 신청은 삭제할 수 없습니다.')
            if row["comment_delete_state"]:
                raise HTTPException(status_code=409, detail="이미 삭제된 댓글입니다.")
            cursor.execute(
                "UPDATE board_a_write SET comment_delete_state = 1, comment_content = '' WHERE bulletin_seq = %s AND comment_seq = %s AND comment_seq > 0",
                (bulletin_seq, comment_seq),
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
    return {"result": "OK", "bulletin_seq": bulletin_seq, "comment_seq": comment_seq, "comment_delete_state": True}

# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
