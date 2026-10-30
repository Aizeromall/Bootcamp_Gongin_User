# 작업자 : 신현진
# 최초 작업 일 : 2026-10-26

# 구장대여 API - version2 (ground_router에 묶여 실제 주소 앞에 /ground 가 붙음)
#   GET    /ground/reservation/slots/{g_code}?r_date=날짜                구장의 날짜별 대여 가능 시간대 (담당 매니저 포함)
#   POST   /ground/reservation                                         구장 시간대 대여 (회원·팀장이 구장 전체를 빌림)
#   GET    /ground/reservation/customer/{c_id_seq}                     회원별 대여 내역 (?r_category=2 취소 내역)
#   GET    /ground/reservation/{r_seq}                                 대여 1건 상세
#   DELETE /ground/reservation/{r_seq}?c_id_seq=회원ID&r_c_category=사유  대여 취소 (기타 : 사유 글 직접 작성)
#
# [version1 실력매칭(match/reservation.py)과 다른 점]
#   실력매칭 : 회원 1명이 자리 1개를 예약 → 같은 시간대에 수용인원(g_num)까지 여러 명이 모여 매치 성사
#   구장대여 : 회원(팀장) 1명이 시간대 전체를 빌림 → 본인 팀원을 부르거나 팀매칭을 진행
#   그래서 대여는 시간대마다 1건만 가능하고, 실력매칭 예약과 같은 시간대에 겹치지 않게 서로 막음
#
# [저장 위치] ERD의 reservation(예약하다) 테이블을 실력매칭과 함께 사용
#   reservation_category : 1 = 실력매칭 / 2 = 구장대여 → 이 파일은 2만 다룸
#   r_category / r_c_category : 기존과 같은 예약·취소 규칙 (match/reservation_status.py)
#     - 회원(팀장)이 직접 취소하면 기타 → 작성한 사유 글을 r_c_category에 저장 (2026.10.28 신현진)
#       ('1' ~ '3'은 매니저 취소 사유라 회원은 쓸 수 없음)
#   r_check : 0으로 저장 (팀매칭 성사 여부, 성사 전에는 0)
#   담당 매니저 : reservation에 매니저 컬럼이 없으므로 assign 배정표의 요일·시간으로 조회
#   대여 금액 : 저장하지 않고 ground.g_price(시간대 1개 전체 금액)로 계산
import logging
from datetime import date
from typing import Annotated

import pymysql
from fastapi import APIRouter, Body, HTTPException, Query, status

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
# 실력매칭 예약과 같은 기준을 쓰기 위해 match 폴더의 공용 값·함수를 가져옴
#   TIME_SLOTS : 예약 시간대 목록 (08:00~22:00 시작, 2시간 단위)
#   find_assigned_manager : 요일·시간대에 배정된 경기매니저 조회
#   sport_from_customer_id : c_id_seq 끝 번호(01~04)로 종목 확인
from ..match.reservation import TIME_SLOTS, find_assigned_manager, sport_from_customer_id
from ..team_match.lineup import guard_participant, participant_condition, cancel_pending
#   format_time : 시간 값 → "08:00" 형식으로 통일
#   RESERVATION_MANAGER_JOIN : 예약 행마다 배정표 기준 매니저를 붙이는 JOIN
from ..match.reservation_search import RESERVATION_MANAGER_JOIN, format_time
#   예약·취소 상태 / 예약 구분(1 실력매칭 / 2 구장대여) 공용 처리
#   CANCEL_REASONS / RESERVED_CANCEL_CODES : 취소 사유 이름, 회원이 쓸 수 없는 사유 값 (2026.10.28 신현진)
from ..match.reservation_status import (
    CANCEL_REASONS,
    RESERVED_CANCEL_CODES,
    RESERVATION_MATCH,
    RESERVATION_RENTAL,
    cancel_reason,
    category_condition,
    is_canceled,
    reservation_type_condition,
)

# 이 파일의 API들을 담는 라우터 (ground/__init__.py에서 ground_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# 예약·취소 구분 값 (r_category) - 조회 필터용
CATEGORY_RESERVED = 1   # 예약
CATEGORY_CANCELED = 2   # 취소


