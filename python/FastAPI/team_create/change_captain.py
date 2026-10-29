# 작업자 : 신현진
# 최초 작업 일 : 2026-10-28

# 팀장 변경 API (team.py의 router에 묶여 실제 주소 앞에 /team 이 붙음)
#   POST /team/captain/{t_id}        현재 팀장(A)이 같은 팀 팀원(B)에게 팀장을 넘김
#
# [처리 내용] 하나의 트랜잭션으로 함께 처리
#   1) team_captain_change에 새 팀장 B 저장 (팀장 변경 이력은 지우지 않고 계속 쌓임)
#   2) A의 진행 중인 구장대여(reservation_category = 2, 취소 안 됨, 오늘 이후)의 reservation.c_id_seq → B
#      → 팀 경기 매칭(team_match_connect.py)의 대여 조회·취소·매칭 수락을 B가 이어서 할 수 있음
#   3) 그 대여로 쓴 [매칭신청] 게시글(board_a_write의 게시글 행, comment_seq = 0)의 작성자 → B
#      → 매칭 신청 확인·수락·거절도 B가 이어서 처리
#   4) 결제(pay.c_id_seq)는 실제로 돈을 낸 A 그대로 둠 (취소 시 환불이 A에게 가도록)
#   이미 달린 신청·수락 댓글(댓글 행)은 작성 당시 기록이라 바꾸지 않음
#
# [팀장 확인] team_create/delete.py · apply_team.py와 같은 규칙
#   team_captain_change의 가장 최근 팀장, 변경 기록이 없으면 team_create의 개설자
import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict, Field

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
# 구장대여·취소 여부 조건과 [매칭신청] 게시글 규칙은 기존 코드와 같은 값을 사용
from ..match.reservation_status import RESERVATION_RENTAL, category_condition, reservation_type_condition
from ..team_match.team_match_connect import BOARD_CATEGORY_TEAM_MATCH, POST_COMMENT_SEQ, POST_RESERVATION_MARK

# 이 파일의 API들을 담는 라우터 (team.py에서 팀 router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# 현재 팀원으로 보는 가입 상태 (apply_team.py와 같은 기준, 빈 값·가입일은 기존 데이터 호환)
ACTIVE_MEMBER_CATEGORIES = ("", "가입", "가입일")


# 팀장 변경 요청 값
# c_id_seq : 요청한 회원 (현재 팀장 A, 본인 확인용)
# new_captain : 새 팀장이 될 같은 팀 팀원 B
class ChangeCaptainRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", str_strip_whitespace=True,
        json_schema_extra={"example": {"c_id_seq": "captain_01", "new_captain": "member_01"}},
    )
    c_id_seq: str = Field(min_length=1, max_length=50, description="현재 팀장 회원 ID (본인 확인용)")
    new_captain: str = Field(min_length=1, max_length=50, description="새 팀장이 될 팀원 회원 ID")


