# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""FastAPI 서버 진입점입니다. DB 처리는 각 기능 router와 database.py가 담당합니다."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# `python3 python/FastAPI/main.py` 직접 실행은 패키지 문맥이 없으므로
# python 폴더를 import 경로에 넣은 뒤 절대 import를 사용합니다.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from FastAPI.auth import auth_router
    from FastAPI.team.team import router as team_router
    from FastAPI.announce import announce_router
    from FastAPI.board.board import router as board_router
    from FastAPI.inquiry.inquiry import router as inquiry_router
    from FastAPI.match import match_router
    from FastAPI.cancel import cancel_router                # 수정 : 신현진 2026.10.23
    from FastAPI.report.report import router as report_router   # 수정 : 김병재 2026.10.26
    from FastAPI.sanction.sanction import router as sanction_router   # 수정 : 김병재 2026.10.27
    from FastAPI.appeal.appeal import router as appeal_router   # 수정 : 김병재 2026.10.27
    # 중간 수정 작성자 - 신현진
    # 수정일 2026.10.26
    # 구장 조회·구장 대여(version2) router (python/FastAPI/ground 폴더)
    from FastAPI.ground import ground_router
    # 중간 수정 작성자 - 신현진
    # 수정일 2026.10.26
    # 팀 경기 매칭 router (python/FastAPI/team_match 폴더)
    from FastAPI.team_match import team_match_router
else:
    # `python -m FastAPI.main` 모듈 실행에서는 일반 상대 import를 사용합니다.
    from .auth import auth_router
    from .team.team import router as team_router
    from .announce import announce_router
    from .board.board import router as board_router
    from .inquiry.inquiry import router as inquiry_router
    from .match import match_router
    from .cancel import cancel_router                       # 수정 : 신현진 2026.10.23
    from .report.report import router as report_router      # 수정 : 김병재 2026.10.26
    from .sanction.sanction import router as sanction_router      # 수정 : 김병재 2026.10.27
    from .appeal.appeal import router as appeal_router      # 수정 : 김병재 2026.10.27
    # 중간 수정 작성자 - 신현진
    # 수정일 2026.10.26
    # 구장 조회·구장 대여(version2) router (python/FastAPI/ground 폴더)
    from .ground import ground_router
    # 중간 수정 작성자 - 신현진
    # 수정일 2026.10.26
    # 팀 경기 매칭 router (python/FastAPI/team_match 폴더)
    from .team_match import team_match_router

# main.py → FastAPI → python → 프로젝트 루트 순서로 서버 환경 설정을 읽습니다.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(
    title="Bootcamp Gongin User API",
    version="1.0.0",
    description="회원가입과 로그인 API입니다. /docs에서 요청 형식과 상태 코드를 확인할 수 있습니다.",
)


def api_port() -> int:
    """비어 있거나 잘못된 API_PORT도 서버 기본 포트로 안전하게 처리"""

    try:
        return int(os.getenv("API_PORT") or "8000")
    except ValueError:
        return 8000

# Flutter Web 등 허용된 클라이언트 Origin을 .env의 API_CORS_ORIGINS에 쉼표로 설정합니다.
cors_origins = [origin.strip() for origin in os.getenv("API_CORS_ORIGINS", "*").split(",") if origin.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins or ["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health", tags=["Health"], summary="서버 상태 확인")
def health() -> dict[str, str]:
    """DB에 접근하지 않고 FastAPI 프로세스 상태만 확인합니다."""

    return {"status": "ok", "service": "bootcamp-gongin-user"}


# 인증 router: 회원가입·로그인 기능을 /auth 하위 경로로 연결합니다.
app.include_router(auth_router, prefix="/auth")
# 공지 router: 사용자 대상 공지의 분류·목록·상세만 읽기 전용으로 제공합니다.
app.include_router(announce_router, prefix="/announce", tags=["User Announcement"])
# 구장 예약 router: 종목별 회원 ID와 구장 코드를 reservation 테이블에 연결합니다.
app.include_router(match_router, prefix="/match", tags=["Ground Reservation"])

# 문의 router: 문의 작성·내 문의 목록 기능을 /inquiry 하위 경로로 연결합니다.
app.include_router(inquiry_router, prefix="/inquiry")

# 취소 router: 회원 예약 취소 기능을 /cancel 하위 경로로 연결합니다.          # 수정 : 신현진 2026.10.23
app.include_router(cancel_router, prefix="/cancel")

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 구장 router (version2): 구장 관련 기능을 /ground 하위 경로로 연결합니다.
#   - 구장 조회 : /ground, /ground/{g_code}  (기존 /match/ground 에서 주소 변경)
#   - 구장 대여 : /ground/reservation/...    (회원·팀장이 비어 있는 시간대에 구장 전체를 빌림, 담당 매니저 지정)
# 실력매칭 예약(/match/reservation)과 같은 시간대에 겹치지 않도록 서로 막습니다.
# /ground 주소는 ground/__init__.py에서 붙이므로 여기서는 prefix 없이 등록합니다.
app.include_router(ground_router)

# 중간 수정 작성자 - 신현진
# 수정일 2026.10.26
# 팀 경기 매칭 router: 팀장끼리 팀 대결을 신청·수락하는 기능을 /team_match 하위 경로로 연결합니다.
#   - 팀장이 구장대여 후 그 대여 내역으로 [매칭신청] 게시글 작성
#   - 다른 팀 팀장이 리스트에서 신청 → 게시글에 신청 댓글 ("요청됨")
#   - 게시글 팀 팀장이 수락 → 대댓글로 수락·성사 기록 + team_match 저장 + 대여 r_check = 1
# /team_match 주소는 team_match/__init__.py에서 붙이므로 여기서는 prefix 없이 등록합니다.
app.include_router(team_match_router)


# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 게시글·댓글 router를 연결하여 Swagger와 앱에서 /board 경로로 사용합니다.
app.include_router(board_router, prefix="/board", tags=["Board"])

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 팀 개설·최초 팀장 등록 API를 /team 하위에 연결합니다.
app.include_router(team_router, prefix="/team", tags=["Team"])
# 제재 router: 내 제재 내역 조회 기능을 /sanction 하위 경로로 연결합니다.   # 수정 : 김병재 2026.10.27
app.include_router(sanction_router, prefix="/sanction")

# 이의신청 router: 이의신청 접수·내 이의신청 내역 기능을 /appeal 하위 경로로 연결합니다.   # 수정 : 김병재 2026.10.27
app.include_router(appeal_router, prefix="/appeal")


if __name__ == "__main__":
    import uvicorn

    # API_HOST와 API_PORT는 프로젝트 루트 .env에서 읽습니다.
    uvicorn.run(
        "FastAPI.main:app",
        host=os.getenv("API_HOST") or "0.0.0.0",
        port=api_port(),
        reload=False,
    )

# 수정 일 : 2026-10-26 / 수정자 : 신현진 (ground router, team_match router 추가)
# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건 (취소 API DELETE CORS 허용)
# 최종 수정 일 : 2026-10-26 / 작업자 : 김병재 (신고 API 라우터 등록)
# 최종 수정 일 : 2026-10-27 / 작업자 : 김병재 (제재 API 라우터 등록)
# 이전 수정 일 : 2026-10-26 / 작업자 : 양태건 (취소 API DELETE CORS 허용) / 수정자 : 신현진 (ground router, team_match router 추가)
# 최종 수정 일 : 2026-10-27 / 수정자 : 최현준 (공지·게시판 router 동시 유지 및 main 충돌 해결)
