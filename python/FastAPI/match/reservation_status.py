"""실제 문자열 예약 상태·취소 사유 공통 처리.
작업자 : 양태건 / 최종 수정일 : 2026-10-26
수정자 : 신현진 / 2026-10-26 (예약 구분 reservation_category 1 실력매칭 / 2 구장대여 추가)
수정자 : 신현진 / 2026-10-28 (취소 사유 '4' 기타 추가, 회원 취소 사유 글 규칙)
"""
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
