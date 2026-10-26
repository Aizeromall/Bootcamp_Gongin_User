# 2026-10-26
# 작업자 : 양태건

"""회원 게시판 및 댓글 API.

GET    /board/select                         게시글 목록 (종목·게시판 분류, 검색, 페이지)
GET    /board/select/{bulletin_seq}          게시글 상세 및 조회 수 증가
POST   /board/insert                         게시글 작성
DELETE /board/delete/{bulletin_seq}          본인 게시글 및 연결 댓글 삭제
GET    /board/comment/select/{bulletin_seq}  댓글·대댓글 전체 깊이 조회
POST   /board/comment/insert/{bulletin_seq}  댓글·대댓글 작성
DELETE /board/comment/delete/{comment_seq}  본인 댓글 삭제 표시 (대댓글 유지)

기존 API와 동일하게 c_id_seq로 회원 존재 여부와 작성자를 확인합니다.
DB 구조는 변경하지 않고 database.py의 .env 기반 MySQL 연결을 사용합니다.
"""

import logging
from contextlib import contextmanager
from typing import Optional

import pymysql
from fastapi import APIRouter, Body, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)


# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 공통 요청 검증: 앞뒤 공백을 제거한 뒤 글자 수를 검사하며 불필요한 필드를 받지 않습니다.
class BoardTextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    c_id_seq: str = Field(min_length=1, max_length=50, description="작성 회원의 종목별 ID")


# 게시글 작성에 필요한 값입니다. 조회 수와 작성일은 클라이언트가 지정하지 않습니다.
class InsertBoardRequest(BoardTextRequest):
    event_category: Optional[str] = Field(default=None, min_length=1, max_length=50)
    board_category: Optional[str] = Field(default=None, min_length=1, max_length=50)
    board_title: str = Field(min_length=1, max_length=200)
    board_content: str = Field(min_length=1, max_length=10000)


# 부모 댓글을 생략하면 일반 댓글, 지정하면 부모 depth + 1인 대댓글을 생성합니다.
class InsertCommentRequest(BoardTextRequest):
    comment_content: str = Field(min_length=1, max_length=5000)
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 최초 댓글은 생략 또는 null, 대댓글만 실제 부모 comment_seq를 전달합니다.
    reply_to_comment_seq: Optional[int] = Field(
        default=None, gt=0,
        description="일반 댓글: 생략 또는 null / 대댓글: 같은 게시글의 실제 부모 댓글 번호",
    )



