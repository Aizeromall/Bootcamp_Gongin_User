# 2026-10-30
# 작업자 : 김병재

"""내 소속팀 관련 router를 main.py에 전달합니다."""
from fastapi import APIRouter

from .list_my_team import router as list_my_team_router
from .team_members import router as team_members_router

# 수정 일 : 2026-10-30 / 작업자 : 김병재
# main.py에서 prefix 없이 등록하도록 /my_team 경로를 여기서 붙입니다.
# 조회 API의 경로가 ""이므로 include_router의 prefix로 붙여야 FastAPI 경로 검증을 통과합니다.
#   - 내 종목별 소속팀 조회 : GET /my_team (로그인 JWT 필요)
#   - 내 소속팀 팀원 목록   : GET /my_team/members/{t_id} (로그인 JWT 필요, 팀원만)
router = APIRouter()
router.include_router(list_my_team_router, prefix="/my_team", tags=["My Team"])
router.include_router(team_members_router, prefix="/my_team", tags=["My Team"])

# 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
