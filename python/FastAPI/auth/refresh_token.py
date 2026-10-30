# 2026-10-30
# 작업자 : 김병재

"""일반 로그인 JWT 갱신 router입니다. 기존 로그인·토큰 발급 코드는 변경하지 않고 재사용만 합니다."""

from datetime import timedelta

import jwt
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from .account_lifecycle import account_db, authentication_result, load_members, owned_active
from .token import AUDIENCE, ISSUER, security, signing_key

router = APIRouter()

# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 만료된 JWT도 이 기간 안이면 다시 발급합니다. 앱을 30분 넘게 꺼 두어도 재로그인 없이 이어서 사용합니다.
# 갱신할 때마다 새 토큰 기준으로 다시 30일이 주어지므로, 30일 안에 한 번이라도 앱을 쓰면 로그인이 계속 유지됩니다.
# 기간이 지나면 401을 반환하며 앱에서 다시 로그인해야 합니다. (발표용 설정: 서버 측 토큰 폐기 기능은 없음)
REFRESH_GRACE_SECONDS = 30 * 24 * 60 * 60

REFRESH_ERRORS = {
    401: {"description": "토큰 누락·위조, 또는 만료 후 갱신 가능 기간(30일) 경과"},
    403: {"description": "토큰의 종목이 모두 삭제 신청 등으로 비활성"},
    404: {"description": "회원 정보 없음"},
    409: {"description": "회원 식별자·로그인 방식 충돌"},
    500: {"description": "회원 DB 조회 실패"},
    503: {"description": "AUTH_TOKEN_SECRET 미설정"},
}


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 서명·발급자·용도(audience)는 기존 decode_token과 같은 기준으로 검증하고 만료 시각만 유예합니다.
def decode_expired_token(encoded: str) -> dict:
    key = signing_key()
    try:
        claims = jwt.decode(
            encoded, key, algorithms=["HS256"], audience=AUDIENCE, issuer=ISSUER,
            leeway=timedelta(seconds=REFRESH_GRACE_SECONDS),
            options={"require": ["sub", "member_ids", "c_id_seq", "iat", "exp", "aud", "iss"]},
        )
        members = claims["member_ids"]
        if (not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 45
                or not isinstance(members, list) or not members
                or any(not isinstance(m, str) or not 1 <= len(m) <= 50 for m in members)):
            raise ValueError("회원 claim 형식 오류")
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="로그인 정보가 만료되었습니다. 다시 로그인해 주세요.",
                            headers={"WWW-Authenticate": "Bearer"}) from None


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 토큰 갱신: DB에서 현재 활성 종목을 다시 확인한 뒤 로그인 응답과 같은 형식으로 새 JWT를 반환합니다.
# 삭제 신청·탈퇴한 종목은 새 토큰의 member_ids에서 빠지며, 활성 종목이 없으면 403입니다.
@router.post("/refresh", responses=REFRESH_ERRORS, summary="로그인 토큰 갱신 (만료 후 30일까지)")
def refresh_token(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="일반 로그인 Bearer 토큰이 필요합니다.",
                            headers={"WWW-Authenticate": "Bearer"})
    claims = decode_expired_token(credentials.credentials)
    # 읽기 전용 조회입니다. account_db 기본값(write=False)으로 commit하지 않습니다.
    with account_db() as connection, connection.cursor() as cursor:
        rows = load_members(cursor, claims["sub"])
    # 토큰 발급 당시 본인 종목 중 하나라도 활성 상태여야 갱신합니다.
    owned_active(rows, claims)
    return authentication_result(claims["sub"], rows[0]["c_login_type"], rows)

# 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
