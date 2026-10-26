# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 구장 결제내역 조회 API (match_router에 묶여 실제 주소 앞에 /match 가 붙음)
#   GET /match/payment/customer/{c_id_seq}       회원별 결제 내역 (예약 + 구장 정보 포함)
#   GET /match/payment/reservation/{r_seq}       예약 1건의 결제 내역 (결제 여부 확인용)
#   GET /match/payment/{p_seq}                   결제 1건 상세
# 조회만 하고 받는 값(body)이 없어서 BaseModel class 없음
import logging

import pymysql
from fastapi import APIRouter, HTTPException

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
from .reservation_search import RESERVATION_MANAGER_JOIN, format_time  # 시간 값 → "08:00" 형식으로 통일

# 이 파일의 API들을 담는 라우터 (__init__.py에서 match_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# DB에서 받은 결제 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄
def payment_to_dict(row: dict) -> dict:
    return {
        "p_seq": row["p_seq"],                   # 결제번호 (AI)
        "p_num": row["p_num"],                   # 결제코드 (구장코드_결제번호, 예: 2_1)
        "r_seq": row["r_seq"],                   # 예약번호
        "c_id_seq": row["c_id_seq"],             # 결제한 회원
        "p_amount": row["p_amount"],             # 결제금액 (1인 금액)
        "p_date": row["p_date"],                 # 결제일 (예약일과 동일하게 저장됨)
        "p_method": row["p_method"],             # 결제수단 (카드 결제, 카카오페이 등)
        "g_code": row["g_code"],                 # 구장코드 (reservation JOIN)
        "g_name": row["g_name"],                 # 구장명 (ground JOIN)
        "r_date": row["r_date"],                 # 예약일 (reservation JOIN)
        "rs_time": format_time(row["rs_time"]),  # 예약 시작 시간
        "re_time": format_time(row["re_time"]),  # 예약 종료 시간
        "m_id": row["m_id"],                     # 예약에 배정된 경기매니저 ID (reservation JOIN, 없으면 None)
        "m_name": row["m_name"],                 # 경기매니저 이름 (match_manager JOIN)
    }


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 결제 조회에서 공통으로 쓰는 SELECT
# p / r / g / m 은 테이블 별칭 (pay / reservation / ground / match_manager)
# pay.r_seq = reservation.r_seq 로 어떤 예약의 결제인지 찾고,
# reservation.g_code = ground.g_code 로 구장 이름을 가져옴
# 매니저는 assign의 경기 요일·시간으로 조회하며 미배정 결제도 표시합니다.
# 디버그: 없는 reservation.m_id 대신 실제 배정표 조인을 재사용합니다.
# 작업자 : 양태건 / 최종 수정일 : 2026-10-26
RESERVATION_JOIN = f"""
    SELECT p.p_seq, p.p_num, p.r_seq, p.c_id_seq, p.p_amount, p.p_date, p.p_method,
        r.g_code, g.g_name, r.r_date, r.rs_time, r.re_time, m.m_id, m.m_name
    FROM pay AS p
    INNER JOIN reservation AS r ON r.r_seq = p.r_seq
    INNER JOIN ground AS g ON g.g_code = r.g_code
    {RESERVATION_MANAGER_JOIN}
"""


# 회원별 결제 내역 조회
# 예: /match/payment/customer/hong_01
@router.get("/payment/customer/{c_id_seq}")
def select_payments_by_customer(c_id_seq: str):
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            sql = RESERVATION_JOIN + """
                WHERE p.c_id_seq = %s
                ORDER BY p.p_date DESC, p.p_seq DESC
            """
            cursor.execute(sql, (c_id_seq,))  # %s 자리에 값이 들어감 (SQL 인젝션 방지)
            rows = cursor.fetchall()  # 결과 전체를 dict 목록으로 받음
        # 결제 내역이 하나도 없으면 빈 리스트 [] 가 나감 (에러 아님)
        return {"results": [payment_to_dict(row) for row in rows]}
    except pymysql.MySQLError:
        logger.exception("회원 결제 내역 DB 조회 실패")
        raise HTTPException(status_code=500, detail="결제 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("회원 결제 내역 조회 실패")
        raise HTTPException(status_code=500, detail="결제 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 예약 1건의 결제 내역 조회
# 예약당 결제는 1번만 가능하므로(payment.py에서 막음) 결과는 0건 또는 1건
# 결제 전이면 404 → 앱에서 "결제하기" 버튼을 보여주는 용도로 사용
# 예: /match/payment/reservation/15
@router.get("/payment/reservation/{r_seq}")
def select_payment_by_reservation(r_seq: int):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = RESERVATION_JOIN + " WHERE p.r_seq = %s LIMIT 1"
            cursor.execute(sql, (r_seq,))  # 값이 1개여도 튜플이라 (r_seq,) 처럼 쉼표 필요
            row = cursor.fetchone()  # 1건만 받음 (없으면 None)
        if row is None:
            raise HTTPException(status_code=404, detail="해당 예약의 결제 내역이 없습니다.")
        return payment_to_dict(row)
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("예약 결제 내역 DB 조회 실패")
        raise HTTPException(status_code=500, detail="결제 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("예약 결제 내역 조회 실패")
        raise HTTPException(status_code=500, detail="결제 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 결제 1건 상세 조회
# 주의: "/payment/customer/..", "/payment/reservation/.." 보다 아래에 있어야
#       "customer", "reservation"이 p_seq로 잘못 인식되지 않음
@router.get("/payment/{p_seq}")
def select_payment(p_seq: int):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = RESERVATION_JOIN + " WHERE p.p_seq = %s"
            cursor.execute(sql, (p_seq,))
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="존재하지 않는 결제 번호입니다.")
        return payment_to_dict(row)
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("결제 상세 DB 조회 실패")
        raise HTTPException(status_code=500, detail="결제 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("결제 상세 조회 실패")
        raise HTTPException(status_code=500, detail="결제 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
