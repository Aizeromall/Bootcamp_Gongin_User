# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""구장 예약·결제 router를 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .payment import router as payment_router
from .reservation import router as reservation_router

match_router = APIRouter()
# 구장 예약: 2시간 단위의 reservation 데이터를 생성합니다.
match_router.include_router(reservation_router, tags=["Ground Reservation"])
# 결제: 예약 r_seq에 대해 payment 데이터를 생성합니다.
match_router.include_router(payment_router, tags=["Ground Payment"])

# 최종 수정 일 : 2026-10-23