# DB에서 받은 대여 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄
# 응답 키는 실력매칭 예약 조회(reservation_search.py)와 같은 이름을 사용
def ground_reservation_to_dict(row: dict) -> dict:
    return {
        "r_seq": row["r_seq"],                       # 예약번호 (결제 /match/payment 에도 그대로 사용)
        "c_id_seq": row["c_id_seq"],                 # 대여한 회원 (팀장)
        "g_code": row["g_code"],                     # 구장코드
        "g_name": row["g_name"],                     # 구장명 (ground JOIN)
        "g_address": row["g_address"],               # 구장 주소 (ground JOIN)
        "g_price": row["g_price"],                   # 대여 금액 (시간대 1개 전체 금액, ground JOIN)
        "m_id": row["m_id"],                         # 담당 경기매니저 ID (배정이 없으면 None)
        "m_name": row["m_name"],                     # 경기매니저 이름 (배정표 기준 JOIN)
        "r_date": row["r_date"],                     # 대여일 (경기일, 취소해도 그대로 유지)
        "rs_time": format_time(row["rs_time"]),      # 대여 시작 시간
        "re_time": format_time(row["re_time"]),      # 대여 종료 시간
        "reservation_category": row["reservation_category"],  # 예약 구분 (1.픽업매치, 2.구장대여)
        "r_category": CATEGORY_CANCELED if is_canceled(row) else CATEGORY_RESERVED,  # 1 예약 / 2 취소
        "is_canceled": is_canceled(row),             # 취소 여부 (앱에서 true/false로 바로 사용)
        "r_c_category": row["r_c_category"],         # 취소 사유 (회원 취소는 작성한 글, 매니저 취소는 '1' ~ '3')
        "cancel_reason": cancel_reason(row),         # 취소 사유 표시 (예약 상태면 None)
        "r_check": bool(row["r_check"]),             # 팀매칭 성사 여부 (DB 0/1 → false/true)
        "p_seq": row["p_seq"],                       # 결제번호 (결제 전이거나 취소로 환불되면 None)
        "is_paid": row["p_seq"] is not None,         # 결제 완료 여부
    }


# 대여 조회에서 공통으로 쓰는 SELECT
# r / g / m / p 는 테이블 별칭 (reservation / ground / match_manager / pay)
# INNER JOIN ground : 대여한 구장의 이름·주소·금액을 함께 가져옴
# RESERVATION_MANAGER_JOIN : 대여일 요일·시간에 배정된 매니저 (reservation_search.py와 같은 기준)
# LEFT JOIN pay : 결제 전인 대여도 빠지지 않고 나옴 (결제 값은 None)
# 마지막 WHERE : 구장대여(reservation_category = 2)만 조회
GROUND_RESERVATION_SELECT = f"""
    SELECT r.r_seq, r.c_id_seq, r.g_code, g.g_name, g.g_address, g.g_price, m.m_id, m.m_name,
        r.r_date, r.rs_time, r.re_time, r.r_check, r.reservation_category, r.r_category, r.r_c_category, p.p_seq
    FROM reservation AS r
    INNER JOIN ground AS g ON g.g_code = r.g_code
    {RESERVATION_MANAGER_JOIN}
    LEFT JOIN pay AS p ON p.r_seq = r.r_seq
    WHERE {reservation_type_condition(RESERVATION_RENTAL, 'r')}
      AND NOT {participant_condition('r')}
"""


