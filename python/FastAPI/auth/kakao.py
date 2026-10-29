# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""카카오 REST 인가 코드 로그인. 브라우저에서 동의 후 서버 콜백으로 돌아옵니다."""

from urllib.parse import urlencode

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response

from .social_account import finish_identity
from .social_flow import start_state, finish_state, FLOW_SECONDS
from .social_http import setting, redirect_uri, provider_request, access_token, SOCIAL_ERRORS
from .token import signing_key

router = APIRouter(prefix="/kakao", tags=["Auth Kakao"])


# 수정 일 : 2026-10-28 / 작업자 : 최현준
# 앱이 보낸 회원 ID를 신뢰하지 않고 공급자 서버의 토큰 소유자와 앱 ID를 검증합니다.
@router.post("/mobile", responses=SOCIAL_ERRORS, summary="카카오 모바일 SDK 토큰 로그인")
def mobile_kakao(response: Response,
                 access_token: str = Body(embed=True, min_length=1, max_length=4096)) -> dict:
    signing_key()
    expected_app = setting("KAKAO_APP_ID")
    info = provider_request("GET", "https://kapi.kakao.com/v1/user/access_token_info",
                            headers={"Authorization": "Bearer " + access_token})
    subject = info.get("id")
    if (isinstance(subject, bool) or not isinstance(subject, int) or subject <= 0
            or str(info.get("app_id")) != expected_app
            or isinstance(info.get("expires_in"), bool)
            or not isinstance(info.get("expires_in"), int) or info["expires_in"] <= 0):
        raise HTTPException(status_code=401, detail="이 앱에서 발급한 유효한 카카오 인증이 필요합니다.")
    response.headers["Cache-Control"] = "no-store"
    return finish_identity("kakao", str(subject))


@router.get("/login", responses=SOCIAL_ERRORS, summary="카카오 로그인 시작 URL 발급")
def start_kakao(request: Request, response: Response) -> dict:
    signing_key()
    client_id = setting("KAKAO_REST_API_KEY")
    setting("KAKAO_CLIENT_SECRET")
    uri = redirect_uri("kakao")
    state = start_state("kakao", request, response)
    return {"authorization_url": "https://kauth.kakao.com/oauth/authorize?" + urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": uri, "state": state}),
        "expires_in": FLOW_SECONDS}


@router.get("/callback", responses=SOCIAL_ERRORS, summary="카카오 인증 결과 콜백 (직접 입력용 아님)")
def kakao_callback(request: Request, response: Response,
                   state: str = Query(min_length=1, max_length=256),
                   code: str | None = Query(default=None, min_length=1, max_length=4096),
                   error: str | None = Query(default=None, max_length=256)) -> dict:
    finish_state("kakao", state, request, response)
    if error is not None or not code:
        raise HTTPException(status_code=400, detail="카카오 로그인이 취소되었거나 인증 코드가 없습니다.")
    tokens = provider_request("POST", "https://kauth.kakao.com/oauth/token", data={
        "grant_type": "authorization_code", "client_id": setting("KAKAO_REST_API_KEY"),
        "client_secret": setting("KAKAO_CLIENT_SECRET"), "redirect_uri": redirect_uri("kakao"), "code": code})
    profile = provider_request("GET", "https://kapi.kakao.com/v2/user/me",
                               headers={"Authorization": "Bearer " + access_token(tokens)})
    subject = profile.get("id")
    if isinstance(subject, bool) or not isinstance(subject, int) or subject <= 0:
        raise HTTPException(status_code=502, detail="카카오 회원 고유 ID를 확인할 수 없습니다.")
    return finish_identity("kakao", str(subject))

# 최종 수정 일 : 2026-10-28
