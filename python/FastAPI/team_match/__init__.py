# 작업자 : 신현진
# 최초 작업 일 : 2026-10-26

"""팀 경기 매칭 router를 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .team_match_connect import router as team_match_connect_router

team_match_router = APIRouter()
# 팀 경기 매칭: [매칭신청] 게시글 작성 / 상대 팀 리스트 / 신청 / 수락·거절 (/team_match/...)
# 매칭 진행 과정은 board_a_write(게시글 + 댓글·대댓글)에 남기고, 성사되면 team_match에 저장합니다.
team_match_router.include_router(team_match_connect_router, prefix="/team_match", tags=["Team Match"])

# 최종 수정 일 : 2026-10-26
