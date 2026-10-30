# 작업자 : 최현준 (수정)
# 최초 작업 일 : 2026-10-26 (기존 작업 이력 유지)
"""실제 문자열 예약 상태·취소 사유 공통 처리.
작업자 : 양태건 / 최종 수정일 : 2026-10-26
수정자 : 신현진 / 2026-10-26 (예약 구분 reservation_category 1 실력매칭 / 2 구장대여 추가)
수정자 : 신현진 / 2026-10-28 (취소 사유 '4' 기타 추가, 회원 취소 사유 글 규칙)
"""
from datetime import datetime, time, timedelta

from ..notification.events import now_kst
# 중간 수정 작성자 - 신현진
# 수정일 2026.10.28
# 취소 사유 (reservation.r_c_category, VARCHAR)
#   '1' ~ '3' : 매니저·본사가 버튼으로 골라 취소 (본사 앱) → 회원 앱에서는 이름으로 표시만
#   기타      : 회원이 직접 취소 → 회원이 작성한 글을 r_c_category에 그대로 저장
#               (코드 '4'로 저장된 값은 "기타"로 표시)
#   본사 앱은 '1' ~ '3'만 매니저 취소로 보고, 그 외 값(회원이 쓴 글)은 회원 취소로 봅니다.
CANCEL_REASONS = {"1": "정원 미달", "2": "우천·기상 악화", "3": "노쇼 및 환불", "4": "기타"}
# 회원이 사유 글로 쓸 수 없는 값
#   '1' ~ '3' : 매니저 취소 코드와 같아서 본사 앱이 매니저 취소로 잘못 봄
#   '0'       : 예약 상태(취소 아님)로 보는 값
RESERVED_CANCEL_CODES = ("0", "1", "2", "3")


# 수정 일 : 2026-10-30 / 작업자 : 최현준
# MySQL TIME은 timedelta로 반환될 수 있으며 업무 시각은 한국 시각입니다.
def cancellation_allowed(day, start_time, now=None):
    if isinstance(start_time, timedelta):
        offset = start_time
    elif isinstance(start_time, time):
        offset = timedelta(hours=start_time.hour, minutes=start_time.minute, seconds=start_time.second)
    else:
        parts = str(start_time).split(':')
        if len(parts) not in (2, 3):
            raise ValueError('예약 시작 시간을 확인할 수 없습니다.')
        offset = timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2]) if len(parts) == 3 else 0)
    if offset < timedelta(0) or offset >= timedelta(days=1):
        raise ValueError('예약 시작 시간이 유효하지 않습니다.')
    start = datetime.combine(day, time.min) + offset
    return (now or now_kst()) < start - timedelta(hours=1)


def is_canceled(row: dict) -> bool:
    reason = str(row.get("r_c_category") or "").strip()
    return reason not in ("", "0") or str(row.get("r_category") or "").strip() == "2"


def cancel_reason(row: dict) -> str | None:
    reason = str(row.get("r_c_category") or "").strip()
    return CANCEL_REASONS.get(reason, reason) if reason not in ("", "0") else None


def category_condition(canceled: bool, alias: str = "") -> str:
    # alias는 서버 내부에서 정한 테이블 별칭만 사용합니다.
    prefix = f"{alias}." if alias else ""
    condition = (f"(TRIM(COALESCE({prefix}r_c_category, '')) NOT IN ('', '0') "
                 f"OR TRIM(COALESCE({prefix}r_category, '')) = '2')")
    return condition if canceled else f"NOT {condition}"


# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# reservation.reservation_category : 예약 구분 (version2 구장대여 추가)
#   1 = 실력매칭 (회원 1명이 자리 1개 예약, 정원이 차면 매치 성사) → match/reservation.py
#   2 = 구장대여 (회원·팀장 1명이 시간대 전체를 빌림, 담당 매니저 지정) → ground/ground_reservation.py
# 같은 reservation 테이블에 함께 저장하므로 조회·정원 계산 쿼리마다 구분 조건을 넣어야 합니다.
# ************************
# 버그 확인 일 : 2026-10-28 / 작업자 : 최현준
# 1. 버그 발생 위치 : 예약 분류 상수와 SQL/Python 비교 조건
# 2. 버그 내용 : DB VARCHAR의 '2'를 정수 2와 비교해 대여 금액·중복·취소 분기가 잘못 실행됨
# 3. 디버깅 내용 : 예약 분류를 문자열 '1'/'2'로 통일하고 SQL도 문자열 리터럴로 비교
# 4. 테스트 사항 : 문자열 기준 대여 중복·금액·취소·슬롯·저장·화면 표시 회귀 검증
# 5. 결과 및 추후 보완 사항 : 빈 더미 데이터는 보정하지 않으며 예약 상태 r_category는 별개로 유지
# ************************
RESERVATION_MATCH = "1"    # 실력매칭
RESERVATION_RENTAL = "2"   # 구장대여


def reservation_type_condition(reservation_type: str, alias: str = "") -> str:
    # alias는 서버 내부에서 정한 테이블 별칭만 사용합니다.
    # 서버 상수만 허용해 SQL 삽입을 막고 VARCHAR를 숫자로 암묵 변환하지 않습니다.
    if reservation_type not in (RESERVATION_MATCH, RESERVATION_RENTAL):
        raise ValueError("예약 분류는 문자열 '1' 또는 '2'만 사용할 수 있습니다.")
    prefix = f"{alias}." if alias else ""
    return f"{prefix}reservation_category = '{reservation_type}'"

# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (경기 1시간 전 취소 제한)
