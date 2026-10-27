# 2026-10-26
# 작업자 : 양태건

"""게시글 목록·상세 조회 router."""
from typing import Optional

import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query


from ..database import connect
from .insert import BoardCategory, EventCategory

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 실제 DB board_a_write 사용: comment_seq=0은 게시글, 양수는 댓글입니다.
# 모든 댓글 식별·변경은 게시글 번호와 댓글 번호의 복합 PK를 사용합니다.
router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 기존 게시글 조회 API와 상세 조회 시 조회 수 증가 동작을 유지합니다.
# 1. 게시글 목록 조회: 필터 조건을 바인딩하고 목록 조회만으로는 조회 수를 올리지 않습니다.
@router.get("/select", summary="게시글 목록 조회")
def select_boards(
    event_category: Optional[EventCategory] = Query(default=None),
    board_category: Optional[BoardCategory] = Query(default=None),
    keyword: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions = ["b.comment_seq = 0"]
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
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) AS total FROM board_a_write b" + where, tuple(params))
            total = cursor.fetchone()["total"]
            cursor.execute(
                """SELECT b.bulletin_seq, b.c_id_seq, c.c_name, b.event_category,
                          b.board_category, b.board_title, b.board_date, b.board_views
                   FROM board_a_write b
                   LEFT JOIN customer c ON c.c_id_seq = b.c_id_seq"""
                + where + " ORDER BY b.board_date DESC, b.bulletin_seq DESC LIMIT %s OFFSET %s",
                tuple(params + [limit, offset]),
            )
            rows = cursor.fetchall()
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
    return {"total": total, "limit": limit, "offset": offset, "results": rows}


# 2. 게시글 상세 조회: 조회 수를 원자적으로 1 증가시키고 상세 내용을 돌려줍니다.
@router.get("/select/{bulletin_seq}", summary="게시글 상세 조회")
def select_board(bulletin_seq: int = Path(gt=0)):
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute("UPDATE board_a_write SET board_views = board_views + 1 WHERE bulletin_seq = %s AND comment_seq = 0", (bulletin_seq,))
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
            cursor.execute(
                """SELECT b.*, c.c_name FROM board_a_write b
                   LEFT JOIN customer c ON c.c_id_seq = b.c_id_seq
                   WHERE b.bulletin_seq = %s AND b.comment_seq = 0""", (bulletin_seq,),
            )
            row = cursor.fetchone()
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
    return row

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
