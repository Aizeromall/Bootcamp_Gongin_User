# 작업자 : 최현준
# 최초 작업 일 : 2026-10-23

"""인증 API router를 하나로 묶어 main.py에 전달합니다."""

from fastapi import APIRouter

from .login import router as login_router
from .register import router as register_router

# main.py의 prefix="/auth"와 결합해 /auth/register, /auth/login 경로를 생성합니다.
auth_router = APIRouter()
# 회원가입: customer 테이블에 선택 종목별 회원 데이터를 생성합니다.
auth_router.include_router(register_router, tags=["Auth Register"])
# 로그인: c_id_seq, c_pw로 회원을 인증하고 선호 종목을 반환합니다.
auth_router.include_router(login_router, tags=["Auth Login"])

# 최종 수정 일 : 2026-10-23
