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
# 모든 예약 응답에 배정 경기매니저(m_id, m_name)를 함께 보냄 (reservation.m_id, 2026.10.26 추가)
#
# reservation.r_category : 예약 구분
#   1 = 예약 (r_date = 경기일, r_cancel_date = NULL)
#   2 = 취소 (r_date = 원래 경기일 그대로, r_cancel_date = 취소한 날짜)
#   취소해도 행을 지우지 않고 r_category만 2로 바꿔서 취소 내역을 조회할 수 있게 함
import logging
from datetime import date, timedelta

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
import pymysql
from fastapi import APIRouter, HTTPException, Query

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
from .reservation import TIME_SLOTS  # 예약 시간대 목록 (08:00~22:00, 2시간 단위)

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
        "r_category": row["r_category"],         # 카테고리 (1 예약 / 2 취소)
        "is_canceled": row["r_category"] == CATEGORY_CANCELED,  # 취소 여부 (앱에서 true/false로 바로 사용)
        "r_cancel_date": row["r_cancel_date"],   # 취소일 (예약 상태면 None)
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
RESERVATION_SELECT = """
    SELECT r.r_seq, r.c_id_seq, r.g_code, g.g_name, g.g_address, r.m_id, m.m_name,
        r.r_date, r.rs_time, r.re_time, r.r_check, r.r_category, r.r_cancel_date, p.p_seq
    FROM reservation AS r
    INNER JOIN ground AS g ON g.g_code = r.g_code
    LEFT JOIN match_manager AS m ON m.m_id = r.m_id
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
            # 예약 내역은 경기일 최신순, 취소 내역은 취소한 날짜 최신순으로 정렬
            if r_category == CATEGORY_CANCELED:
                order_by = "r.r_cancel_date DESC, r.r_seq DESC"
            else:
                order_by = "r.r_date DESC, r.rs_time DESC"
            sql = RESERVATION_SELECT + f"""
                WHERE r.c_id_seq = %s AND r.r_category = %s
                ORDER BY {order_by}
            """
            # order_by는 위에서 정한 고정 문자열만 들어가므로 f-string을 써도 SQL 인젝션 위험 없음
            cursor.execute(sql, (c_id_seq, r_category))  # %s 자리에 값이 순서대로 들어감 (SQL 인젝션 방지)
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
            # r_category = 1 : 취소된 예약은 자리를 차지하지 않으므로 세지 않음
            sql = """
                SELECT rs_time, COUNT(*) AS reservation_count
                FROM reservation
                WHERE g_code = %s AND r_date = %s AND r_category = %s
                GROUP BY rs_time
            """
            cursor.execute(sql, (g_code, r_date, CATEGORY_RESERVED))
            rows = cursor.fetchall()

        # {시작시간: 예약 수} 형태로 정리 (예약이 없는 시간대는 dict에 없음)
        counts = {format_time(row["rs_time"]): row["reservation_count"] for row in rows}
        capacity = ground["g_num"]  # 수용인원
        # TIME_SLOTS 전체를 돌면서 예약 없는 시간대도 0건으로 채워서 보냄
        slots = []
        for rs_time, re_time in TIME_SLOTS.items():
            count = counts.get(rs_time, 0)
            slots.append({
                "rs_time": rs_time,                              # 시작 시간
                "re_time": re_time,                              # 종료 시간
                "reservation_count": count,                      # 현재 예약 수
                "remaining_capacity": max(capacity - count, 0),  # 남은 자리
                "is_full": count >= capacity,                    # 마감 여부
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

# 최종 수정 일 : 2026-10-26
