# 작업자 : 최현준
# 최초 작업 일 : 2026-10-27
"""일반 로그인 JWT 발급·검증. FCM 토큰과 회원 인증 토큰은 서로 다릅니다."""

import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .. import database  # .env를 읽은 뒤 요청 시점에 설정을 확인합니다.

security = HTTPBearer(auto_error=False)
AUDIENCE = "gongin-user"
ISSUER = "gongin-user-api"
TOKEN_SECONDS = 1800


def signing_key() -> str:
    """프로세스마다 달라지는 임시 키를 사용하지 않고 잘못된 설정은 차단합니다."""
    key = os.getenv("AUTH_TOKEN_SECRET", "")
    if len(key.encode("utf-8")) < 32:
        raise HTTPException(status_code=503, detail="AUTH_TOKEN_SECRET을 32바이트 이상으로 설정해 주세요.")
    return key


def issue_token(c_id: str, member_ids: list[str]) -> dict:
    if not member_ids:
        raise HTTPException(status_code=401, detail="이용 가능한 회원 정보가 없습니다.")
    now = datetime.now(timezone.utc)
    encoded = jwt.encode(
        {"sub": c_id, "member_ids": member_ids, "c_id_seq": member_ids[0],
         "iat": now, "exp": now + timedelta(seconds=TOKEN_SECONDS),
         "aud": AUDIENCE, "iss": ISSUER},
        signing_key(), algorithm="HS256",
    )
    return {"access_token": encoded, "token_type": "bearer", "expires_in": TOKEN_SECONDS}


def decode_token(encoded: str) -> dict:
    key = signing_key()
    try:
        claims = jwt.decode(
            encoded, key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
            options={"require": ["sub", "member_ids", "c_id_seq", "iat", "exp", "aud", "iss"]},
        )
        members = claims["member_ids"]
        if (not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 45
                or not isinstance(members, list) or not members
                or any(not isinstance(m, str) or not 1 <= len(m) <= 50 for m in members)
                or claims["c_id_seq"] not in members):
            raise ValueError("회원 claim 형식 오류")
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="로그인이 필요하거나 인증 토큰이 만료되었습니다.",
                            headers={"WWW-Authenticate": "Bearer"}) from None


def current_account(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="일반 로그인 Bearer 토큰이 필요합니다.",
                            headers={"WWW-Authenticate": "Bearer"})
    return decode_token(credentials.credentials)

# 최종 수정 일 : 2026-10-27
