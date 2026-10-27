# 작업자 : 최현준
# 최초 작업 일 : 2026-10-27

"""announcement 테이블의 사용자 대상 공지만 조회하는 읽기 전용 API."""

import logging
from typing import Annotated

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)

# 대상은 요청값으로 받지 않습니다. 공백이 붙은 값이나 다른 대상도 제외합니다.
USER_TARGET = "사용자"
TARGET_CONDITION = "CAST(a_target AS BINARY) = CAST(%s AS BINARY)"
PUBLIC_COLUMNS = "a_seq, a_classify, a_title, a_detail, a_date, a_target"
SERVER_ERROR = {
    500: {"description": "DB 연결·조회 실패 또는 서버 처리 오류"},
}


def select_rows(sql: str, params: tuple) -> list[dict]:
    """공통 DB 조회: 파라미터 바인딩을 사용하고 연결을 반드시 종료합니다."""

    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute(sql, params)
            return list(cursor.fetchall())
    except pymysql.MySQLError:
        logger.exception("사용자 공지 DB 조회 실패")
        raise HTTPException(status_code=500, detail="공지 조회 중 DB 오류가 발생했습니다.") from None
    except Exception:
        logger.exception("사용자 공지 처리 실패")
        raise HTTPException(status_code=500, detail="공지 조회에 실패했습니다.") from None
    finally:
        if connection is not None:
            connection.close()


# 상세 번호 경로보다 먼저 등록해 categories가 번호로 해석되지 않게 합니다.
@router.get(
    "/categories",
    summary="사용자 공지의 분류 목록 조회",
    responses=SERVER_ERROR,
)
def list_categories() -> dict:
    """사용자 공지에 존재하는 분류만 반환합니다. 공지가 없으면 빈 목록입니다."""

    # 매니저·본사 공지에만 있는 분류는 사용자에게도 노출하지 않습니다.
    # NULL·공백 분류는 선택 목록에서 제외하며, 전체 공지 조회에서는 볼 수 있습니다.
    rows = select_rows(
        f"""SELECT DISTINCT a_classify FROM announcement
            WHERE {TARGET_CONDITION}
              AND a_classify IS NOT NULL AND TRIM(a_classify) <> ''
            ORDER BY a_classify""",
        (USER_TARGET,),
    )
    return {"results": [row["a_classify"] for row in rows]}


@router.get(
    "",
    summary="사용자 공지 목록 및 분류별 조회",
    responses={
        400: {"description": "분류에 공백만 입력됨"},
        422: {"description": "분류 길이 또는 페이지 범위 검증 실패"},
        **SERVER_ERROR,
    },
)
def list_announcements(
    a_classify: Annotated[str | None, Query(min_length=1, max_length=50, description="분류 목록에서 선택한 값. 생략하면 전체")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="페이지당 조회 건수")] = 20,
    offset: Annotated[int, Query(ge=0, description="건너뛸 건수")] = 0,
) -> dict:
    """등록일과 번호 내림차순으로 조회합니다. 존재하지 않는 분류는 빈 목록입니다."""

    sql = f"SELECT {PUBLIC_COLUMNS} FROM announcement WHERE {TARGET_CONDITION}"
    params = [USER_TARGET]
    if a_classify is not None:
        if not a_classify.strip():
            raise HTTPException(status_code=400, detail="분류에는 공백만 입력할 수 없습니다.")
        # 분류를 하드코딩하지 않고 DB에 존재하는 값과 비교합니다.
        sql += " AND a_classify = %s"
        params.append(a_classify)
    sql += " ORDER BY a_date DESC, a_seq DESC LIMIT %s OFFSET %s"
    rows = select_rows(sql, (*params, limit, offset))
    return {"results": rows, "limit": limit, "offset": offset}


@router.get(
    "/{a_seq}",
    summary="사용자 공지 상세 조회",
    responses={
        404: {"description": "존재하지 않거나 사용자 대상이 아닌 공지"},
        422: {"description": "공지 번호는 1 이상의 정수여야 함"},
        **SERVER_ERROR,
    },
)
def get_announcement(a_seq: Annotated[int, Path(gt=0, description="공지 번호")]) -> dict:
    """번호를 알고 있어도 사용자 대상 공지에만 접근할 수 있습니다."""

    rows = select_rows(
        f"SELECT {PUBLIC_COLUMNS} FROM announcement WHERE a_seq = %s AND {TARGET_CONDITION} LIMIT 1",
        (a_seq, USER_TARGET),
    )
    if not rows:
        # 비공개 공지의 존재 여부도 노출하지 않도록 동일한 404 응답을 사용합니다.
        raise HTTPException(status_code=404, detail="조회할 수 있는 공지가 없습니다.")
    return rows[0]

# 최종 수정 일 : 2026-10-27