# 모든 API에서 연결 해제, 쓰기 성공 시 commit, 실패 시 rollback을 일관되게 처리합니다.
@contextmanager
def board_connection(write: bool = False):
    connection = None
    try:
        connection = connect()
        yield connection
        if write:
            connection.commit()
    except HTTPException:
        if connection is not None and write:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None and write:
            connection.rollback()
        logger.exception("게시판 참조 관계 충돌")
        raise HTTPException(status_code=409, detail="연결된 게시글 또는 댓글 정보를 확인해 주세요.")
    except Exception:
        if connection is not None and write:
            connection.rollback()
        logger.exception("게시판 처리 실패")
        raise HTTPException(status_code=500, detail="게시판 처리 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 회원 FK가 존재하는지 확인합니다. 작성 및 삭제 요청에 사용합니다.
def require_member(cursor, c_id_seq: str):
    cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (c_id_seq,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")


# 게시글 존재 확인 및 필요 시 잠금: 댓글 등록과 게시글 삭제가 충돌하지 않도록 합니다.
def require_board(cursor, bulletin_seq: int, lock: bool = False) -> dict:
    sql = "SELECT bulletin_seq, c_id_seq FROM board WHERE bulletin_seq = %s"
    if lock:
        sql += " FOR UPDATE"
    cursor.execute(sql, (bulletin_seq,))
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
    return row


# 1. 게시글 목록 조회: 필터 조건을 바인딩하고 목록 조회만으로는 조회 수를 올리지 않습니다.
@router.get("/select", summary="게시글 목록 조회")
def select_boards(
    event_category: Optional[str] = Query(default=None, min_length=1, max_length=50),
    board_category: Optional[str] = Query(default=None, min_length=1, max_length=50),
    keyword: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions = []
    params = []
    for column, value in [("event_category", event_category), ("board_category", board_category)]:
        if value is not None:
            conditions.append(f"b.{column} = %s")
            params.append(value.strip())
    if keyword and keyword.strip():
        # !, %, _를 이스케이프하여 입력한 검색어 자체를 제목·내용에서 찾습니다.
        escaped = keyword.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        conditions.append("(b.board_title LIKE %s ESCAPE '!' OR b.board_content LIKE %s ESCAPE '!')")
        params.extend([f"%{escaped}%", f"%{escaped}%"])
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    with board_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM board b" + where, tuple(params))
            total = cursor.fetchone()["total"]
            cursor.execute(
                """SELECT b.bulletin_seq, b.c_id_seq, c.c_name, b.event_category,
                          b.board_category, b.board_title, b.board_date, b.board_views
                   FROM board b
                   LEFT JOIN customer c ON c.c_id_seq = b.c_id_seq"""
                + where + " ORDER BY b.board_date DESC, b.bulletin_seq DESC LIMIT %s OFFSET %s",
                tuple(params + [limit, offset]),
            )
            rows = cursor.fetchall()
    return {"total": total, "limit": limit, "offset": offset, "results": rows}


# 2. 게시글 상세 조회: 조회 수를 원자적으로 1 증가시키고 상세 내용을 돌려줍니다.
@router.get("/select/{bulletin_seq}", summary="게시글 상세 조회")
def select_board(bulletin_seq: int = Path(gt=0)):
    with board_connection(write=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("UPDATE board SET board_views = board_views + 1 WHERE bulletin_seq = %s", (bulletin_seq,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
            cursor.execute(
                """SELECT b.*, c.c_name FROM board b
                   LEFT JOIN customer c ON c.c_id_seq = b.c_id_seq
                   WHERE b.bulletin_seq = %s""", (bulletin_seq,),
            )
            row = cursor.fetchone()
    return row


# 3. 게시글 작성: 회원 확인 후 작성일은 NOW(), 조회 수는 0으로 저장합니다.
@router.post("/insert", status_code=status.HTTP_201_CREATED, summary="게시글 작성")
def insert_board(payload: InsertBoardRequest):
    with board_connection(write=True) as connection:
        with connection.cursor() as cursor:
            require_member(cursor, payload.c_id_seq)
            cursor.execute(
                """INSERT INTO board
                   (c_id_seq, event_category, board_category, board_title, board_content, board_date, board_views)
                   VALUES (%s, %s, %s, %s, %s, NOW(), 0)""",
                (payload.c_id_seq, payload.event_category, payload.board_category,
                 payload.board_title, payload.board_content),
            )
            bulletin_seq = cursor.lastrowid
    return {"result": "OK", "bulletin_seq": bulletin_seq}


# 4. 게시글 삭제: 작성자만 삭제할 수 있으며 댓글까지 함께 삭제합니다.
# 자기 참조 FK는 먼저 연결을 해제한 뒤 삭제하고, 어느 단계든 실패하면 전체 rollback합니다.
@router.delete("/delete/{bulletin_seq}", summary="본인 게시글 삭제")
def delete_board(
    bulletin_seq: int = Path(gt=0),
    c_id_seq: str = Query(min_length=1, max_length=50),
):
    c_id_seq = c_id_seq.strip()
    with board_connection(write=True) as connection:
        with connection.cursor() as cursor:
            require_member(cursor, c_id_seq)
            row = require_board(cursor, bulletin_seq, lock=True)
            if row["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 게시글만 삭제할 수 있습니다.")
            cursor.execute("UPDATE board_comment SET reply_to_comment_seq = NULL WHERE bulletin_seq = %s", (bulletin_seq,))
            cursor.execute("DELETE FROM board_comment WHERE bulletin_seq = %s", (bulletin_seq,))
            comments_deleted = cursor.rowcount
            cursor.execute("DELETE FROM board WHERE bulletin_seq = %s", (bulletin_seq,))
    return {"result": "OK", "bulletin_seq": bulletin_seq, "comments_deleted": comments_deleted}


# 5. 댓글 정렬: 재귀 호출 없이 부모 다음에 자식이 오는 순서로 펼칩니다.
# depth가 커져도 호출 스택을 사용하지 않으며, 삭제 댓글은 원문을 노출하지 않습니다.
def order_comments(rows: list[dict]) -> list[dict]:
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
    with board_connection() as connection:
        with connection.cursor() as cursor:
            require_board(cursor, bulletin_seq)
            cursor.execute(
                """SELECT q.comment_seq, q.bulletin_seq, q.c_id_seq, c.c_name,
                          q.reply_to_comment_seq, q.depth, q.comment_content, q.comment_delete_state
                   FROM board_comment q
                   LEFT JOIN customer c ON c.c_id_seq = q.c_id_seq
                   WHERE q.bulletin_seq = %s ORDER BY q.comment_seq ASC""", (bulletin_seq,),
            )
            rows = order_comments(cursor.fetchall())
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
    with board_connection(write=True) as connection:
        with connection.cursor() as cursor:
            # 게시글을 먼저 잠가 게시글 삭제와 댓글 작성의 실행 순서를 맞춥니다.
            require_board(cursor, bulletin_seq, lock=True)
            require_member(cursor, payload.c_id_seq)
            depth = 0
            if payload.reply_to_comment_seq is not None:
                cursor.execute(
                    """SELECT comment_seq, bulletin_seq, depth FROM board_comment
                       WHERE comment_seq = %s FOR UPDATE""", (payload.reply_to_comment_seq,),
                )
                parent = cursor.fetchone()
                if parent is None:
                    raise HTTPException(status_code=404, detail="부모 댓글이 존재하지 않습니다.")
                if parent["bulletin_seq"] != bulletin_seq:
                    raise HTTPException(status_code=409, detail="같은 게시글의 댓글에만 답변할 수 있습니다.")
                if not 0 <= parent["depth"] < 2147483647:
                    raise HTTPException(status_code=409, detail="댓글 깊이 정보를 확인해 주세요.")
                depth = parent["depth"] + 1
            cursor.execute(
                """INSERT INTO board_comment
                   (bulletin_seq, c_id_seq, reply_to_comment_seq, depth, comment_content, comment_delete_state)
                   VALUES (%s, %s, %s, %s, %s, 0)""",
                (bulletin_seq, payload.c_id_seq, payload.reply_to_comment_seq, depth, payload.comment_content),
            )
            comment_seq = cursor.lastrowid
    return {"result": "OK", "bulletin_seq": bulletin_seq, "comment_seq": comment_seq,
            "reply_to_comment_seq": payload.reply_to_comment_seq, "depth": depth}


# 8. 댓글 삭제: 작성자만 삭제 표시할 수 있으며 자식 댓글과 부모 번호는 보존합니다.
@router.delete("/comment/delete/{comment_seq}", summary="본인 댓글 삭제")
def delete_comment(
    comment_seq: int = Path(gt=0),
    c_id_seq: str = Query(min_length=1, max_length=50),
):
    c_id_seq = c_id_seq.strip()
    with board_connection(write=True) as connection:
        with connection.cursor() as cursor:
            require_member(cursor, c_id_seq)
            cursor.execute(
                "SELECT comment_seq, c_id_seq, comment_delete_state FROM board_comment WHERE comment_seq = %s FOR UPDATE",
                (comment_seq,),
            )
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 댓글입니다.")
            if row["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 댓글만 삭제할 수 있습니다.")
            if row["comment_delete_state"]:
                raise HTTPException(status_code=409, detail="이미 삭제된 댓글입니다.")
            cursor.execute(
                "UPDATE board_comment SET comment_delete_state = 1, comment_content = '' WHERE comment_seq = %s",
                (comment_seq,),
            )
    return {"result": "OK", "comment_seq": comment_seq, "comment_delete_state": True}


# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
