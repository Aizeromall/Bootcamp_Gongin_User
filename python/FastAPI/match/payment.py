# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""reservation 완료 직후 r_seq를 기준으로 payment 데이터를 생성하는 API입니다."""

import logging
import secrets
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Annotated, Literal

import pymysql
from fastapi import APIRouter, Body, HTTPException, status

from ..database import connect
from .reservation_status import RESERVATION_RENTAL, is_canceled

router = APIRouter()
logger = logging.getLogger(__name__)

# p_method는 숫자가 아닌 varchar 문자열로 저장
PaymentMethod = Literal["카드 결제", "카카오페이", "네이버페이", "토스 페이", "휴대폰 결제", "애플 페이"]


def calculate_payment_amount(g_price: object, g_num: object) -> int:
    """구장 총 이용금액을 수용 인원으로 나눈 뒤 원 단위 반올림한 금액을 반환합니다."""

    try:
        price = Decimal(str(g_price))
        capacity = Decimal(str(g_num))
        if price < 0 or capacity <= 0:
            raise ValueError
        # pay.p_amount가 INT이므로 0.5원 이상은 올림하는 원 단위 반올림을 적용합니다.
        return int((price / capacity).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (InvalidOperation, ValueError):
        raise HTTPException(status_code=409, detail="결제할 수 없는 구장 금액 또는 수용 인원입니다.")


@router.post(
    "/payment",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "c_id_seq가 비어 있음"},
        403: {"description": "예약 회원과 결제 요청 회원이 일치하지 않음"},
        404: {"description": "r_seq에 해당하는 예약 또는 구장 정보가 없음"},
        # 중간 수정 작성자 - 신현진
        # 수정일 2026.10.26
        409: {"description": "이미 결제된 예약, 취소된 예약 또는 유효하지 않은 구장 금액"},
        422: {"description": "r_seq 또는 p_method 요청값 검증 실패"},
        500: {"description": "DB 연결 또는 결제 처리 실패"},
    },
)
def create_payment(
    r_seq: Annotated[int, Body(gt=0, description="결제할 reservation 테이블의 예약 번호")],
    c_id_seq: Annotated[str, Body(min_length=4, max_length=45, description="결제를 요청한 회원의 customer FK")],
    p_method: Annotated[PaymentMethod, Body(description="카드 결제 등 선택한 결제 수단 문자열")],
) -> dict:
    """예약일·구장 가격을 사용해 단일 결제 데이터를 생성합니다.

    프런트엔드는 예약 성공 응답의 r_seq를 받은 직후 이 endpoint를 호출합니다.
    """

    c_id_seq = c_id_seq.strip()
    if not c_id_seq:
        raise HTTPException(status_code=400, detail="c_id_seq는 비어 있을 수 없습니다.")

    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # reservation과 ground를 함께 잠가 결제 도중 가격·예약 정보가 바뀌지 않게 합니다.
            # reservation_category : 구장대여(2)는 결제 금액이 달라서 구분값도 함께 조회 (2026.10.26 신현진)
            cursor.execute(
                """SELECT r.r_seq, r.c_id_seq, r.r_date, r.g_code, r.reservation_category,
                        r.r_category, r.r_c_category, g.g_price, g.g_num
                    FROM reservation AS r
                    INNER JOIN ground AS g ON g.g_code = r.g_code
                    WHERE r.r_seq = %s FOR UPDATE""",
                (r_seq,),
            )
            reservation = cursor.fetchone()
            if reservation is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 예약 번호입니다.")
            # 요청 회원과 reservation FK 회원이 일치할 때만 결제를 진행합니다.
            if reservation["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 예약에 대해서만 결제할 수 있습니다.")
            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 디버그: 취소 사유가 등록된 예약도 재결제를 차단합니다.
            # 작업자 : 양태건 / 최종 수정일 : 2026-10-26
            if is_canceled(reservation):
                raise HTTPException(status_code=409, detail="취소된 예약은 결제할 수 없습니다.")

            # 검증된 reservation FK를 pay에도 저장하고, 예약당 한 번만 결제되게 합니다.
            cursor.execute(
                "SELECT p_seq FROM pay WHERE r_seq = %s LIMIT 1 FOR UPDATE",
                (r_seq,),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="해당 회원은 이미 이 예약을 결제했습니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 결제 금액
            #   실력매칭(1) : 구장 이용금액 ÷ 수용인원 (1인 금액)
            #   구장대여(2) : 시간대 전체를 빌리므로 구장 이용금액 전체 (수용인원 1로 나눔)
            #   값이 없으면 DB 기본값과 같은 1(실력매칭)로 봄
            if reservation.get("reservation_category", 1) == RESERVATION_RENTAL:
                p_amount = calculate_payment_amount(reservation["g_price"], 1)
            else:
                p_amount = calculate_payment_amount(reservation["g_price"], reservation["g_num"])
            # p_seq는 AI이므로, 임시 고유 번호로 INSERT한 뒤 lastrowid로 최종 p_num을 만듭니다.
            pending_p_num = f"pending_{secrets.token_hex(8)}"
            cursor.execute(
                """INSERT INTO pay (p_num, r_seq, c_id_seq, p_amount, p_date, p_method)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (pending_p_num, r_seq, reservation["c_id_seq"], p_amount, reservation["r_date"], p_method),
            )
            p_seq = cursor.lastrowid
            if not isinstance(p_seq, int) or p_seq <= 0:
                raise RuntimeError("pay.p_seq 자동 증가값을 가져오지 못했습니다.")

            # 예: g_code=2, p_seq=1이면 p_num=2_1로 확정합니다.
            p_num = f"{reservation['g_code']}_{p_seq}"
            cursor.execute("UPDATE pay SET p_num = %s WHERE p_seq = %s", (p_num, p_seq))

        connection.commit()
        return {
            "result": "OK",
            "p_seq": p_seq,
            "p_num": p_num,
            "r_seq": r_seq,
            "c_id_seq": reservation["c_id_seq"],
            "p_amount": str(p_amount),
            "p_date": reservation["r_date"],
            "p_method": p_method,
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()
        logger.exception("결제 DB 처리 실패")
        raise HTTPException(status_code=500, detail="결제 처리 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("결제 처리 실패")
        raise HTTPException(status_code=500, detail="결제 처리에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건 / 수정자 : 신현진 (구장대여 결제 금액)
