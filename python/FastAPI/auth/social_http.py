# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""고정된 공급자 HTTPS 주소만 호출하며 토큰·secret·응답 원문을 로그에 남기지 않습니다."""

import os
from urllib.parse import urlsplit

import httpx
from fastapi import HTTPException

SOCIAL_ERRORS = {
    400: {"description": "state·쿠키·가입 티켓 만료/재사용 또는 로그인 동의 취소"},
    401: {"description": "공급자 인증 실패·위조·만료 또는 Google 이외의 Firebase 인증"},
    403: {"description": "탈퇴한 계정"},
    409: {"description": "기존 회원·계정 충돌 또는 중복 가입"},
    422: {"description": "필수 입력값·종목·포지션 검증 실패"},
    500: {"description": "회원 DB 처리 실패"},
    502: {"description": "공급자 응답 형식 또는 API 오류"},
    503: {"description": "서버 설정 누락·공급자 연결 실패·요청 과다"},
}


def setting(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=503, detail=f"서버의 {name} 설정이 필요합니다.")
    return value


def redirect_uri(provider: str) -> str:
    value = setting(provider.upper() + "_REDIRECT_URI")
    parsed = urlsplit(value)
    if (parsed.scheme not in ("https", "http") or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path != "/auth/" + provider + "/callback"):
        raise HTTPException(status_code=503, detail="서버의 로그인 콜백 주소 설정을 확인해 주세요.")
    # HTTP는 로컬/LAN 개발용입니다. 운영 서버·기기 통신은 HTTPS로 구성해야 합니다.
    return value


def provider_request(method: str, url: str, **kwargs) -> dict:
    try:
        with httpx.Client(timeout=10, follow_redirects=False) as client:
            response = client.request(method, url, **kwargs)
        if response.status_code in (400, 401, 403):
            raise HTTPException(status_code=401, detail="공급자 로그인 인증에 실패했습니다. 다시 로그인해 주세요.")
        if response.status_code == 429 or response.status_code >= 500:
            raise HTTPException(status_code=503, detail="공급자 인증 서비스를 잠시 사용할 수 없습니다.")
        if response.status_code != 200:
            raise HTTPException(status_code=502, detail="공급자 인증 응답을 확인할 수 없습니다.")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("JSON object required")
        return payload
    except HTTPException:
        raise
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="공급자 인증 서비스에 연결하지 못했습니다.") from None
    except ValueError:
        raise HTTPException(status_code=502, detail="공급자 인증 응답 형식이 올바르지 않습니다.") from None


def access_token(payload: dict) -> str:
    value = payload.get("access_token")
    if not isinstance(value, str) or not value:
        raise HTTPException(status_code=401, detail="공급자 인증 토큰을 발급받지 못했습니다.")
    return value

# 최종 수정 일 : 2026-10-28
