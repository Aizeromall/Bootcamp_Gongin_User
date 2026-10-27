# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 취소 후 행과 경기일을 유지하고 r_c_category에 사용자가 직접 작성한 사유를 저장합니다.
# 기존 1~3 코드로 저장된 취소 사유도 계속 조회할 수 있습니다.
# 디버그: 실제 DB에 없는 취소일 컬럼을 참조하지 않습니다.
# 작업자 : 양태건 / 최종 수정일 : 2026-10-26
import logging
from datetime import date

import pymysql
from fastapi import APIRouter, HTTPException, Query

from ..match.reservation_status import CANCEL_REASONS, RESERVATION_RENTAL, category_condition, is_canceled
from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

# 이 파일의 API들을 담는 라우터 (__init__.py에서 cancel_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 예약 구분 값 (reservation.r_category)
CATEGORY_CANCELED = 2   # 취소


# 회원 예약 1건 취소
# 예: DELETE /cancel/reservation/9002?c_id_seq=dummy1_01
@router.delete("/reservation/{r_seq}")
def delete_customer_reservation(
    r_seq: int,
    r_c_category: str = Query(min_length=1, max_length=50, description="사용자가 작성한 취소 사유 (최대 50자)"),
    c_id_seq: str = Query(min_length=4, max_length=50, description="취소를 요청한 회원 (본인 확인용)"),
):
    c_id_seq = c_id_seq.strip()  # 앞뒤 공백 제거
    # 디버그: 자유 입력 사유를 공백 제거 후 검증하고 그대로 저장합니다.
    # 작업자 : 양태건 / 최종 수정일 : 2026-10-26
    r_c_category = r_c_category.strip()
    if not r_c_category:
        raise HTTPException(status_code=422, detail="취소 사유를 입력해 주세요.")
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 1) 취소할 예약 조회
            # FOR UPDATE : 취소하는 동안 다른 요청이 이 예약을 바꾸지 못하게 잠금
            # reservation_category : 구장대여(2)는 이 API로 취소하지 않도록 구분값도 함께 조회 (2026.10.26 신현진)
            sql = """
                SELECT r_seq, c_id_seq, g_code, r_date, r_check, reservation_category, r_category, r_c_category
                FROM reservation
                WHERE r_seq = %s
                FOR UPDATE
            """
            cursor.execute(sql, (r_seq,))  # 값이 1개여도 튜플이라 (r_seq,) 처럼 쉼표 필요
            reservation = cursor.fetchone()  # 1건만 받음 (없으면 None)
            if reservation is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 예약 번호입니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 1-1) 구장대여(reservation_category = 2)는 구장대여 취소 API에서만 취소
            # (실력매칭 취소 규칙 r_check 등과 섞이지 않게 분리)
            # 값이 없으면 DB 기본값과 같은 1(실력매칭)로 봄
            if reservation.get("reservation_category", 1) == RESERVATION_RENTAL:
                raise HTTPException(
                    status_code=409,
                    detail="구장대여 예약은 /ground/reservation/{r_seq} 에서 취소해 주세요.",
                )

            # 2) 본인 예약인지 확인
            if reservation["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 예약만 취소할 수 있습니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 2-1) 이미 취소된 예약인지 확인 (행을 지우지 않으므로 같은 예약을 두 번 취소하는 것을 막음)
            if is_canceled(reservation):
                raise HTTPException(status_code=409, detail="이미 취소된 예약입니다.")

            # 3) 매치 성사 여부 확인 (r_check = 1 이면 인원이 다 차서 매치 확정)
            # DB에는 0/1로 저장되어 있어서 bool()로 true/false 변환
            if bool(reservation["r_check"]):
                raise HTTPException(status_code=409, detail="매치가 성사된 예약은 취소할 수 없습니다.")

            # 4) 지난 날짜 예약인지 확인
            if reservation["r_date"] < date.today():
                raise HTTPException(status_code=409, detail="이미 지난 예약은 취소할 수 없습니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 5) 결제 내역 삭제 (결제 전 예약이면 지울 게 없어서 rowcount = 0)
            # 예약 행은 남지만 결제는 환불 처리되므로 pay에서는 삭제
            cursor.execute("SELECT p_seq, p_amount FROM pay WHERE r_seq = %s", (r_seq,))
            payment = cursor.fetchone()  # 환불 금액 안내용 (없으면 None)
            cursor.execute("DELETE FROM pay WHERE r_seq = %s", (r_seq,))

            # 취소 사유를 남겨 취소 조회에 포함하고 중복 취소를 방지합니다.
            cursor.execute(
                f"""UPDATE reservation
                    SET r_category = %s, r_c_category = %s
                    WHERE r_seq = %s AND {category_condition(False)}""",
                ("2", r_c_category, r_seq),
            )
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="이미 취소된 예약입니다.")
        connection.commit()  # 결제 삭제 + 예약 취소 상태 변경을 한 번에 확정
        return {
            "result": "OK",
            "r_seq": r_seq,                                              # 취소된 예약번호
            "c_id_seq": c_id_seq,                                        # 취소한 회원
            "r_category": CATEGORY_CANCELED,                             # 변경된 카테고리 (2 취소)
            "r_date": reservation["r_date"],                             # 취소한 경기의 경기일
            "r_c_category": r_c_category,
            "cancel_reason": CANCEL_REASONS.get(r_c_category, r_c_category),
            "is_refunded": payment is not None,                          # 결제 취소(환불) 여부
            "refund_amount": payment["p_amount"] if payment else 0,      # 환불 금액
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 404/403/409는 되돌린 뒤 그대로 전달
        raise
    # 중간 수정 작성자 - 신현진
    # 수정일 2026.10.26
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()  # 에러 시 결제 삭제·취소 상태 변경을 모두 되돌림
        logger.exception("예약 취소 DB 처리 실패")
        raise HTTPException(status_code=500, detail="예약 취소 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("예약 취소 처리 실패")
        raise HTTPException(status_code=500, detail="예약 취소에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건 / 수정자 : 신현진 (구장대여 예약 취소 분리)
