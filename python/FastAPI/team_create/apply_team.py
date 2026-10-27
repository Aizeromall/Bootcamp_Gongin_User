# 2026-10-27
# 작업자 : 양태건

"""팀 가입·탈퇴 API.

POST /team/apply/{t_id}                     가입 신청 즉시 가입 완료
DELETE /team/leave/{t_id}?c_id_seq=회원ID   본인 팀 탈퇴
c_category='가입'/'탈퇴', tr_date=해당 처리 시각으로 저장합니다.
(c_id_seq, t_id)가 UNIQUE이므로 재가입 시 기존 행을 갱신하며 가장 최근 상태·날짜를 보관합니다.
승인 대기·거절 기능은 없으며 기존 빈 값·가입일·탈퇴일도 읽기 호환합니다.
새로 저장하거나 상태를 변경할 때는 가입·탈퇴만 사용합니다.
"""

import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query, status
from pydantic import BaseModel, ConfigDict, Field

from ..database import connect

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 가입 상태는 가입으로 저장하며 기존 가입일 데이터는 조회 호환만 유지합니다.
router = APIRouter()
logger = logging.getLogger(__name__)


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 날짜와 카테고리는 회원이 입력하지 않고 서버에서 가입·탈퇴 처리에 따라 정합니다.
class ApplyTeamRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True,
        json_schema_extra={"example": {"c_id_seq": "member_01"}},
    )
    c_id_seq: str = Field(min_length=1, max_length=50, description="가입할 종목별 회원 ID")


