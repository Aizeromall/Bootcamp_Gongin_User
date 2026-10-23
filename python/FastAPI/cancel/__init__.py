# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

"""예약 취소 router를 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .customer_match_delete import router as customer_match_delete_router

cancel_router = APIRouter()
# 회원 예약 취소: 매치가 성사되지 않은 본인 예약을 취소합니다.
cancel_router.include_router(customer_match_delete_router, tags=["Customer Match Cancel"])

# 최종 수정 일 : 2026-10-23
