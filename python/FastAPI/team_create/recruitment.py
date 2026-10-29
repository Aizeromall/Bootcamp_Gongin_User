# 2026-10-28
# 작업자 : 양태건
"""tr_state를 이용한 팀 단위 가입 신청 조회·승인·거절. DB 구조는 변경하지 않습니다."""
import logging

from fastapi import APIRouter, HTTPException, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from ..database import connect
from .apply_team import active_registration, recruitment_team

router = APIRouter()
logger = logging.getLogger(__name__)


class RecruitmentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    c_id_seq: str = Field(min_length=1, max_length=50, description="현재 팀장 회원 ID")
    applicant_id: str = Field(min_length=1, max_length=50, description="신청 회원 ID")


# 수정 일 : 2026-10-28 / 작업자 : 양태건
# 팀장이 아닌 회원에게는 본인 신청 상태만 전달하고 다른 신청자 정보를 노출하지 않습니다.
@router.get("/recruitment/{bulletin_seq}", summary="모집 글의 팀·본인 상태·팀장 신청 목록")
def select_recruitment(bulletin_seq: int = Path(gt=0), c_id_seq: str = Query(min_length=1, max_length=50)):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            team = recruitment_team(cursor, bulletin_seq)
            cursor.execute("SELECT tr_state, c_category FROM t_register WHERE t_id = %s AND c_id_seq = %s",
                           (team["t_id"], c_id_seq))
            mine = cursor.fetchone()
            cursor.execute(f"SELECT t_id FROM t_register WHERE c_id_seq = %s AND {active_registration()} LIMIT 1",
                           (c_id_seq,))
            membership = cursor.fetchone()
            own = team["captain_id"] == c_id_seq
            rows = []
            if own:
                cursor.execute("""SELECT tr.tr_seq, tr.c_id_seq, cu.c_name, tr.tr_state, tr.tr_date
                    FROM t_register tr INNER JOIN customer cu ON cu.c_id_seq = tr.c_id_seq
                    WHERE tr.t_id = %s AND tr.tr_state IN ('대기', '승인', '거절')
                      AND tr.c_id_seq <> %s ORDER BY tr.tr_date DESC, tr.tr_seq DESC""",
                    (team["t_id"], c_id_seq))
                rows = cursor.fetchall()
        closed = team["c_category"] == "폐지일"
        return {"team": team, "can_manage": own and not closed,
                "can_apply": not own and not closed and membership is None and (mine is None or mine["tr_state"] != "대기"),
                "my_state": "가입" if membership and membership["t_id"] == team["t_id"] else (mine or {}).get("tr_state"),
                "results": rows}
    except HTTPException:
        raise
    except Exception:
        logger.exception("모집 신청 조회 실패")
        raise HTTPException(status_code=500, detail="모집 신청 정보를 확인하지 못했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 수정 일 : 2026-10-28 / 작업자 : 양태건
# 신청 회원→팀 순서로 잠가 중복 승인·다른 팀 동시 가입을 막고 승인 때만 실제 소속을 반영합니다.
def decide(payload, t_id, accept):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT c_id_seq FROM customer WHERE c_id_seq = %s FOR UPDATE", (payload.applicant_id,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 신청 회원입니다.")
            cursor.execute("""SELECT t.t_id, t.t_name, tc.c_category, COALESCE(
                (SELECT cc.t_c_captain FROM team_captain_change cc WHERE cc.t_id = t.t_id
                 ORDER BY cc.t_c_date DESC, cc.t_c_seq DESC LIMIT 1), tc.c_id_seq) AS captain_id
                FROM team t INNER JOIN team_create tc ON tc.t_id = t.t_id WHERE t.t_id = %s FOR UPDATE""", (t_id,))
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀입니다.")
            if team["captain_id"] != payload.c_id_seq:
                raise HTTPException(status_code=403, detail="현재 팀장만 신청을 처리할 수 있습니다.")
            if team["c_category"] == "폐지일":
                raise HTTPException(status_code=409, detail="폐지된 팀의 신청은 처리할 수 없습니다.")
            cursor.execute("SELECT tr_seq, tr_state FROM t_register WHERE t_id = %s AND c_id_seq = %s FOR UPDATE",
                           (t_id, payload.applicant_id))
            application = cursor.fetchone()
            if application is None:
                raise HTTPException(status_code=404, detail="가입 신청이 없습니다.")
            if application["tr_state"] != "대기":
                raise HTTPException(status_code=409, detail="대기 중인 신청만 처리할 수 있습니다.")
            if accept:
                cursor.execute(f"SELECT t_id FROM t_register WHERE c_id_seq = %s AND {active_registration()} LIMIT 1 FOR UPDATE",
                               (payload.applicant_id,))
                if cursor.fetchone() is not None:
                    raise HTTPException(status_code=409, detail="신청 회원이 이미 다른 팀에 가입했습니다.")
                cursor.execute("UPDATE customer SET c_team = %s WHERE c_id_seq = %s", (team["t_name"], payload.applicant_id))
                # 다른 팀 대기 신청은 더 이상 가입할 수 없으므로 함께 거절 처리합니다.
                cursor.execute("""UPDATE t_register SET tr_state = '거절', tr_date = NOW()
                    WHERE c_id_seq = %s AND t_id <> %s AND tr_state = '대기'""", (payload.applicant_id, t_id))
            state = "승인" if accept else "거절"
            cursor.execute("UPDATE t_register SET tr_state = %s, c_category = %s, tr_date = NOW() WHERE tr_seq = %s",
                           (state, "가입" if accept else "", application["tr_seq"]))
        connection.commit()
        return {"result": "OK", "t_id": t_id, "c_id_seq": payload.applicant_id, "tr_state": state}
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("모집 신청 처리 실패")
        raise HTTPException(status_code=500, detail="가입 신청 처리 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


@router.post("/approve/{t_id}", summary="팀장이 가입 신청 승인")
def approve_recruitment(payload: RecruitmentDecision, t_id: int = Path(gt=0)):
    return decide(payload, t_id, True)


@router.post("/reject/{t_id}", summary="팀장이 가입 신청 거절")
def reject_recruitment(payload: RecruitmentDecision, t_id: int = Path(gt=0)):
    return decide(payload, t_id, False)

# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건

# 수정 일 : 2026-10-28 / 작업자 : 양태건
# 모집 글이 없어도 팀 정보 화면에서 현재 팀장이 가입 신청을 관리할 수 있습니다.
@router.get("/applications/{t_id}", summary="현재 팀장의 가입 신청 목록")
def select_team_applications(t_id: int = Path(gt=0), c_id_seq: str = Query(min_length=1, max_length=50)):
    from .select import TEAM_SELECT
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute(TEAM_SELECT + " WHERE t.t_id = %s", (t_id,))
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀입니다.")
            if team["captain_id"] != c_id_seq:
                raise HTTPException(status_code=403, detail="현재 팀장만 신청 목록을 확인할 수 있습니다.")
            cursor.execute("""SELECT tr.tr_seq, tr.c_id_seq, cu.c_name, tr.tr_state, tr.tr_date
                FROM t_register tr INNER JOIN customer cu ON cu.c_id_seq = tr.c_id_seq
                WHERE tr.t_id = %s AND tr.tr_state IN ('대기', '승인', '거절') AND tr.c_id_seq <> %s
                ORDER BY tr.tr_date DESC, tr.tr_seq DESC""", (t_id, c_id_seq))
            rows = cursor.fetchall()
        return {"team": team, "can_manage": team['c_category'] != '폐지일', "can_apply": False, "results": rows}
    except HTTPException:
        raise
    except Exception:
        logger.exception("팀 신청 목록 조회 실패")
        raise HTTPException(status_code=500, detail="신청 목록을 확인하지 못했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
