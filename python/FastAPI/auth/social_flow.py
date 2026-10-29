# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""OAuth state·가입 티켓의 단기 보관. 단일 API 프로세스 전용이며 재시작 시 폐기됩니다."""

import hashlib
import secrets
import time
from threading import Lock

from fastapi import HTTPException, Request, Response

FLOW_SECONDS = 600
MAX_FLOWS = 2000
_entries = {}
_lock = Lock()


def put_flow(kind: str, data: dict) -> str:
    secret = secrets.token_urlsafe(32)
    key = hashlib.sha256(secret.encode()).hexdigest()
    with _lock:
        now = time.monotonic()
        for expired in [k for k, v in _entries.items() if v["until"] <= now]:
            del _entries[expired]
        if len(_entries) >= MAX_FLOWS:
            raise HTTPException(status_code=503, detail="인증 대기 요청이 많습니다. 잠시 후 다시 시도해 주세요.")
        _entries[key] = {"kind": kind, "data": data, "until": now + FLOW_SECONDS}
    return secret


def take_flow(secret: str, kind: str) -> dict:
    key = hashlib.sha256(secret.encode()).hexdigest()
    with _lock:
        entry = _entries.get(key)
        if entry is None or entry["kind"] != kind or entry["until"] <= time.monotonic():
            raise HTTPException(status_code=400, detail="인증 정보가 만료되었거나 이미 사용되었습니다. 다시 로그인해 주세요.")
        del _entries[key]
    return entry["data"]


def start_state(provider: str, request: Request, response: Response) -> str:
    # state만 탈취해도 다른 브라우저에서 콜백을 완료할 수 없도록 별도 HttpOnly 쿠키와 결합합니다.
    browser = secrets.token_urlsafe(32)
    state = put_flow("oauth:" + provider, {"browser_hash": hashlib.sha256(browser.encode()).hexdigest()})
    response.set_cookie("oauth_" + provider, browser, max_age=FLOW_SECONDS, httponly=True,
                        secure=request.url.scheme == "https", samesite="lax", path="/auth/" + provider)
    response.headers["Cache-Control"] = "no-store"
    return state


def finish_state(provider: str, state: str, request: Request, response: Response) -> None:
    # 쿠키가 없는 호출은 state를 소비하지 않습니다. 정상 쿠키라도 state는 한 번만 사용합니다.
    browser = request.cookies.get("oauth_" + provider)
    if not browser:
        raise HTTPException(status_code=400, detail="로그인을 시작한 브라우저에서 다시 시도해 주세요.")
    key = hashlib.sha256(state.encode()).hexdigest()
    digest = hashlib.sha256(browser.encode()).hexdigest()
    with _lock:
        entry = _entries.get(key)
        if (entry is None or entry["kind"] != "oauth:" + provider
                or entry["until"] <= time.monotonic()
                or not secrets.compare_digest(entry["data"]["browser_hash"], digest)):
            raise HTTPException(status_code=400, detail="로그인 요청을 확인할 수 없거나 만료되었습니다.")
        del _entries[key]
    response.delete_cookie("oauth_" + provider, path="/auth/" + provider)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"

# 최종 수정 일 : 2026-10-28
