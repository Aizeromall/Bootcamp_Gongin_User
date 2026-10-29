# 2026-10-27
# 작업자 : 양태건

"""팀 관련 router를 main.py에 전달합니다."""
from fastapi import APIRouter

from .create_team import router as create_team_router
from .delete import router as delete_team_router
from .select import router as select_team_router
from .apply_team import router as apply_team_router
# 수정 일 : 2026-10-28 / 작업자 : 양태건
from .recruitment import router as recruitment_router
# 중간 수정 작성자 - 신현진
# 수정일 2026.10.28
# 팀장 변경 (진행 중인 구장대여·매칭신청 게시글도 새 팀장에게 이전)
from .change_captain import router as change_captain_router

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 팀 개설·폐지·조회와 가입·탈퇴 router를 연결합니다.
router = APIRouter()
router.include_router(create_team_router)
router.include_router(delete_team_router)
router.include_router(select_team_router)
router.include_router(apply_team_router)
router.include_router(recruitment_router)
# 중간 수정 작성자 - 신현진
# 수정일 2026.10.28
# 팀장 변경 router 연결 (POST /team/captain/{t_id})
router.include_router(change_captain_router)

# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건 / 수정자 : 신현진 (팀장 변경 router 추가)
