# 2026-10-27
# 작업자 : 양태건

"""팀 목록·상세 조회 API.

GET /team/select                       운영 중인 팀 목록
GET /team/select?include_closed=true   폐지된 팀까지 포함한 목록
GET /team/select/{t_id}                팀 상세 (폐지 기록도 조회 가능)
DB 구조와 데이터는 변경하지 않고 SELECT만 실행합니다.
"""

import logging
from typing import Optional

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query

from ..database import connect

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 가입 상태는 가입으로 저장하며 기존 가입일 데이터는 조회 호환만 유지합니다.
router = APIRouter()
logger = logging.getLogger(__name__)


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 팀 개설·폐지와 같은 테이블을 사용하며 팀장 변경 기록 중 가장 최근 팀장을 조회합니다.
# 개설 기록이 없는 기존 팀도 LEFT JOIN으로 목록에서 빠지지 않게 합니다.
# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 팀원 수는 가입 또는 기존 빈 상태인 회원만 세며 탈퇴 이력은 제외합니다.
TEAM_SELECT = """
    SELECT t.t_id, t.t_name, t.t_logo, t.t_rating,
           tc.c_id_seq AS creator_id, tc.c_category, tc.c_date,
           captain.c_id_seq AS captain_id, captain.c_name AS captain_name,
           (SELECT COUNT(*) FROM t_register tr WHERE tr.t_id = t.t_id AND COALESCE(tr.c_category, '') IN ('', '가입', '가입일')) AS member_count
    FROM team t
    LEFT JOIN team_create tc ON tc.t_id = t.t_id
    LEFT JOIN customer captain ON captain.c_id_seq = COALESCE(
        (SELECT cc.t_c_captain FROM team_captain_change cc
         WHERE cc.t_id = t.t_id ORDER BY cc.t_c_date DESC, cc.t_c_seq DESC LIMIT 1),
        tc.c_id_seq
    )
"""


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# c_date는 개설 상태면 개설 시각, 폐지 상태면 폐지 시각입니다.
# 폐지된 팀의 captain_id/name은 마지막 팀장 이력이며 현재 매칭 권한을 뜻하지 않습니다.
def team_to_dict(row: dict) -> dict:
    return {**row, "is_closed": row["c_category"] == "폐지일"}


# 팀 목록: 팀명 검색·페이지 처리를 지원하며 기본적으로 폐지된 팀은 제외합니다.
@router.get("/select", summary="팀 목록 조회")
def select_teams(
    keyword: Optional[str] = Query(default=None, max_length=50, description="팀명 검색"),
    include_closed: bool = Query(default=False, description="폐지된 팀도 포함할지 여부"),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    conditions = []
    params = []
    if not include_closed:
        conditions.append("COALESCE(tc.c_category, '') <> '폐지일'")
    if keyword and keyword.strip():
        # 검색어의 %, _를 와일드카드로 해석하지 않고 입력한 글자 그대로 검색합니다.
        escaped = keyword.strip().replace("!", "!!").replace("%", "!%").replace("_", "!_")
        conditions.append("t.t_name LIKE %s ESCAPE '!'")
        params.append(f"%{escaped}%")
    where = " WHERE " + " AND ".join(conditions) if conditions else ""
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # total은 페이지 크기와 관계없는 전체 검색 결과 수입니다.
            cursor.execute(
                "SELECT COUNT(*) AS total FROM team t LEFT JOIN team_create tc ON tc.t_id = t.t_id" + where,
                tuple(params),
            )
            total = cursor.fetchone()["total"]
            cursor.execute(
                TEAM_SELECT + where + " ORDER BY t.t_id DESC LIMIT %s OFFSET %s",
                tuple(params + [limit, offset]),
            )
            rows = [team_to_dict(row) for row in cursor.fetchall()]
        return {"total": total, "limit": limit, "offset": offset, "results": rows}
    except pymysql.MySQLError:
        logger.exception("팀 목록 DB 조회 실패")
        raise HTTPException(status_code=500, detail="팀 목록 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀 목록 조회 실패")
        raise HTTPException(status_code=500, detail="팀 목록 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 팀 상세: 팀 정보·팀원 수·팀장 및 개설/폐지 상태를 확인합니다. 조회 수 등의 쓰기는 없습니다.
@router.get("/select/{t_id}", summary="팀 상세 조회")
def select_team(t_id: int = Path(gt=0, description="조회할 팀 ID")):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute(TEAM_SELECT + " WHERE t.t_id = %s", (t_id,))
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀입니다.")
        return team_to_dict(row)
    except HTTPException:
        raise
    except pymysql.MySQLError:
        logger.exception("팀 상세 DB 조회 실패")
        raise HTTPException(status_code=500, detail="팀 상세 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀 상세 조회 실패")
        raise HTTPException(status_code=500, detail="팀 상세 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
