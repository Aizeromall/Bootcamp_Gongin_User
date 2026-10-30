# 2026-10-30
# 작업자 : 김병재

"""내 소속팀 팀원 목록 조회 API.

GET /my_team/members/{t_id}   내가 가입(승인)된 팀의 현재 팀원 목록 (팀장 먼저)
DB 구조와 데이터는 변경하지 않고 SELECT만 실행합니다.
"""

import logging

import pymysql
from fastapi import APIRouter, Depends, HTTPException, Path

from ..auth.token import current_account
from ..database import connect
from ..rating.rating_search import rating_tier
from ..team_create.apply_team import active_registration

router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 현재 팀장은 /team/select와 같이 최근 팀장 변경 이력, 없으면 개설자로 판단합니다.
CAPTAIN_SELECT = """
    SELECT COALESCE(
        (SELECT cc.t_c_captain FROM team_captain_change cc
         WHERE cc.t_id = t.t_id ORDER BY cc.t_c_date DESC, cc.t_c_seq DESC LIMIT 1),
        tc.c_id_seq) AS captain_id, tc.c_category
    FROM team t LEFT JOIN team_create tc ON tc.t_id = t.t_id
    WHERE t.t_id = %s
"""

# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 승인된 팀원(기존 빈 상태 가입 데이터 포함)만 조회합니다. 대기·거절·탈퇴 회원은 제외합니다.
MEMBER_SELECT = f"""
    SELECT tr.c_id_seq, cu.c_name, cu.c_position, cu.c_rating, tr.tr_date
    FROM t_register tr
    INNER JOIN customer cu ON cu.c_id_seq = tr.c_id_seq
    WHERE tr.t_id = %s AND {active_registration('tr')} AND cu.c_deletdate IS NULL
    ORDER BY tr.tr_date, tr.tr_seq
"""


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 팀원 목록: 로그인 JWT의 종목 회원 ID 중 하나가 이 팀의 팀원일 때만 조회할 수 있습니다.
# 응답에는 이름·포지션·등급만 담고 연락처 등 개인정보는 반환하지 않습니다.
@router.get("/members/{t_id}", summary="내 소속팀 팀원 목록", responses={
    401: {"description": "로그인 JWT 누락·위조·만료"},
    403: {"description": "내가 가입된 팀이 아님"},
    404: {"description": "존재하지 않거나 폐지된 팀"},
    500: {"description": "DB 조회 실패"},
})
def list_team_members(t_id: int = Path(gt=0, description="팀 ID"),
                      account: dict = Depends(current_account)) -> dict:
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute(CAPTAIN_SELECT, (t_id,))
            team = cursor.fetchone()
            if team is None or team["c_category"] == "폐지일":
                raise HTTPException(status_code=404, detail="존재하지 않거나 폐지된 팀입니다.")
            cursor.execute(MEMBER_SELECT, (t_id,))
            rows = cursor.fetchall()
    except HTTPException:
        raise
    except pymysql.MySQLError:
        logger.exception("팀원 목록 DB 조회 실패")
        raise HTTPException(status_code=500, detail="팀원 목록 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀원 목록 조회 실패")
        raise HTTPException(status_code=500, detail="팀원 목록 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

    # 본인 확인: 내 종목 회원 ID 중 하나가 승인된 팀원이어야 합니다.
    if not any(row["c_id_seq"] in account["member_ids"] for row in rows):
        raise HTTPException(status_code=403, detail="가입된 팀의 팀원만 확인할 수 있습니다.")
    members = [{
        "c_id_seq": row["c_id_seq"], "c_name": row["c_name"], "c_position": row["c_position"],
        "c_rating": row["c_rating"], "tier": rating_tier(row["c_rating"]), "tr_date": row["tr_date"],
        "is_captain": row["c_id_seq"] == team["captain_id"],
        "is_me": row["c_id_seq"] in account["member_ids"],
    } for row in rows]
    # 팀장을 맨 앞에 두고 나머지는 가입 순서를 유지합니다(sorted는 안정 정렬).
    members = sorted(members, key=lambda member: not member["is_captain"])
    return {"t_id": t_id, "captain_id": team["captain_id"], "total": len(members), "results": members}

# 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
