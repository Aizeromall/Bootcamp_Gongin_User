# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""네이버 REST 인가 코드 로그인. state와 시작 브라우저 쿠키를 함께 검증합니다."""

from urllib.parse import urlencode

from fastapi import APIRouter, Body, HTTPException, Query, Request, Response

from .social_account import finish_identity
from .social_flow import start_state, finish_state, FLOW_SECONDS
from .social_http import setting, redirect_uri, provider_request, access_token, SOCIAL_ERRORS
from .token import signing_key

router = APIRouter(prefix="/naver", tags=["Auth Naver"])


# 수정 일 : 2026-10-28 / 작업자 : 최현준
# 회원 ID는 앱 입력값이 아닌 네이버 프로필 API의 검증된 응답만 사용합니다.
@router.post("/mobile", responses=SOCIAL_ERRORS, summary="네이버 모바일 SDK 토큰 로그인")
def mobile_naver(response: Response,
                 access_token: str = Body(embed=True, min_length=1, max_length=4096)) -> dict:
    signing_key()
    profile = provider_request("GET", "https://openapi.naver.com/v1/nid/me",
                               headers={"Authorization": "Bearer " + access_token})
    member = profile.get("response")
    subject = member.get("id") if isinstance(member, dict) else None
    if profile.get("resultcode") != "00" or not isinstance(subject, str) or not subject.strip():
        raise HTTPException(status_code=401, detail="유효한 네이버 인증이 필요합니다.")
    response.headers["Cache-Control"] = "no-store"
    return finish_identity("naver", subject)


@router.get("/login", responses=SOCIAL_ERRORS, summary="네이버 로그인 시작 URL 발급")
def start_naver(request: Request, response: Response) -> dict:
    signing_key()
    client_id = setting("NAVER_CLIENT_ID")
    setting("NAVER_CLIENT_SECRET")
    uri = redirect_uri("naver")
    state = start_state("naver", request, response)
    return {"authorization_url": "https://nid.naver.com/oauth2.0/authorize?" + urlencode({
        "response_type": "code", "client_id": client_id, "redirect_uri": uri, "state": state}),
        "expires_in": FLOW_SECONDS}


@router.get("/callback", responses=SOCIAL_ERRORS, summary="네이버 인증 결과 콜백 (직접 입력용 아님)")
def naver_callback(request: Request, response: Response,
                   state: str = Query(min_length=1, max_length=256),
                   code: str | None = Query(default=None, min_length=1, max_length=4096),
                   error: str | None = Query(default=None, max_length=256)) -> dict:
    finish_state("naver", state, request, response)
    if error is not None or not code:
        raise HTTPException(status_code=400, detail="네이버 로그인이 취소되었거나 인증 코드가 없습니다.")
    tokens = provider_request("POST", "https://nid.naver.com/oauth2.0/token", data={
        "grant_type": "authorization_code", "client_id": setting("NAVER_CLIENT_ID"),
        "client_secret": setting("NAVER_CLIENT_SECRET"), "code": code, "state": state})
    profile = provider_request("GET", "https://openapi.naver.com/v1/nid/me",
                               headers={"Authorization": "Bearer " + access_token(tokens)})
    member = profile.get("response")
    subject = member.get("id") if isinstance(member, dict) else None
    if profile.get("resultcode") != "00" or not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=502, detail="네이버 회원 고유 ID를 확인할 수 없습니다.")
    return finish_identity("naver", subject)

# 최종 수정 일 : 2026-10-28
