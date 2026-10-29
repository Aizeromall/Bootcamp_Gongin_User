# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""인증 API router를 하나로 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .login import router as login_router
from .register import router as register_router
from .google import router as google_router
from .kakao import router as kakao_router
from .naver import router as naver_router
from .social_account import router as social_register_router
from .account import router as account_router

# main.py의 prefix="/auth"와 결합해 /auth/register, /auth/login 경로를 생성합니다.
auth_router = APIRouter()
# 회원가입: customer 테이블에 선택 종목별 회원 데이터를 생성합니다.
auth_router.include_router(register_router, tags=["Auth Register"])
# 로그인: c_id_seq, c_pw로 회원을 인증하고 선호 종목을 반환합니다.
auth_router.include_router(login_router, tags=["Auth Login"])
# 공급자별 인증 → 기존 회원 JWT 또는 신규 가입 티켓 → 추가 정보 입력 순서입니다.
auth_router.include_router(google_router)
auth_router.include_router(kakao_router)
auth_router.include_router(naver_router)
auth_router.include_router(social_register_router, tags=["Auth Social Register"])
# 프로필 및 종목 생명주기 router: main.py의 /auth prefix 아래에 연결합니다.
auth_router.include_router(account_router)

# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
