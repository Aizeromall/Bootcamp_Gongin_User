# 작업자 : 신현진
# 최초 작업 일 : 2026-10-29

"""회원·팀 등급 점수 조회 router를 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .rating_search import router as rating_search_router

rating_router = APIRouter()
# 점수 조회: 등급표 / 내 수준 통계 / 내 경기별 점수 변동 / 팀 경기별 점수 변동 (/rating/...)
# 점수는 관리자 앱의 경기 결과 등록에서만 바뀌고, 회원 앱은 조회만 합니다.
rating_router.include_router(rating_search_router, prefix="/rating", tags=["Rating"])

# 최종 수정 일 : 2026-10-29
