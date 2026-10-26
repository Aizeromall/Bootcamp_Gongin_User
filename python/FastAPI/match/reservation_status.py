"""실제 문자열 예약 상태·취소 사유 공통 처리.
작업자 : 양태건 / 최종 수정일 : 2026-10-26
수정자 : 신현진 / 2026-10-26 (예약 구분 reservation_category 1 실력매칭 / 2 구장대여 추가)
"""
CANCEL_REASONS = {"1": "정원 미달", "2": "우천·기상 악화", "3": "노쇼 및 환불"}


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
RESERVATION_MATCH = 1    # 실력매칭
RESERVATION_RENTAL = 2   # 구장대여


def reservation_type_condition(reservation_type: int, alias: str = "") -> str:
    # alias는 서버 내부에서 정한 테이블 별칭만 사용합니다.
    # int()로 변환해서 숫자만 SQL에 들어가게 합니다. (예: "r.reservation_category = 1")
    prefix = f"{alias}." if alias else ""
    return f"{prefix}reservation_category = {int(reservation_type)}"
