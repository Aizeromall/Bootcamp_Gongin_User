# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""ground 수용 인원을 기준으로 reservation 데이터를 생성하는 API입니다."""

import logging
import re
from datetime import date
from typing import Annotated

import pymysql
from fastapi import APIRouter, Body, HTTPException, status

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)
TIME_SLOTS = {
    "08:00": "10:00", "10:00": "12:00", "12:00": "14:00", "14:00": "16:00",
    "16:00": "18:00", "18:00": "20:00", "20:00": "22:00", "22:00": "24:00",
}
SPORT_BY_SEQUENCE = {1: "축구", 2: "농구", 3: "야구", 4: "배구"}
CUSTOMER_SEQUENCE_PATTERN = re.compile(r"^.+_0([1-4])$")


def sport_from_customer_id(customer_id_sequence: str) -> str:
    """c_id_seq 마지막 번호로 예약 가능한 종목을 확인합니다."""

    matched = CUSTOMER_SEQUENCE_PATTERN.fullmatch(customer_id_sequence)
    if matched is None:
        raise HTTPException(status_code=400, detail="c_id_seq는 아이디_01부터 아이디_04 형식이어야 합니다.")
    return SPORT_BY_SEQUENCE[int(matched.group(1))]


@router.post(
    "/reservation",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "c_id_seq 또는 예약 시작 시간 형식 오류"},
        404: {"description": "고객 또는 구장 코드가 존재하지 않음"},
        409: {"description": "중복 예약 또는 해당 시간의 구장 정원 초과"},
        422: {"description": "필수 요청값 검증 실패"},
        500: {"description": "DB 연결 또는 예약 처리 실패"},
    },
)
def create_reservation(
    c_id_seq: Annotated[str, Body(min_length=4, max_length=45, description="회원 아이디 + 종목 번호")],
    g_code: Annotated[str, Body(min_length=1, max_length=45, description="ground 테이블의 구장 코드")],
    r_date: Annotated[date, Body(description="예약 일자")],
    rs_time: Annotated[str, Body(description="예약 시작 시간: 08:00~22:00, 2시간 단위")],
) -> dict:
    """한 사용자와 구장을 연결한 예약을 생성하고 슬롯 마감 여부를 갱신합니다."""

    c_id_seq, g_code = c_id_seq.strip(), g_code.strip()
    if not c_id_seq or not g_code:
        raise HTTPException(status_code=400, detail="c_id_seq와 g_code는 비어 있을 수 없습니다.")
    if rs_time not in TIME_SLOTS:
        raise HTTPException(status_code=400, detail="rs_time은 08:00부터 22:00까지 2시간 단위로 선택해야 합니다.")

    sport_name, re_time = sport_from_customer_id(c_id_seq), TIME_SLOTS[rs_time]
    connection = None
    try:
        connection = connect()
        # 구장 row를 잠가 동시 예약이 수용 인원을 넘지 않게 합니다.
        with connection.cursor() as cursor:
            cursor.execute("SELECT g_code, g_num FROM ground WHERE g_code = %s FOR UPDATE", (g_code,))
            ground = cursor.fetchone()
            if ground is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장 코드입니다.")
            if not isinstance(ground["g_num"], int) or ground["g_num"] <= 0:
                raise HTTPException(status_code=409, detail="예약할 수 없는 구장입니다.")

            # c_id_seq 전체를 확인해 종목별 회원 데이터와 예약을 연결합니다.
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s LIMIT 1", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 같은 회원의 같은 구장·날짜·시간 중복 예약을 막습니다.
            # r_category = 1 : 취소(2)한 시간대는 다시 예약할 수 있게 예약 상태만 확인
            cursor.execute(
                """SELECT 1 FROM reservation
                    WHERE c_id_seq = %s AND g_code = %s AND r_date = %s AND rs_time = %s
                        AND r_category = 1
                    LIMIT 1 FOR UPDATE""",
                (c_id_seq, g_code, r_date, rs_time),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="이미 예약한 시간대입니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 동일 슬롯의 예약 수와 ground.g_num 수용 인원을 비교합니다.
            # r_category = 1 : 취소된 예약은 자리를 차지하지 않으므로 제외
            cursor.execute(
                """SELECT COUNT(*) AS reservation_count FROM reservation
                    WHERE g_code = %s AND r_date = %s AND rs_time = %s AND r_category = 1""",
                (g_code, r_date, rs_time),
            )
            reservation_count = cursor.fetchone()["reservation_count"]
            if reservation_count >= ground["g_num"]:
                raise HTTPException(status_code=409, detail="해당 시간대 예약이 마감되었습니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # r_check는 생성 시 false이며, 정원이 찬 경우 아래에서 true로 갱신합니다.
            # r_category는 1(예약)로 저장합니다.
            cursor.execute(
                """INSERT INTO reservation (g_code, c_id_seq, rs_time, re_time, r_date, r_check, r_category)
                   VALUES (%s, %s, %s, %s, %s, %s, %s)""",
                (g_code, c_id_seq, rs_time, re_time, r_date, False, 1),
            )
            # 예약 AI 값 r_seq는 결제 endpoint의 필수 입력값이므로 성공 응답에 포함합니다.
            r_seq = cursor.lastrowid
            if not isinstance(r_seq, int) or r_seq <= 0:
                raise RuntimeError("reservation.r_seq 자동 증가값을 가져오지 못했습니다.")
            is_full = reservation_count + 1 >= ground["g_num"]
            if is_full:
                # 중간 수정 작성자 - 신현진
                # 수정일 2026.10.26
                # 슬롯의 모든 예약을 true로 맞춰 조회 시 마감 상태를 일관되게 표시합니다.
                # r_category = 1 : 이미 취소된 예약은 마감 처리 대상에서 제외
                cursor.execute(
                    """UPDATE reservation SET r_check = %s
                        WHERE g_code = %s AND r_date = %s AND rs_time = %s AND r_category = 1""",
                    (True, g_code, r_date, rs_time),
                )

        connection.commit()
        return {
            "result": "OK", "r_seq": r_seq, "c_id_seq": c_id_seq, "sport": sport_name,
            "g_code": g_code, "r_date": r_date, "rs_time": rs_time,
            "re_time": re_time, "r_check": is_full,
            "remaining_capacity": ground["g_num"] - reservation_count - 1,
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()
        logger.exception("구장 예약 DB 처리 실패")
        raise HTTPException(status_code=500, detail="예약 처리 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("구장 예약 처리 실패")
        raise HTTPException(status_code=500, detail="예약 처리에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 수정자 : 신현진
