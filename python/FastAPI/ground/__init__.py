# 작업자 : 신현진
# 최초 작업 일 : 2026-10-26

"""구장 조회·구장 대여(version2) router를 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .ground_reservation import router as ground_reservation_router
from .ground_search import router as ground_search_router

ground_router = APIRouter()
# /ground 주소는 여기서 붙입니다. (main.py에서는 prefix 없이 ground_router를 등록)
# 구장 목록 주소가 ""(빈 문자열)이라 prefix 없이 묶으면 FastAPI가 등록을 막기 때문입니다.
# 구장 대여: 회원(팀장)이 비어 있는 시간대에 구장 전체를 빌립니다. (/ground/reservation/...)
# 주의: 구장 상세(/ground/{g_code})보다 먼저 등록해야 "reservation"이 g_code로 잘못 인식되지 않습니다.
ground_router.include_router(ground_reservation_router, prefix="/ground", tags=["Ground Rental"])
# 구장 조회: 구장 목록 / 구장 1건 상세를 조회합니다. (/ground, /ground/{g_code})
ground_router.include_router(ground_search_router, prefix="/ground", tags=["Ground Search"])

# 최종 수정 일 : 2026-10-26
