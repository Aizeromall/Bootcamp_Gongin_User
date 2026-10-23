# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 회원 예약 취소 API (cancel_router에 묶여 실제 주소 앞에 /cancel 이 붙음)
#   DELETE /cancel/reservation/{r_seq}?c_id_seq=회원ID     회원이 예약한 구장 1건 취소
# 취소 조건
#   1) 본인 예약만 취소 가능
#   2) 매치가 성사되지 않은(인원이 다 차지 않은, r_check = 0) 예약만 취소 가능
#   3) 이미 지난 날짜의 예약은 취소 불가
# 결제가 되어 있으면 결제 내역(pay)도 같이 삭제 (환불 처리)
# 주소로 예약번호 + 회원ID만 받으므로 BaseModel class 없음
import logging
from datetime import date

import pymysql
from fastapi import APIRouter, HTTPException, Query

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

# 이 파일의 API들을 담는 라우터 (__init__.py에서 cancel_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)


# 회원 예약 1건 취소
# 예: DELETE /cancel/reservation/9002?c_id_seq=dummy1_01
@router.delete("/reservation/{r_seq}")
def delete_customer_reservation(
    r_seq: int,
    c_id_seq: str = Query(min_length=4, max_length=50, description="취소를 요청한 회원 (본인 확인용)"),
):
    c_id_seq = c_id_seq.strip()  # 앞뒤 공백 제거
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            # 1) 취소할 예약 조회
            # FOR UPDATE : 취소하는 동안 다른 요청이 이 예약을 바꾸지 못하게 잠금
            sql = """
                SELECT r_seq, c_id_seq, g_code, r_date, r_check
                FROM reservation
                WHERE r_seq = %s
                FOR UPDATE
            """
            cursor.execute(sql, (r_seq,))  # 값이 1개여도 튜플이라 (r_seq,) 처럼 쉼표 필요
            reservation = cursor.fetchone()  # 1건만 받음 (없으면 None)
            if reservation is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 예약 번호입니다.")

            # 2) 본인 예약인지 확인
            if reservation["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 예약만 취소할 수 있습니다.")

            # 3) 매치 성사 여부 확인 (r_check = 1 이면 인원이 다 차서 매치 확정)
            # DB에는 0/1로 저장되어 있어서 bool()로 true/false 변환
            if bool(reservation["r_check"]):
                raise HTTPException(status_code=409, detail="매치가 성사된 예약은 취소할 수 없습니다.")

            # 4) 지난 날짜 예약인지 확인
            if reservation["r_date"] < date.today():
                raise HTTPException(status_code=409, detail="이미 지난 예약은 취소할 수 없습니다.")

            # 5) 결제 내역 삭제 (결제 전 예약이면 지울 게 없어서 rowcount = 0)
            # pay.r_seq가 reservation을 참조(FK)하므로 결제를 먼저 지워야 예약 삭제 가능
            cursor.execute("SELECT p_seq, p_amount FROM pay WHERE r_seq = %s", (r_seq,))
            payment = cursor.fetchone()  # 환불 금액 안내용 (없으면 None)
            cursor.execute("DELETE FROM pay WHERE r_seq = %s", (r_seq,))

            # 6) 예약 삭제
            cursor.execute("DELETE FROM reservation WHERE r_seq = %s", (r_seq,))
            # rowcount: 삭제된 행 수 → 0이면 그 사이에 이미 삭제된 예약
            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="취소할 예약이 없습니다.")
        connection.commit()  # 결제 삭제 + 예약 삭제를 한 번에 확정
        return {
            "result": "OK",
            "r_seq": r_seq,                                              # 취소된 예약번호
            "c_id_seq": c_id_seq,                                        # 취소한 회원
            "is_refunded": payment is not None,                          # 결제 취소(환불) 여부
            "refund_amount": payment["p_amount"] if payment else 0,      # 환불 금액
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 404/403/409는 되돌린 뒤 그대로 전달
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()  # 에러 시 삭제 취소
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

# 최종 수정 일 : 2026-10-23
