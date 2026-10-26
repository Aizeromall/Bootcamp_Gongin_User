"""실제 문자열 예약 상태·취소 사유 공통 처리.
작업자 : 양태건 / 최종 수정일 : 2026-10-26
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
