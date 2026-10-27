# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 구장 예약내역 조회 API (match_router에 묶여 실제 주소 앞에 /match 가 붙음)
#   GET /match/reservation/customer/{c_id_seq}           회원별 예약 내역 (구장 정보 + 결제 여부 포함)
#       ?r_category=1 (기본값) 예약 내역 / ?r_category=2 취소 내역
#   GET /match/reservation/ground/{g_code}?r_date=날짜   구장의 날짜별 시간대 예약 현황 (남은 자리)
#   GET /match/reservation/{r_seq}                       예약 1건 상세 (예약/취소 상관없이 조회)
# 조회만 하고 받는 값(body)이 없어서 BaseModel class 없음
# 매니저 정보는 실제 assign 배정표에서 조회합니다.
#
# reservation.r_category : 예약 구분
#   빈 취소 사유 = 예약, r_c_category가 등록되면 취소입니다.
#   r_c_category: 1 정원 미달 / 2 우천·기상 악화 / 3 노쇼 및 환불
#   취소해도 예약 행과 원래 경기일을 보존합니다.
import logging
from datetime import date, timedelta

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
import pymysql
from fastapi import APIRouter, HTTPException, Query

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
# 예약 구분(reservation_category) 1 실력매칭 / 2 구장대여 조건을 함께 사용 (2026.10.26 신현진)
from .reservation_status import (
    RESERVATION_MATCH,
    RESERVATION_RENTAL,
    cancel_reason,
    category_condition,
    is_canceled,
    reservation_type_condition,
)
from .reservation import ASSIGN_DAY_CONDITION, TIME_SLOTS  # 예약 시간대 목록 (08:00~22:00, 2시간 단위)

# 이 파일의 API들을 담는 라우터 (__init__.py에서 match_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 예약 구분 값 (DB의 r_category 숫자에 이름을 붙여서 코드에서 1, 2를 직접 쓰지 않게 함)
CATEGORY_RESERVED = 1   # 예약
CATEGORY_CANCELED = 2   # 취소


