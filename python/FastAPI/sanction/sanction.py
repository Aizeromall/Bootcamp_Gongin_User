# 작업자 : 김병재
# 최초 작업 일 : 2026-10-27

"""제재 API router를 하나로 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .list_sanction import router as list_router

# main.py의 prefix="/sanction"과 결합해 /sanction/list 경로를 생성합니다.
router = APIRouter()
router.include_router(list_router, prefix="/list", tags=["Sanction List"])  # 내 제재 내역

# 최종 수정 일 : 2026-10-27
