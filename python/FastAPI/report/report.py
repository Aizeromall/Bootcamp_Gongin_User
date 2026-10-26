# 작업자 : 김병재
# 최초 작업 일 : 2026-10-26

"""신고 API router를 하나로 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .insert_report import router as insert_router
from .list_report import router as list_router

# main.py의 prefix="/report"와 결합해 /report/insert, /report/list 경로를 생성합니다.
router = APIRouter()
router.include_router(insert_router, prefix="/insert", tags=["Report Insert"])  # 신고 작성
router.include_router(list_router, prefix="/list", tags=["Report List"])  # 내 신고 내역

# 최종 수정 일 : 2026-10-26
