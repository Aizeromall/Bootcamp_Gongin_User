# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""구장 예약·결제 router를 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .ground_search import router as ground_search_router
from .payment import router as payment_router
from .payment_search import router as payment_search_router
from .reservation import router as reservation_router
from .reservation_search import router as reservation_search_router
from .resultcheck import router as resultcheck_router

match_router = APIRouter()
# 구장 예약: 2시간 단위의 reservation 데이터를 생성합니다.
match_router.include_router(reservation_router, tags=["Ground Reservation"])
# 결제: 예약 r_seq에 대해 payment 데이터를 생성합니다.
match_router.include_router(payment_router, tags=["Ground Payment"])
# 구장 조회: 구장 목록 / 구장 1건 상세를 조회합니다.
match_router.include_router(ground_search_router, tags=["Ground Search"])
# 예약 조회: 회원별 예약 내역 / 구장 시간대 예약 현황 / 예약 1건을 조회합니다.
match_router.include_router(reservation_search_router, tags=["Reservation Search"])
# 결제 조회: 회원별 결제 내역 / 예약별 결제 / 결제 1건을 조회합니다.
match_router.include_router(payment_search_router, tags=["Payment Search"])
# 경기결과 조회: 회원이 참여한 경기결과 목록 / 결과 1건을 조회합니다.
match_router.include_router(resultcheck_router, tags=["Result Check"])

# 최종 수정 일 : 2026-10-23
