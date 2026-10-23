# 작업자 : 김병재
# 최초 작업 일 : 2026-10-23

"""문의 API router를 하나로 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .insert_inquiry import router as insert_router
from .list_inquiry import router as list_router

# main.py의 prefix="/inquiry"와 결합해 /inquiry/insert, /inquiry/list 경로를 생성합니다.
router = APIRouter()
router.include_router(insert_router, prefix="/insert", tags=["Inquiry Insert"])  # 문의 작성
router.include_router(list_router, prefix="/list", tags=["Inquiry List"])  # 내 문의 목록