# 시간 값 → "08:00" 형식 문자열로 통일
# DB 컬럼이 TIME 타입이면 pymysql이 timedelta로 주기 때문에 그대로 보내면 초(숫자)로 바뀜
# 문자열(varchar)로 저장된 경우에는 앞 5글자(HH:MM)만 사용
def format_time(value) -> str:
    if isinstance(value, timedelta):
        total_minutes = int(value.total_seconds()) // 60
        return f"{total_minutes // 60:02d}:{total_minutes % 60:02d}"
    return str(value)[:5]


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# DB에서 받은 예약 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄
def reservation_to_dict(row: dict) -> dict:
    return {
        "r_seq": row["r_seq"],                   # 예약번호
        "c_id_seq": row["c_id_seq"],             # 예약한 회원 (회원ID + 종목번호)
        "g_code": row["g_code"],                 # 구장코드
        "g_name": row["g_name"],                 # 구장명 (ground JOIN)
        "g_address": row["g_address"],           # 구장 주소 (ground JOIN)
        "m_id": row["m_id"],                     # 배정 경기매니저 ID (배정이 없으면 None)
        "m_name": row["m_name"],                 # 경기매니저 이름 (match_manager JOIN)
        "r_date": row["r_date"],                 # 경기일 (예약한 날짜, 취소해도 그대로 유지)
        # 예약 구분 (1 실력매칭 / 2 구장대여) - 값이 없으면 DB 기본값과 같은 1(실력매칭)  # 2026.10.26 신현진
        "reservation_category": row.get("reservation_category", RESERVATION_MATCH),
        "r_category": CATEGORY_CANCELED if is_canceled(row) else CATEGORY_RESERVED,         # 카테고리 (1 예약 / 2 취소)
        "is_canceled": is_canceled(row),  # 취소 여부 (앱에서 true/false로 바로 사용)
        "r_c_category": row["r_c_category"],
        "cancel_reason": cancel_reason(row),   # 취소 사유 표시명 (예약 상태면 None)
        "rs_time": format_time(row["rs_time"]),  # 예약 시작 시간
        "re_time": format_time(row["re_time"]),  # 예약 종료 시간
        "r_check": bool(row["r_check"]),         # 해당 시간대 마감 여부 (DB 0/1 → false/true)
        "p_seq": row["p_seq"],                   # 결제번호 (결제 전이거나 취소로 환불되면 None)
        "is_paid": row["p_seq"] is not None,     # 결제 완료 여부
    }


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 예약 조회에서 공통으로 쓰는 SELECT
# r / g / m / p 는 테이블 별칭 (reservation / ground / match_manager / pay)
# INNER JOIN ground : 예약한 구장의 이름·주소를 함께 가져옴
# LEFT JOIN match_manager : 배정 매니저 이름을 가져옴 (매니저가 없는 예약도 빠지지 않고 None)
# LEFT JOIN pay : 결제 전인 예약도 빠지지 않고 나옴 (결제 값은 None)
# 디버그: reservation에 없는 m_id 대신 실제 배정 요일·시간으로 매니저를 연결합니다.
# 작업자 : 양태건 / 최종 수정일 : 2026-10-26
RESERVATION_MANAGER_JOIN = f"""
    LEFT JOIN match_manager AS m ON m.m_id = (
        SELECT a.m_id FROM assign AS a
        INNER JOIN match_manager AS assigned ON assigned.m_id = a.m_id
        WHERE a.g_code = r.g_code AND {ASSIGN_DAY_CONDITION.replace('%s', 'r.r_date')}
            AND TIME_TO_SEC(r.rs_time) >= TIME_TO_SEC(TRIM(SUBSTRING_INDEX(a.a_time, '~', 1)))
            AND TIME_TO_SEC(r.re_time) <= TIME_TO_SEC(TRIM(SUBSTRING_INDEX(a.a_time, '~', -1)))
        ORDER BY a.assign_seq DESC LIMIT 1
    )
"""
# reservation_category : 예약 구분 (1 실력매칭 / 2 구장대여) 컬럼 추가 (2026.10.26 신현진)
RESERVATION_SELECT = f"""
    SELECT r.r_seq, r.c_id_seq, r.g_code, g.g_name, g.g_address, m.m_id, m.m_name,
        r.r_date, r.rs_time, r.re_time, r.r_check, r.reservation_category, r.r_category, r.r_c_category, p.p_seq
    FROM reservation AS r
    INNER JOIN ground AS g ON g.g_code = r.g_code
    {RESERVATION_MANAGER_JOIN}
    LEFT JOIN pay AS p ON p.r_seq = r.r_seq
"""


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 회원별 예약 내역 / 취소 내역 조회
# r_category를 안 보내면 1(예약)로 조회 → 기존 앱 화면(내역 > 예약)은 그대로 동작
# 예: /match/reservation/customer/hong_01                 예약 내역
#     /match/reservation/customer/hong_01?r_category=2    취소 내역
@router.get("/reservation/customer/{c_id_seq}")
def select_reservations_by_customer(
    c_id_seq: str,
    # ge=1, le=2 : 1~2 밖의 값이 오면 FastAPI가 자동으로 422 에러 처리
    r_category: int = Query(CATEGORY_RESERVED, ge=1, le=2, description="1 예약 내역 / 2 취소 내역"),
):
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            # 취소 시각 컬럼이 없으므로 경기일·예약번호 기준으로 정렬합니다.
            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # reservation_category = 1 : 실력매칭 내역만 조회 (구장대여 내역은 /ground/reservation/customer/... 에서 조회)
            sql = RESERVATION_SELECT + f"""
                WHERE r.c_id_seq = %s AND {category_condition(r_category == CATEGORY_CANCELED, 'r')}
                    AND {reservation_type_condition(RESERVATION_MATCH, 'r')}
                ORDER BY r.r_date DESC, r.rs_time DESC, r.r_seq DESC
            """
            cursor.execute(sql, (c_id_seq,))
            rows = cursor.fetchall()  # 결과 전체를 dict 목록으로 받음
        # 예약이 하나도 없으면 빈 리스트 [] 가 나감 (에러 아님)
        return {"results": [reservation_to_dict(row) for row in rows]}
    except pymysql.MySQLError:
        logger.exception("회원 예약 내역 DB 조회 실패")
        raise HTTPException(status_code=500, detail="예약 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("회원 예약 내역 조회 실패")
        raise HTTPException(status_code=500, detail="예약 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 구장의 날짜별 시간대 예약 현황 조회 (예약 화면에서 시간 선택용)
# 시간대마다 예약 수를 세서 ground.g_num(수용인원)과 비교해 남은 자리를 계산
# 예: /match/reservation/ground/G001?r_date=2026-10-25
@router.get("/reservation/ground/{g_code}")
def select_reservation_status(g_code: str, r_date: date):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 1) 구장이 있는지 + 수용인원 확인
            cursor.execute("SELECT g_code, g_name, g_num FROM ground WHERE g_code = %s", (g_code,))
            ground = cursor.fetchone()  # 1건만 받음 (없으면 None)
            if ground is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장 코드입니다.")

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 2) 해당 날짜의 시간대별 예약 수
            # GROUP BY rs_time : 같은 시작 시간끼리 묶어서 COUNT(*)로 개수를 셈
            # 취소 사유가 있는 예약은 정원에서 제외하고 기존 빈 상태 예약도 포함
            # reservation_category = 1 : 실력매칭 예약만 정원으로 셈
            sql = f"""
                SELECT rs_time, COUNT(*) AS reservation_count
                FROM reservation
                WHERE g_code = %s AND r_date = %s
                    AND {category_condition(False)} AND {reservation_type_condition(RESERVATION_MATCH)}
                GROUP BY rs_time
            """
            cursor.execute(sql, (g_code, r_date))
            rows = cursor.fetchall()

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.26
            # 3) 구장대여(reservation_category = 2)로 빌려진 시간대 (취소 사유가 없는 대여만)
            # 대여된 시간대는 실력매칭 예약을 받을 수 없으므로 마감으로 표시
            cursor.execute(
                f"""SELECT rs_time FROM reservation
                    WHERE g_code = %s AND r_date = %s
                        AND {category_condition(False)} AND {reservation_type_condition(RESERVATION_RENTAL)}""",
                (g_code, r_date),
            )
            rented_times = {format_time(row["rs_time"]) for row in cursor.fetchall()}

        # 중간 수정 작성자 - 신현진
        # 수정일 2026.10.26
        # {시작시간: 예약 수} 형태로 정리 (예약이 없는 시간대는 dict에 없음)
        counts = {format_time(row["rs_time"]): row["reservation_count"] for row in rows}
        capacity = ground["g_num"]  # 수용인원
        # TIME_SLOTS 전체를 돌면서 예약 없는 시간대도 0건으로 채워서 보냄
        # 구장 대여된 시간대는 남은 자리 0 / 마감(true)으로 보냄
        slots = []
        for rs_time, re_time in TIME_SLOTS.items():
            count = counts.get(rs_time, 0)
            is_rented = rs_time in rented_times
            slots.append({
                "rs_time": rs_time,                              # 시작 시간
                "re_time": re_time,                              # 종료 시간
                "reservation_count": count,                      # 현재 예약 수
                "remaining_capacity": 0 if is_rented else max(capacity - count, 0),  # 남은 자리
                "is_full": is_rented or count >= capacity,       # 마감 여부
                "is_rented": is_rented,                          # 구장 대여로 마감된 시간대
            })
        return {
            "g_code": ground["g_code"],
            "g_name": ground["g_name"],
            "g_num": capacity,
            "r_date": r_date,
            "slots": slots,
        }
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("구장 예약 현황 DB 조회 실패")
        raise HTTPException(status_code=500, detail="예약 현황 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("구장 예약 현황 조회 실패")
        raise HTTPException(status_code=500, detail="예약 현황 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 예약 1건 상세 조회
# 주의: "/reservation/customer/..", "/reservation/ground/.." 보다 아래에 있어야
#       "customer", "ground"가 r_seq로 잘못 인식되지 않음
@router.get("/reservation/{r_seq}")
def select_reservation(r_seq: int):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = RESERVATION_SELECT + " WHERE r.r_seq = %s"
            cursor.execute(sql, (r_seq,))  # 값이 1개여도 튜플이라 (r_seq,) 처럼 쉼표 필요
            row = cursor.fetchone()  # 1건만 받음 (없으면 None)
        if row is None:
            raise HTTPException(status_code=404, detail="존재하지 않는 예약 번호입니다.")
        return reservation_to_dict(row)
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("예약 상세 DB 조회 실패")
        raise HTTPException(status_code=500, detail="예약 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("예약 상세 조회 실패")
        raise HTTPException(status_code=500, detail="예약 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건 / 수정자 : 신현진 (구장 대여 시간대 마감 표시)
