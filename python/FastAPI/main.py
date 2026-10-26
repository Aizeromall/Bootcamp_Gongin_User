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
    from FastAPI.inquiry.inquiry import router as inquiry_router
    from FastAPI.match import match_router
    from FastAPI.cancel import cancel_router                # 수정 : 신현진 2026.10.23
else:
    # `python -m FastAPI.main` 모듈 실행에서는 일반 상대 import를 사용합니다.
    from .auth import auth_router
    from .inquiry.inquiry import router as inquiry_router
    from .match import match_router
    from .cancel import cancel_router                       # 수정 : 신현진 2026.10.23

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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.get("/health", tags=["Health"], summary="서버 상태 확인")
def health() -> dict[str, str]:
    """DB에 접근하지 않고 FastAPI 프로세스 상태만 확인합니다."""

    return {"status": "ok", "service": "bootcamp-gongin-user"}


# 인증 router: 회원가입·로그인 기능을 /auth 하위 경로로 연결합니다.
app.include_router(auth_router, prefix="/auth")
# 구장 예약 router: 종목별 회원 ID와 구장 코드를 reservation 테이블에 연결합니다.
app.include_router(match_router, prefix="/match", tags=["Ground Reservation"])

# 문의 router: 문의 작성·내 문의 목록 기능을 /inquiry 하위 경로로 연결합니다.
app.include_router(inquiry_router, prefix="/inquiry")

# 취소 router: 회원 예약 취소 기능을 /cancel 하위 경로로 연결합니다.          # 수정 : 신현진 2026.10.23
app.include_router(cancel_router, prefix="/cancel")


if __name__ == "__main__":
    import uvicorn

    # API_HOST와 API_PORT는 프로젝트 루트 .env에서 읽습니다.
    uvicorn.run(
        "FastAPI.main:app",
        host=os.getenv("API_HOST") or "0.0.0.0",
        port=api_port(),
        reload=False,
    )

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건 (취소 API DELETE CORS 허용)
