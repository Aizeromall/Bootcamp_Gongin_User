# 2026-10-27
# 작업자 : 양태건

"""팀 신청은 tr_state='대기', 승인 후에만 c_category='가입'과 회원 소속을 반영합니다.
tr_date는 현재 상태의 처리 시각이며 기존 빈 tr_state 가입 기록은 호환합니다.
(c_id_seq, t_id)별 최근 상태만 보관하며 게시글별 신청 이력은 저장하지 않습니다.
"""

import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query, status
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from ..database import connect

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 가입 상태는 가입으로 저장하며 기존 가입일 데이터는 조회 호환만 유지합니다.
router = APIRouter()
logger = logging.getLogger(__name__)


# 수정 일 : 2026-10-28 / 작업자 : 양태건
# 빈 상태는 기존 가입 데이터만 호환하며 대기·거절을 현재 팀원에서 제외합니다.
def active_registration(alias=""):
    prefix = alias + "." if alias else ""
    return (f"COALESCE({prefix}c_category, '') IN ('', '가입', '가입일') "
            f"AND COALESCE({prefix}tr_state, '') IN ('', '승인')")


def recruitment_team(cursor, bulletin_seq, lock=False):
    """모집글 작성자의 실제 가입 팀을 찾습니다. 게시글 상세 조회 수는 변경하지 않습니다."""
    cursor.execute(
        f"""SELECT t.t_id, t.t_name, tc.c_category, COALESCE(
            (SELECT cc.t_c_captain FROM team_captain_change cc WHERE cc.t_id = t.t_id
             ORDER BY cc.t_c_date DESC, cc.t_c_seq DESC LIMIT 1), tc.c_id_seq) AS captain_id
        FROM board_a_write b INNER JOIN t_register tr ON tr.c_id_seq = b.c_id_seq
        INNER JOIN team t ON t.t_id = tr.t_id INNER JOIN team_create tc ON tc.t_id = t.t_id
        WHERE b.bulletin_seq = %s AND b.comment_seq = 0 AND b.board_category = '팀원모집'
          AND b.comment_delete_state = 0 AND {active_registration('tr')}
        ORDER BY t.t_id LIMIT 1 {"FOR UPDATE" if lock else ""}""", (bulletin_seq,),
    )
    row = cursor.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="모집 게시글에 연결된 팀이 없습니다.")
    return row


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 날짜와 카테고리는 회원이 입력하지 않고 서버에서 가입·탈퇴 처리에 따라 정합니다.
class ApplyTeamRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True,
        json_schema_extra={"example": {"c_id_seq": "member_01"}},
    )
    c_id_seq: str = Field(min_length=1, max_length=50, description="가입할 종목별 회원 ID")
    bulletin_seq: Optional[int] = Field(default=None, gt=0, description="모집 게시글 번호")


# 가입 완료: 회원·팀을 잠그고 중복 소속을 확인한 뒤 가입 기록과 회원 소속을 함께 저장합니다.
@router.post("/apply/{t_id}", status_code=status.HTTP_201_CREATED, summary="팀 가입 신청 (팀장 승인 대기)")
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

            # 수정 일 : 2026-10-28 / 작업자 : 양태건
            # 모집글과 대상 팀의 연결을 서버에서 확인합니다. 일반 팀 화면 신청도 대기로 처리합니다.
            if payload.bulletin_seq is not None:
                linked = recruitment_team(cursor, payload.bulletin_seq, lock=True)
                if linked["t_id"] != t_id:
                    raise HTTPException(status_code=409, detail="모집 게시글의 팀이 일치하지 않습니다.")
            cursor.execute(
                f"SELECT t_id FROM t_register WHERE c_id_seq = %s AND {active_registration()} LIMIT 1 FOR UPDATE",
                (payload.c_id_seq,),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="이미 소속된 팀이 있습니다.")
            cursor.execute("SELECT tr_seq, tr_state, c_category FROM t_register WHERE c_id_seq = %s AND t_id = %s FOR UPDATE",
                           (payload.c_id_seq, t_id))
            previous = cursor.fetchone()
            if previous and previous.get("tr_state") == "대기":
                raise HTTPException(status_code=409, detail="이미 가입 승인 대기 중입니다.")
            if previous and (previous.get("tr_state") or "") not in ("", "승인", "거절", "탈퇴"):
                raise HTTPException(status_code=409, detail="기존 신청 상태를 확인해 주세요.")
            if previous and (previous.get("c_category") or "") not in ("", "가입", "가입일", "탈퇴", "탈퇴일"):
                raise HTTPException(status_code=409, detail="기존 가입 상태를 확인해 주세요.")
            if previous is None:
                cursor.execute("""INSERT INTO t_register (c_id_seq, t_id, tr_date, c_category, tr_state)
                                  VALUES (%s, %s, NOW(), '', '대기')""", (payload.c_id_seq, t_id))
            else:
                cursor.execute("""UPDATE t_register SET c_category = '', tr_state = '대기', tr_date = NOW()
                                  WHERE tr_seq = %s""", (previous["tr_seq"],))
            # 신청만으로 customer.c_team은 변경하지 않습니다.
            cursor.execute("SELECT tr_seq, tr_date, c_category, tr_state FROM t_register WHERE c_id_seq = %s AND t_id = %s",
                           (payload.c_id_seq, t_id))
            joined = cursor.fetchone()
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
                "SELECT tr_seq, c_category, tr_state FROM t_register WHERE c_id_seq = %s AND t_id = %s FOR UPDATE",
                (c_id_seq, t_id),
            )
            membership = cursor.fetchone()
            if membership is None:
                raise HTTPException(status_code=404, detail="해당 팀에 가입한 기록이 없습니다.")
            if (membership["c_category"] or "") not in ("", "가입", "가입일") or (membership.get("tr_state") or "") not in ("", "승인"):
                raise HTTPException(status_code=409, detail="이미 탈퇴했거나 가입 중인 상태가 아닙니다.")
            cursor.execute(
                """SELECT t_c_captain FROM team_captain_change WHERE t_id = %s
                   ORDER BY t_c_date DESC, t_c_seq DESC LIMIT 1 FOR UPDATE""", (t_id,),
            )
            captain = cursor.fetchone()
            if (captain["t_c_captain"] if captain else team["c_id_seq"]) == c_id_seq:
                raise HTTPException(status_code=409, detail="현재 팀장은 팀장 변경 또는 팀 폐지 후 탈퇴해 주세요.")
            cursor.execute(
                """UPDATE t_register SET c_category = '탈퇴', tr_state = '탈퇴', tr_date = NOW()
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


# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