# 구장의 날짜별 대여 가능 시간대 조회 (구장 예약 화면의 시간 선택 버튼용)
# 시간대마다 아래 두 가지를 확인해서 대여 가능 여부를 계산 (둘 다 취소 사유가 없는 예약만)
#   1) 다른 회원이 이미 대여했는지 (reservation_category = 2)
#   2) 실력매칭 예약이 1명이라도 있는지 (reservation_category = 1)
# 예: /ground/reservation/slots/1?r_date=2026-10-30
@router.get("/reservation/slots/{g_code}")
def select_ground_reservation_slots(g_code: str, r_date: date):
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            # 1) 구장이 있는지 + 대여 금액 확인
            cursor.execute("SELECT g_code, g_name, g_price FROM ground WHERE g_code = %s", (g_code,))
            ground = cursor.fetchone()  # 1건만 받음 (없으면 None)
            if ground is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장 코드입니다.")

            # 2) 해당 날짜의 예약된 시간대를 구분값과 함께 조회 (취소 사유가 없는 예약만)
            cursor.execute(
                f"""SELECT DISTINCT rs_time, reservation_category FROM reservation
                    WHERE g_code = %s AND r_date = %s AND {category_condition(False)}""",
                (g_code, r_date),
            )
            rows = cursor.fetchall()
            rented_times = {format_time(row["rs_time"]) for row in rows
                            if row["reservation_category"] == RESERVATION_RENTAL}
            match_times = {format_time(row["rs_time"]) for row in rows
                           if row["reservation_category"] == RESERVATION_MATCH}

            # 3) TIME_SLOTS 전체를 돌면서 시간대별 대여 가능 여부 + 담당 매니저를 채움
            slots = []
            for rs_time, re_time in TIME_SLOTS.items():
                manager = find_assigned_manager(cursor, g_code, r_date, rs_time, re_time)
                is_rented = rs_time in rented_times
                has_match = rs_time in match_times
                slots.append({
                    "rs_time": rs_time,                              # 시작 시간
                    "re_time": re_time,                              # 종료 시간
                    "is_rented": is_rented,                          # 다른 회원이 대여한 시간대
                    "has_match_reservation": has_match,              # 실력매칭 예약이 있는 시간대
                    "is_available": not is_rented and not has_match, # 대여 가능 여부 (false면 화면에 "예약완료")
                    "m_id": manager["m_id"] if manager else None,    # 그 시간대 담당 매니저
                    "m_name": manager["m_name"] if manager else None,
                })
        return {
            "g_code": ground["g_code"],
            "g_name": ground["g_name"],
            "g_price": ground["g_price"],   # 시간대 1개 대여 금액
            "r_date": r_date,
            "slots": slots,
        }
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("구장대여 시간대 DB 조회 실패")
        raise HTTPException(status_code=500, detail="대여 시간대 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("구장대여 시간대 조회 실패")
        raise HTTPException(status_code=500, detail="대여 시간대 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 구장 시간대 대여 (회원·팀장이 시간대 전체를 빌림)
# 대여 조건
#   1) 지난 날짜는 대여 불가
#   2) 같은 시간대에 다른 대여가 있으면 불가
#   3) 같은 시간대에 실력매칭 예약이 1명이라도 있으면 불가
# 담당 매니저는 앱에서 받지 않고 assign 배정표에서 서버가 찾아서 응답 (배정이 없으면 None)
# 결제는 응답의 r_seq로 기존 POST /match/payment 를 사용 (구장대여는 g_price 전체 금액)
@router.post(
    "/reservation",
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "c_id_seq / 시작 시간 형식 오류 또는 지난 날짜"},
        404: {"description": "회원 또는 구장 코드가 존재하지 않음"},
        409: {"description": "이미 대여된 시간대 또는 실력매칭 예약이 있는 시간대"},
        422: {"description": "필수 요청값 검증 실패"},
        500: {"description": "DB 연결 또는 대여 처리 실패"},
    },
)
def create_ground_reservation(
    # 수정 일 : 2026-10-28 / 작업자 : 최현준 — 기존 FK를 유지하면서 48자 소셜 회원 PK를 허용합니다.
    c_id_seq: Annotated[str, Body(min_length=4, max_length=50, description="대여하는 회원 (customer FK, 최대 50자)")],
    g_code: Annotated[str, Body(min_length=1, max_length=45, description="ground 테이블의 구장 코드")],
    r_date: Annotated[date, Body(description="대여 일자")],
    rs_time: Annotated[str, Body(description="대여 시작 시간: 08:00~22:00, 2시간 단위")],
):
    c_id_seq, g_code = c_id_seq.strip(), g_code.strip()  # 앞뒤 공백 제거
    if rs_time not in TIME_SLOTS:
        raise HTTPException(status_code=400, detail="rs_time은 08:00부터 22:00까지 2시간 단위로 선택해야 합니다.")
    if r_date < date.today():
        raise HTTPException(status_code=400, detail="지난 날짜는 대여할 수 없습니다.")

    sport_name, re_time = sport_from_customer_id(c_id_seq), TIME_SLOTS[rs_time]  # 종목 확인 + 종료 시간(2시간 뒤)
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:
            # 1) 구장 조회 + 잠금
            # FOR UPDATE : 대여하는 동안 같은 구장의 다른 대여·실력매칭 예약이 끼어들지 못하게 잠금
            # (실력매칭 예약 match/reservation.py도 같은 ground 행을 먼저 잠그므로 둘이 동시에 들어가지 않음)
            cursor.execute("SELECT g_code, g_price FROM ground WHERE g_code = %s FOR UPDATE", (g_code,))
            ground = cursor.fetchone()  # 1건만 받음 (없으면 None)
            if ground is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장 코드입니다.")

            # 2) 회원 확인
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s LIMIT 1", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 3) 같은 시간대의 예약을 구분값과 함께 확인 (취소 사유가 없는 예약만)
            cursor.execute(
                f"""SELECT reservation_category FROM reservation
                    WHERE g_code = %s AND r_date = %s AND rs_time = %s AND {category_condition(False)}""",
                (g_code, r_date, rs_time),
            )
            booked_types = {row["reservation_category"] for row in cursor.fetchall()}
            if RESERVATION_RENTAL in booked_types:
                raise HTTPException(status_code=409, detail="이미 대여된 시간대입니다.")
            if RESERVATION_MATCH in booked_types:
                raise HTTPException(status_code=409, detail="실력매칭 예약이 있는 시간대라 대여할 수 없습니다.")

            # 4) 그 시간대 담당 경기매니저 조회 (assign 배정표의 요일·시간 기준, 없으면 None)
            manager = find_assigned_manager(cursor, g_code, r_date, rs_time, re_time)

            # 5) 대여 저장
            #   reservation_category = 2 (구장대여)
            #   r_check = 0 (팀매칭 성사 전), r_category = "1" (예약), r_c_category = "" (취소 사유 없음)
            #   r_category / r_c_category 값은 실력매칭 예약(match/reservation.py)과 같은 형식
            cursor.execute(
                """INSERT INTO reservation
                    (g_code, c_id_seq, rs_time, re_time, r_date, r_check, reservation_category, r_category, r_c_category)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (g_code, c_id_seq, rs_time, re_time, r_date, False, RESERVATION_RENTAL, "1", ""),
            )
            r_seq = cursor.lastrowid  # 방금 저장된 예약번호 (AUTO_INCREMENT)
            if not isinstance(r_seq, int) or r_seq <= 0:
                raise RuntimeError("reservation.r_seq 자동 증가값을 가져오지 못했습니다.")
        connection.commit()  # 위 작업을 한 번에 확정
        return {
            "result": "OK",
            "r_seq": r_seq,                                       # 예약번호 (결제 시 사용)
            "c_id_seq": c_id_seq,                                 # 대여한 회원
            "sport": sport_name,                                  # 회원 종목
            "g_code": g_code,                                     # 구장코드
            "r_date": r_date,                                     # 대여일
            "rs_time": rs_time,                                   # 시작 시간
            "re_time": re_time,                                   # 종료 시간
            "reservation_category": RESERVATION_RENTAL,           # 예약 구분 (2 구장대여)
            "g_price": ground["g_price"],                         # 대여 금액
            "m_id": manager["m_id"] if manager else None,         # 담당 매니저 ID
            "m_name": manager["m_name"] if manager else None,     # 담당 매니저 이름
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 404/409는 되돌린 뒤 그대로 전달
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()  # 에러 시 저장 취소
        logger.exception("구장대여 DB 처리 실패")
        raise HTTPException(status_code=500, detail="구장 대여 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("구장대여 처리 실패")
        raise HTTPException(status_code=500, detail="구장 대여에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 회원별 대여 내역 / 취소 내역 조회
# r_category를 안 보내면 1(예약)로 조회
# 예: /ground/reservation/customer/hong_01                대여 내역
#     /ground/reservation/customer/hong_01?r_category=2   취소 내역
@router.get("/reservation/customer/{c_id_seq}")
def select_ground_reservations_by_customer(
    c_id_seq: str,
    # ge=1, le=2 : 1~2 밖의 값이 오면 FastAPI가 자동으로 422 에러 처리
    r_category: int = Query(CATEGORY_RESERVED, ge=1, le=2, description="1 대여 내역 / 2 취소 내역"),
):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 취소 시각 컬럼이 없으므로 대여일·예약번호 기준 최신순으로 정렬
            sql = GROUND_RESERVATION_SELECT + f"""
                AND r.c_id_seq = %s AND {category_condition(r_category == CATEGORY_CANCELED, 'r')}
                ORDER BY r.r_date DESC, r.rs_time DESC, r.r_seq DESC
            """
            cursor.execute(sql, (c_id_seq,))
            rows = cursor.fetchall()
        # 대여 내역이 하나도 없으면 빈 리스트 [] 가 나감 (에러 아님)
        return {"results": [ground_reservation_to_dict(row) for row in rows]}
    except pymysql.MySQLError:
        logger.exception("회원 구장대여 내역 DB 조회 실패")
        raise HTTPException(status_code=500, detail="대여 내역 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("회원 구장대여 내역 조회 실패")
        raise HTTPException(status_code=500, detail="대여 내역 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 대여 1건 상세 조회 (예약/취소 상관없이 조회, 실력매칭 예약번호면 404)
# 주의: "/reservation/slots/..", "/reservation/customer/.." 보다 아래에 있어야
#       "slots", "customer"가 r_seq로 잘못 인식되지 않음
@router.get("/reservation/{r_seq}")
def select_ground_reservation(r_seq: int):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = GROUND_RESERVATION_SELECT + " AND r.r_seq = %s"
            cursor.execute(sql, (r_seq,))  # 값이 1개여도 튜플이라 (r_seq,) 처럼 쉼표 필요
            row = cursor.fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="존재하지 않는 구장대여 번호입니다.")
        return ground_reservation_to_dict(row)
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("구장대여 상세 DB 조회 실패")
        raise HTTPException(status_code=500, detail="대여 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("구장대여 상세 조회 실패")
        raise HTTPException(status_code=500, detail="대여 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 구장대여 취소
# 취소 조건
#   1) 구장대여(reservation_category = 2)만 취소 (실력매칭은 /cancel/reservation/{r_seq})
#   2) 본인 대여만 취소 가능
#   3) 이미 취소된 대여는 다시 취소 불가
#   4) 팀매칭이 성사된(r_check = 1) 대여는 취소 불가
#   5) 이미 지난 날짜의 대여는 취소 불가
# 결제가 되어 있으면 결제 내역(pay)도 같이 삭제 (환불 처리)
# 행은 지우지 않고 r_category = "2"로 UPDATE → 같은 시간대가 다시 비어서 대여·실력매칭 가능
#
# 중간 수정 작성자 - 신현진
# 수정일 2026.10.28
# 회원 직접 취소 = 기타 → 팀장이 작성한 사유 글을 r_c_category에 그대로 저장
#   '1' ~ '3'은 매니저 취소 사유(본사 앱 버튼)라 회원은 고를 수 없고,
#   글로 '1' ~ '3', '0'만 입력하면 매니저 취소·예약 상태로 잘못 보이므로 422로 막음
# 팀장이 바뀌어 대여가 새 팀장에게 넘어간 경우에도 결제(pay.c_id_seq)는 실제로 결제한 회원 그대로라
# 환불 대상은 응답의 refund_c_id_seq(결제한 회원)로 안내
# 예: DELETE /ground/reservation/15?c_id_seq=hong_01&r_c_category=팀매칭 성사 안 됨
@router.delete("/reservation/{r_seq}")
def cancel_ground_reservation(
    r_seq: int,
    r_c_category: str = Query(min_length=1, max_length=50, description="팀장이 작성한 취소 사유 (기타, 최대 50자)"),
    c_id_seq: str = Query(min_length=4, max_length=50, description="취소를 요청한 회원 (본인 확인용)"),
):
    c_id_seq = c_id_seq.strip()            # 앞뒤 공백 제거
    # 사유 글 검사 : 빈 글 / 매니저 취소 코드('1' ~ '3')·예약 상태('0')와 같은 글 → 422
    r_c_category = r_c_category.strip()
    if not r_c_category:
        raise HTTPException(status_code=422, detail="취소 사유를 입력해 주세요.")
    if r_c_category in RESERVED_CANCEL_CODES:
        raise HTTPException(status_code=422, detail="취소 사유는 숫자 하나가 아닌 글로 입력해 주세요.")
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 1) 취소할 대여 조회
            # FOR UPDATE : 취소하는 동안 다른 요청이 이 대여를 바꾸지 못하게 잠금
            cursor.execute(
                """SELECT r_seq, c_id_seq, r_date, r_check, reservation_category, r_category, r_c_category
                    FROM reservation
                    WHERE r_seq = %s
                    FOR UPDATE""",
                (r_seq,),
            )
            reservation = cursor.fetchone()
            if reservation is None or reservation["reservation_category"] != RESERVATION_RENTAL:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장대여 번호입니다.")
            guard_participant(cursor, r_seq)

            # 2) 본인 대여인지 확인
            if reservation["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 대여만 취소할 수 있습니다.")

            # 3) 이미 취소된 대여인지 확인
            if is_canceled(reservation):
                raise HTTPException(status_code=409, detail="이미 취소된 대여입니다.")

            # 4) 팀매칭 성사 여부 확인 (r_check = 1 이면 성사)
            if bool(reservation["r_check"]):
                raise HTTPException(status_code=409, detail="팀매칭이 성사된 대여는 취소할 수 없습니다.")

            # 5) 지난 날짜 대여인지 확인
            if reservation["r_date"] < date.today():
                raise HTTPException(status_code=409, detail="이미 지난 대여는 취소할 수 없습니다.")
            cursor.execute('SELECT r.*,g.g_num FROM reservation r JOIN ground g ON g.g_code=r.g_code WHERE r.r_seq=%s', (r_seq,))
            cancel_pending(cursor, cursor.fetchone())

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.28
            # 6) 결제 내역 삭제 (결제 전 대여면 지울 게 없어서 rowcount = 0)
            # pay.c_id_seq : 실제로 결제한 회원 (팀장이 바뀌었으면 이전 팀장) → 환불 대상 안내용
            cursor.execute("SELECT p_seq, p_amount, c_id_seq FROM pay WHERE r_seq = %s", (r_seq,))
            payment = cursor.fetchone()  # 환불 금액·대상 안내용 (없으면 None)
            cursor.execute("DELETE FROM pay WHERE r_seq = %s", (r_seq,))

            # 중간 수정 작성자 - 신현진
            # 수정일 2026.10.28
            # 7) 취소 상태로 변경 (DELETE 대신 UPDATE → 취소 내역으로 남음)
            # category_condition(False) : 그 사이에 다른 요청이 먼저 취소했으면 바뀌지 않음
            # 회원 직접 취소(기타)이므로 r_c_category = 팀장이 작성한 사유 글
            cursor.execute(
                f"""UPDATE reservation
                    SET r_category = %s, r_c_category = %s
                    WHERE r_seq = %s AND {category_condition(False)}""",
                ("2", r_c_category, r_seq),
            )
            # rowcount: 바뀐 행 수 → 0이면 그 사이에 이미 취소된 대여
            if cursor.rowcount == 0:
                raise HTTPException(status_code=409, detail="이미 취소된 대여입니다.")
        # 중간 수정 작성자 - 신현진
        # 수정일 2026.10.28
        # 응답 : 저장한 사유 글, 환불 대상(결제한 회원) 추가
        connection.commit()  # 결제 삭제 + 취소 상태 변경을 한 번에 확정
        return {
            "result": "OK",
            "r_seq": r_seq,                                          # 취소된 예약번호
            "c_id_seq": c_id_seq,                                    # 취소한 회원
            "reservation_category": RESERVATION_RENTAL,              # 예약 구분 (2 구장대여)
            "r_category": CATEGORY_CANCELED,                         # 변경된 카테고리 (2 취소)
            "r_date": reservation["r_date"],                         # 취소한 대여의 대여일
            "r_c_category": r_c_category,                            # 저장한 취소 사유 (팀장이 작성한 글)
            "cancel_reason": CANCEL_REASONS.get(r_c_category, r_c_category),  # 화면 표시용 취소 사유
            "is_refunded": payment is not None,                      # 결제 취소(환불) 여부
            "refund_amount": payment["p_amount"] if payment else 0,  # 환불 금액
            "refund_c_id_seq": payment["c_id_seq"] if payment else None,  # 환불 대상 (실제로 결제한 회원)
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 404/403/409는 되돌린 뒤 그대로 전달
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()  # 에러 시 결제 삭제·취소 상태 변경을 모두 되돌림
        logger.exception("구장대여 취소 DB 처리 실패")
        raise HTTPException(status_code=500, detail="대여 취소 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("구장대여 취소 처리 실패")
        raise HTTPException(status_code=500, detail="대여 취소에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-26
# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (소셜 회원 ID 입력 길이 DB 정합성 적용)
# 최종 수정 일 : 2026-10-28 수정자 : 신현진 (회원 취소 사유 글 검사, 환불 대상 안내)
# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준 (main 환불 대상 안내와 소셜 회원 ID 길이 처리 통합)
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
