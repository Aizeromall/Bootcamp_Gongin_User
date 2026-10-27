# 2026-10-27
# 작업자 : 양태건

"""팀 폐지 API.

DELETE /team/delete/{t_id}?c_id_seq=팀장회원ID
팀과 팀장 변경 이력은 보존하고, team_create의 상태·날짜와 팀원 소속을 갱신합니다.
team_create는 팀당 한 행이므로 c_date는 개설 시각에서 폐지 시각으로 바뀝니다.
"""

import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query

from ..database import connect

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 가입 상태는 가입으로 저장하며 기존 가입일 데이터는 조회 호환만 유지합니다.
router = APIRouter()
logger = logging.getLogger(__name__)


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 현재 팀장만 폐지할 수 있습니다. 팀장이 변경되었으면 개설자가 아닌 최신 팀장을 확인합니다.
@router.delete(
    "/delete/{t_id}",
    summary="팀장에 의한 팀 폐지",
    responses={
        403: {"description": "현재 팀장이 아님"},
        404: {"description": "회원 또는 팀 개설 기록이 없음"},
        409: {"description": "이미 폐지된 팀 또는 참조 관계 충돌"},
        500: {"description": "팀 폐지 처리 실패"},
    },
)
def delete_team(
    t_id: int = Path(gt=0, description="폐지할 팀 ID"),
    c_id_seq: str = Query(min_length=1, max_length=50, description="폐지를 요청한 현재 팀장 회원 ID"),
):
    c_id_seq = c_id_seq.strip()
    if not c_id_seq:
        raise HTTPException(status_code=422, detail="팀장 회원 ID를 입력해 주세요.")
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 개설 API와 같이 회원을 먼저 잠가 같은 회원의 동시 개설·폐지를 순차 처리합니다.
            cursor.execute("SELECT c_id_seq FROM customer WHERE c_id_seq = %s FOR UPDATE", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 팀 및 개설 기록을 잠가 같은 팀이 중복 폐지되지 않게 합니다.
            cursor.execute(
                """SELECT t.t_id, t.t_name, tc.c_id_seq, tc.c_category
                   FROM team t INNER JOIN team_create tc ON tc.t_id = t.t_id
                   WHERE t.t_id = %s FOR UPDATE""",
                (t_id,),
            )
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀 또는 개설 기록입니다.")

            # 기존 팀 매칭과 동일하게 최신 변경 기록을 우선하고, 없으면 개설자가 팀장입니다.
            cursor.execute(
                """SELECT t_c_captain FROM team_captain_change WHERE t_id = %s
                   ORDER BY t_c_date DESC, t_c_seq DESC LIMIT 1 FOR UPDATE""",
                (t_id,),
            )
            captain = cursor.fetchone()
            captain_id = captain["t_c_captain"] if captain else team["c_id_seq"]
            if captain_id != c_id_seq:
                raise HTTPException(status_code=403, detail="현재 팀장만 팀을 폐지할 수 있습니다.")
            if team["c_category"] == "폐지일":
                raise HTTPException(status_code=409, detail="이미 폐지된 팀입니다.")

            # 폐지 기록: 개설자 ID를 보존하고 카테고리와 날짜만 폐지 정보로 갱신합니다.
            cursor.execute(
                "UPDATE team_create SET c_category = '폐지일', c_date = NOW() WHERE t_id = %s",
                (t_id,),
            )

            # 이 팀 가입 회원만 처리합니다. 다른 팀명으로 이미 갱신된 회원 소속은 덮어쓰지 않습니다.
            cursor.execute(
                """UPDATE customer c INNER JOIN t_register tr ON tr.c_id_seq = c.c_id_seq
                   SET c.c_team = '무소속' WHERE tr.t_id = %s AND c.c_team = %s AND COALESCE(tr.c_category, '') IN ('', '가입', '가입일')""",
                (t_id, team["t_name"]),
            )

            # 가입 이력은 보존하고 현재 팀원만 폐지 처리 시각의 탈퇴 상태로 바꿉니다.
            cursor.execute(
                """UPDATE t_register SET c_category = '탈퇴', tr_date = NOW()
                   WHERE t_id = %s AND COALESCE(c_category, '') IN ('', '가입', '가입일')""", (t_id,),
            )
            members_released = cursor.rowcount

            # 응답은 실제 저장된 폐지 시각을 사용합니다. team과 팀장 이력은 삭제하지 않습니다.
            cursor.execute("SELECT c_date FROM team_create WHERE t_id = %s", (t_id,))
            closed = cursor.fetchone()
            if closed is None:
                raise RuntimeError("팀 폐지 기록을 확인하지 못했습니다.")

        connection.commit()
        return {
            "result": "OK",
            "t_id": t_id,
            "t_name": team["t_name"],
            "captain_id": captain_id,
            "c_category": "폐지일",
            "c_date": closed["c_date"],
            "members_released": members_released,
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 폐지 정보 충돌")
        raise HTTPException(status_code=409, detail="연결된 팀 정보를 확인해 주세요.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 폐지 처리 실패")
        raise HTTPException(status_code=500, detail="팀 폐지 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