# 팀장 변경 (현재 팀장 → 같은 팀 팀원)
# 예: POST /team/captain/3   body {"c_id_seq": "captain_01", "new_captain": "member_01"}
@router.post(
    "/captain/{t_id}",
    status_code=status.HTTP_201_CREATED,
    summary="팀장 변경 (진행 중인 구장대여·매칭신청 게시글도 새 팀장에게 이전)",
    responses={
        403: {"description": "현재 팀장이 아님"},
        404: {"description": "팀 또는 개설 기록이 없음"},
        409: {"description": "폐지된 팀 / 본인에게 변경 / 새 팀장이 현재 팀원이 아님"},
        500: {"description": "팀장 변경 처리 실패"},
    },
)
def change_captain(payload: ChangeCaptainRequest, t_id: int = Path(gt=0, description="팀 ID")):
    captain_id, new_captain = payload.c_id_seq, payload.new_captain
    if captain_id == new_captain:
        raise HTTPException(status_code=409, detail="현재 팀장에게는 팀장을 넘길 수 없습니다.")
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            # 1) 팀 + 개설 기록 조회
            # FOR UPDATE : 팀 폐지·탈퇴·다른 팀장 변경과 동시에 처리되지 않게 팀 행 잠금
            cursor.execute(
                """SELECT t.t_id, t.t_name, tc.c_id_seq, tc.c_category
                   FROM team t INNER JOIN team_create tc ON tc.t_id = t.t_id
                   WHERE t.t_id = %s FOR UPDATE""",
                (t_id,),
            )
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀 또는 개설 기록입니다.")
            if team["c_category"] == "폐지일":
                raise HTTPException(status_code=409, detail="폐지된 팀은 팀장을 변경할 수 없습니다.")

            # 2) 요청한 회원이 현재 팀장인지 확인 (최근 변경 기록 → 없으면 개설자)
            cursor.execute(
                """SELECT t_c_captain FROM team_captain_change WHERE t_id = %s
                   ORDER BY t_c_date DESC, t_c_seq DESC LIMIT 1 FOR UPDATE""",
                (t_id,),
            )
            captain = cursor.fetchone()
            current_captain = captain["t_c_captain"] if captain else team["c_id_seq"]
            if current_captain != captain_id:
                raise HTTPException(status_code=403, detail="현재 팀장만 팀장을 변경할 수 있습니다.")

            # 3) 새 팀장이 이 팀의 현재 팀원인지 확인 (탈퇴한 회원은 불가)
            cursor.execute(
                """SELECT c_category, tr_state FROM t_register WHERE c_id_seq = %s AND t_id = %s FOR UPDATE""",
                (new_captain, t_id),
            )
            member = cursor.fetchone()
            if member is None or (member["c_category"] or "") not in ACTIVE_MEMBER_CATEGORIES or (member.get("tr_state") or "") not in ("", "승인"):
                raise HTTPException(status_code=409, detail="새 팀장은 이 팀의 현재 팀원이어야 합니다.")

            # 4) 팀장 변경 이력 저장 (새 팀장 B)
            cursor.execute(
                """INSERT INTO team_captain_change (t_id, t_c_captain, t_c_date)
                   VALUES (%s, %s, NOW())""",
                (t_id, new_captain),
            )

            # 5) A의 진행 중인 구장대여 조회 (구장대여 · 취소 안 됨 · 오늘 이후)
            # FOR UPDATE : 이전하는 동안 대여 취소·매칭 수락이 끼어들지 않게 잠금
            cursor.execute(
                f"""SELECT r_seq FROM reservation
                    WHERE c_id_seq = %s AND {reservation_type_condition(RESERVATION_RENTAL)}
                        AND {category_condition(False)} AND r_date >= CURDATE()
                    FOR UPDATE""",
                (captain_id,),
            )
            rental_seqs = [row["r_seq"] for row in cursor.fetchall()]

            moved_posts = 0
            for r_seq in rental_seqs:
                # 6) 구장대여 예약자 → B (결제 pay.c_id_seq는 A 그대로 → 환불은 A에게)
                cursor.execute("UPDATE reservation SET c_id_seq = %s WHERE r_seq = %s", (new_captain, r_seq))

                # 7) 그 대여로 쓴 [매칭신청] 게시글(게시글 행) 작성자 → B
                #    게시글 내용 첫 줄의 [예약번호:r_seq]로 연결된 게시글만 이전
                cursor.execute(
                    """UPDATE board_a_write SET c_id_seq = %s
                        WHERE comment_seq = %s AND c_id_seq = %s AND board_category = %s
                            AND board_content LIKE %s""",
                    (new_captain, POST_COMMENT_SEQ, captain_id, BOARD_CATEGORY_TEAM_MATCH,
                     POST_RESERVATION_MARK.format(r_seq=r_seq) + "%"),
                )
                moved_posts += cursor.rowcount
        connection.commit()  # 팀장 변경 + 대여·게시글 이전을 한 번에 확정
        return {
            "result": "OK",
            "t_id": t_id,                        # 팀 ID
            "t_name": team["t_name"],            # 팀명
            "previous_captain": captain_id,      # 이전 팀장 (A)
            "new_captain": new_captain,          # 새 팀장 (B)
            "moved_rentals": rental_seqs,        # B에게 넘어간 구장대여 예약번호 목록
            "moved_posts": moved_posts,          # B에게 넘어간 [매칭신청] 게시글 수
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 403/404/409는 되돌린 뒤 그대로 전달
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀장 변경 정보 충돌")
        raise HTTPException(status_code=409, detail="회원 또는 팀 정보를 확인해 주세요.")
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()  # 에러 시 팀장 변경·대여·게시글 이전을 모두 되돌림
        logger.exception("팀장 변경 DB 처리 실패")
        raise HTTPException(status_code=500, detail="팀장 변경 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀장 변경 처리 실패")
        raise HTTPException(status_code=500, detail="팀장 변경에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 수정 일 : 2026-10-28 / 작업자 : 양태건
# 승인된 실제 팀원에게만 위임하며 기존 빈 상태는 호환합니다.
# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
