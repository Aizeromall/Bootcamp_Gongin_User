# 2026-10-27
# 작업자 : 양태건

"""채팅 로그인 요청 모델과 토큰 발급 router를 함께 관리합니다."""
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import Field, SecretStr

from ..auth.login import verify_password
from ..auth.token import current_account
from .chat_request import ChatRequest
from .chat_room import chat_connection, TOKEN_SECONDS, TOKEN_SECRET, TOKEN_AUDIENCE, TOKEN_ISSUER

router = APIRouter()


# 수정 일 : 2026-10-28 / 작업자 : 최현준
# 간편가입자는 비밀번호가 없으므로 서비스 JWT의 소유 종목만 채팅 토큰으로 교환합니다.
@router.post("/session-token", summary="로그인한 본인의 종목별 채팅 인증", responses={
    401: {"description": "서비스 JWT 누락·만료"}, 403: {"description": "타인 회원 ID"},
    404: {"description": "탈퇴·없는 회원"}, 422: {"description": "회원 ID 형식 오류"},
    500: {"description": "DB 오류"}, 503: {"description": "JWT 설정 오류"},
})
def chat_session_token(c_id_seq: str = Body(embed=True, min_length=1, max_length=50),
                       account: dict = Depends(current_account)):
    if c_id_seq not in account["member_ids"]:
        raise HTTPException(status_code=403, detail="본인 종목의 채팅만 연결할 수 있습니다.")
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT c_id_seq FROM customer WHERE c_id_seq=%s AND c_deletdate IS NULL", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="이용 가능한 회원 정보가 없습니다.")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": c_id_seq, "iat": now, "exp": now + timedelta(seconds=TOKEN_SECONDS),
                        "aud": TOKEN_AUDIENCE, "iss": TOKEN_ISSUER}, TOKEN_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_SECONDS}

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 요청 클래스와 이 클래스를 사용하는 API를 같은 파일로 모았습니다.
class ChatLoginRequest(ChatRequest):
    c_id_seq: str = Field(min_length=1, max_length=50, description="종목별 회원 ID, 예: member_01")
    c_pw: SecretStr = Field(min_length=8, max_length=128)

# 기존 비밀번호 검증 후 채팅 전용 토큰을 발급합니다.
@router.post("/token", summary="채팅 로그인 토큰 발급")
def chat_login(payload: ChatLoginRequest):
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            # 간편가입자의 비밀번호 미지원 표시값은 채팅 비밀번호 로그인에도 사용할 수 없습니다.
            cursor.execute("SELECT c_pw FROM customer WHERE c_id_seq = %s AND c_deletdate IS NULL AND c_login_type = 'local'", (payload.c_id_seq,))
            member = cursor.fetchone()
    if member is None or not verify_password(payload.c_pw.get_secret_value(), member["c_pw"]):
        raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")
    now = datetime.now(timezone.utc)
    token = jwt.encode({"sub": payload.c_id_seq, "iat": now, "exp": now + timedelta(seconds=TOKEN_SECONDS),
                        "aud": TOKEN_AUDIENCE, "iss": TOKEN_ISSUER}, TOKEN_SECRET, algorithm="HS256")
    return {"access_token": token, "token_type": "bearer", "expires_in": TOKEN_SECONDS}

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (간편가입자는 서비스 JWT로 채팅 인증)
