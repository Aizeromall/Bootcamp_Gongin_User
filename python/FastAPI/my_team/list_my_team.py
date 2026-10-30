# 2026-10-30
# 작업자 : 김병재

"""내 소속팀 조회 API.

GET /my_team   로그인 JWT의 모든 종목 회원 ID(member_ids)별 소속팀과 가입 신청 대기 팀
DB 구조와 데이터는 변경하지 않고 SELECT만 실행합니다.
"""

import logging

import pymysql
from fastapi import APIRouter, Depends, HTTPException

from ..auth.token import current_account
from ..database import connect
from ..rating.rating_search import rating_tier
from ..team_create.apply_team import active_registration

router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 종목 코드는 회원 ID 끝자리(_01=축구, _02=농구, _03=야구, _04=배구)입니다.
SPORT_NAMES = {1: "축구", 2: "농구", 3: "야구", 4: "배구"}

# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 팀 정보는 /team/select와 같은 기준(최근 팀장 변경 이력 우선, 승인된 팀원 수)으로 조회합니다.
# 폐지된 팀은 팀 폐지 시 가입 기록도 탈퇴 처리되지만, 이전 데이터에 대비해 한 번 더 제외합니다.
MY_TEAM_SELECT = f"""
    SELECT tr.c_id_seq, tr.tr_state, tr.tr_date,
           t.t_id, t.t_name, t.t_logo, t.t_rating,
           tc.c_id_seq AS creator_id, tc.c_date,
           captain.c_id_seq AS captain_id, captain.c_name AS captain_name,
           (SELECT COUNT(*) FROM t_register member WHERE member.t_id = t.t_id
              AND {active_registration('member')}) AS member_count
    FROM t_register tr
    INNER JOIN team t ON t.t_id = tr.t_id
    LEFT JOIN team_create tc ON tc.t_id = t.t_id
    LEFT JOIN customer captain ON captain.c_id_seq = COALESCE(
        (SELECT cc.t_c_captain FROM team_captain_change cc
         WHERE cc.t_id = t.t_id ORDER BY cc.t_c_date DESC, cc.t_c_seq DESC LIMIT 1),
        tc.c_id_seq
    )
    WHERE tr.c_id_seq IN %s
      AND COALESCE(tc.c_category, '') <> '폐지일'
      AND (({active_registration('tr')}) OR tr.tr_state = '대기')
    ORDER BY tr.c_id_seq, tr.tr_date DESC, t.t_id DESC
"""


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 응답에 노출할 팀 필드만 고릅니다. 회원 개인정보는 팀장 이름 외에 반환하지 않습니다.
def team_summary(row: dict, member_id: str) -> dict:
    return {
        "t_id": row["t_id"], "t_name": row["t_name"], "t_logo": row["t_logo"],
        "t_rating": row["t_rating"], "creator_id": row["creator_id"], "c_date": row["c_date"],
        "captain_id": row["captain_id"], "captain_name": row["captain_name"],
        "member_count": row["member_count"], "tr_date": row["tr_date"],
        # 수정 일 : 2026-10-30 / 작업자 : 김병재
        # 팀 등급은 /rating과 같은 구간표(rating_tier)로 계산해 팀 탭 배너에 표시합니다.
        "tier": rating_tier(row["t_rating"]),
        # 앱에서 팀장 전용 버튼(팀원 승인·팀장 위임·폐지)을 보여줄지 판단하는 값입니다.
        "is_captain": row["captain_id"] == member_id,
    }


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 내 소속팀 조회: 종목마다 소속팀(team, 없으면 null)과 승인 대기 중인 신청 팀(pending)을 함께 반환합니다.
# 회원 ID는 요청값이 아니라 서명된 JWT의 member_ids만 사용하므로 다른 회원의 소속은 조회할 수 없습니다.
@router.get("", summary="내 종목별 소속팀 조회", responses={
    401: {"description": "로그인 JWT 누락·위조·만료"},
    500: {"description": "DB 조회 실패"},
    503: {"description": "AUTH_TOKEN_SECRET 미설정"},
})
def list_my_team(account: dict = Depends(current_account)) -> dict:
    member_ids = sorted(account["member_ids"])
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute(MY_TEAM_SELECT, (tuple(member_ids),))
            rows = cursor.fetchall()
    except pymysql.MySQLError:
        logger.exception("내 소속팀 DB 조회 실패")
        raise HTTPException(status_code=500, detail="소속팀 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("내 소속팀 조회 실패")
        raise HTTPException(status_code=500, detail="소속팀 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

    # 종목별 회원 ID 순서대로 결과 틀을 먼저 만들어, 팀이 없는 종목도 team=null로 반환합니다.
    results = {
        member_id: {"c_id_seq": member_id, "sport": int(member_id[-2:]),
                    "sport_name": SPORT_NAMES.get(int(member_id[-2:])), "team": None, "pending": []}
        for member_id in member_ids
    }
    for row in rows:
        result = results[row["c_id_seq"]]
        if row["tr_state"] == "대기":
            result["pending"].append(team_summary(row, row["c_id_seq"]))
        elif result["team"] is None:
            # 서버는 종목별 회원당 소속팀을 하나만 허용합니다. 예외 데이터가 있으면 최근 가입 팀을 사용합니다.
            result["team"] = team_summary(row, row["c_id_seq"])
    return {"results": list(results.values())}

# 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
