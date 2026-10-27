# 작업자 : 김병재
# 최초 작업 일 : 2026-10-27

"""이의신청 API router를 하나로 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .insert_appeal import router as insert_router
from .list_appeal import router as list_router

# main.py의 prefix="/appeal"와 결합해 /appeal/insert, /appeal/list 경로를 생성합니다.
router = APIRouter()
router.include_router(insert_router, prefix="/insert", tags=["Appeal Insert"])  # 이의신청 접수
router.include_router(list_router, prefix="/list", tags=["Appeal List"])  # 내 이의신청 내역

# 최종 수정 일 : 2026-10-27