# 가입 완료: 회원·팀을 잠그고 중복 소속을 확인한 뒤 가입 기록과 회원 소속을 함께 저장합니다.
@router.post("/apply/{t_id}", status_code=status.HTTP_201_CREATED, summary="팀 가입 신청 및 가입 완료")
def apply_team(payload: ApplyTeamRequest, t_id: int = Path(gt=0)):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT c_id_seq FROM customer WHERE c_id_seq = %s FOR UPDATE", (payload.c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 팀 폐지와 가입 처리가 서로 끼어들지 않도록 같은 팀 행을 잠급니다.
            cursor.execute(
                """SELECT t.t_id, t.t_name, tc.c_category FROM team t
                   INNER JOIN team_create tc ON tc.t_id = t.t_id
                   WHERE t.t_id = %s FOR UPDATE""", (t_id,),
            )
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀 또는 개설 기록입니다.")
            if team["c_category"] == "폐지일":
                raise HTTPException(status_code=409, detail="폐지된 팀에는 가입할 수 없습니다.")

            # 같은 종목 회원 ID는 한 팀에만 소속됩니다. 탈퇴 이력은 현재 소속에서 제외합니다.
            cursor.execute(
                """SELECT t_id FROM t_register WHERE c_id_seq = %s
                   AND COALESCE(c_category, '') IN ('', '가입', '가입일') LIMIT 1 FOR UPDATE""",
                (payload.c_id_seq,),
            )
            membership = cursor.fetchone()
            if membership is not None:
                message = "이미 가입한 팀입니다." if membership["t_id"] == t_id else "이미 다른 팀에 소속되어 있습니다."
                raise HTTPException(status_code=409, detail=message)

            # UNIQUE(c_id_seq, t_id) 때문에 탈퇴했던 팀에 재가입할 때는 기존 행을 사용합니다.
            cursor.execute(
                "SELECT tr_seq, c_category FROM t_register WHERE c_id_seq = %s AND t_id = %s FOR UPDATE",
                (payload.c_id_seq, t_id),
            )
            previous = cursor.fetchone()
            if previous is None:
                cursor.execute(
                    """INSERT INTO t_register (c_id_seq, t_id, tr_date, c_category)
                       VALUES (%s, %s, NOW(), '가입')""", (payload.c_id_seq, t_id),
                )
            else:
                if previous["c_category"] not in ("탈퇴", "탈퇴일"):
                    raise HTTPException(status_code=409, detail="기존 가입 상태를 확인해 주세요.")
                cursor.execute(
                    """UPDATE t_register SET c_category = '가입', tr_date = NOW()
                       WHERE tr_seq = %s AND c_id_seq = %s AND t_id = %s""",
                    (previous["tr_seq"], payload.c_id_seq, t_id),
                )
            cursor.execute("UPDATE customer SET c_team = %s WHERE c_id_seq = %s", (team["t_name"], payload.c_id_seq))
            cursor.execute(
                "SELECT tr_seq, tr_date, c_category FROM t_register WHERE c_id_seq = %s AND t_id = %s",
                (payload.c_id_seq, t_id),
            )
            joined = cursor.fetchone()
            if joined is None:
                raise RuntimeError("가입 기록을 확인하지 못했습니다.")
        connection.commit()
        return {"result": "OK", "t_id": t_id, "t_name": team["t_name"], "c_id_seq": payload.c_id_seq, **joined}
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 가입 정보 충돌")
        raise HTTPException(status_code=409, detail="회원 또는 가입 정보를 확인해 주세요.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 가입 처리 실패")
        raise HTTPException(status_code=500, detail="팀 가입 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 탈퇴 기록은 삭제하지 않습니다. 현재 팀장은 먼저 다른 회원에게 팀장을 넘겨야 합니다.
@router.delete("/leave/{t_id}", summary="본인 팀 탈퇴")
def leave_team(t_id: int = Path(gt=0), c_id_seq: str = Query(min_length=1, max_length=50)):
    c_id_seq = c_id_seq.strip()
    if not c_id_seq:
        raise HTTPException(status_code=422, detail="회원 ID를 입력해 주세요.")
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT c_id_seq FROM customer WHERE c_id_seq = %s FOR UPDATE", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
            cursor.execute(
                """SELECT t.t_id, t.t_name, tc.c_id_seq FROM team t
                   INNER JOIN team_create tc ON tc.t_id = t.t_id WHERE t.t_id = %s FOR UPDATE""", (t_id,),
            )
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀입니다.")
            cursor.execute(
                "SELECT tr_seq, c_category FROM t_register WHERE c_id_seq = %s AND t_id = %s FOR UPDATE",
                (c_id_seq, t_id),
            )
            membership = cursor.fetchone()
            if membership is None:
                raise HTTPException(status_code=404, detail="해당 팀에 가입한 기록이 없습니다.")
            if (membership["c_category"] or "") not in ("", "가입", "가입일"):
                raise HTTPException(status_code=409, detail="이미 탈퇴했거나 가입 중인 상태가 아닙니다.")
            cursor.execute(
                """SELECT t_c_captain FROM team_captain_change WHERE t_id = %s
                   ORDER BY t_c_date DESC, t_c_seq DESC LIMIT 1 FOR UPDATE""", (t_id,),
            )
            captain = cursor.fetchone()
            if (captain["t_c_captain"] if captain else team["c_id_seq"]) == c_id_seq:
                raise HTTPException(status_code=409, detail="현재 팀장은 팀장 변경 또는 팀 폐지 후 탈퇴해 주세요.")
            cursor.execute(
                """UPDATE t_register SET c_category = '탈퇴', tr_date = NOW()
                   WHERE tr_seq = %s AND c_id_seq = %s AND t_id = %s""",
                (membership["tr_seq"], c_id_seq, t_id),
            )
            cursor.execute(
                "UPDATE customer SET c_team = '무소속' WHERE c_id_seq = %s AND c_team = %s",
                (c_id_seq, team["t_name"]),
            )
            cursor.execute(
                "SELECT tr_seq, tr_date, c_category FROM t_register WHERE c_id_seq = %s AND t_id = %s",
                (c_id_seq, t_id),
            )
            left = cursor.fetchone()
            if left is None:
                raise RuntimeError("탈퇴 기록을 확인하지 못했습니다.")
        connection.commit()
        return {"result": "OK", "t_id": t_id, "c_id_seq": c_id_seq, **left}
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 탈퇴 정보 충돌")
        raise HTTPException(status_code=409, detail="연결된 가입 정보를 확인해 주세요.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 탈퇴 처리 실패")
        raise HTTPException(status_code=500, detail="팀 탈퇴 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
