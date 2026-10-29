# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""Firebase Google 로그인 결과 검증. FCM 기기 토큰이나 원본 Google 토큰을 받는 API가 아닙니다."""

from threading import Lock

import firebase_admin
from firebase_admin import auth
from firebase_admin import exceptions as firebase_errors
from fastapi import APIRouter, Body, HTTPException, Response

from .social_account import finish_identity
from .social_http import setting, SOCIAL_ERRORS

router = APIRouter(prefix="/google", tags=["Auth Google"])
_app_lock = Lock()


def firebase_app():
    project = setting("FIREBASE_PROJECT_ID")
    # 프로젝트별 이름으로 초기화하여 FCM 등 다른 Firebase Admin 앱과 설정 충돌을 피합니다.
    name = "gongin-social-" + project
    try:
        with _app_lock:
            try:
                return firebase_admin.get_app(name)
            except ValueError:
                return firebase_admin.initialize_app(options={"projectId": project}, name=name)
    except Exception:
        raise HTTPException(status_code=503, detail="Firebase 서버 자격 증명 설정을 확인해 주세요.") from None


def verified_google_subject(id_token: str) -> str:
    app = firebase_app()
    try:
        claims = auth.verify_id_token(id_token, app=app, check_revoked=True)
    except (auth.CertificateFetchError, firebase_errors.UnavailableError):
        raise HTTPException(status_code=503, detail="Firebase 인증 서비스를 사용할 수 없습니다.") from None
    except (auth.InvalidIdTokenError, auth.RevokedIdTokenError, auth.UserDisabledError,
            auth.UserNotFoundError, ValueError):
        raise HTTPException(status_code=401, detail="Google 인증이 만료되었거나 올바르지 않습니다.") from None
    except Exception:
        raise HTTPException(status_code=503, detail="Firebase 인증 연결 또는 서버 권한을 확인해 주세요.") from None
    firebase = claims.get("firebase")
    if not isinstance(firebase, dict) or firebase.get("sign_in_provider") != "google.com":
        raise HTTPException(status_code=401, detail="Google로 로그인한 Firebase ID 토큰이 필요합니다.")
    identities = firebase.get("identities", {})
    subjects = identities.get("google.com") if isinstance(identities, dict) else None
    if not isinstance(subjects, list) or len(subjects) != 1 or not isinstance(subjects[0], str) or not subjects[0]:
        raise HTTPException(status_code=401, detail="Google 공급자 고유 ID를 확인할 수 없습니다.")
    return subjects[0]


@router.post("/login", responses=SOCIAL_ERRORS, summary="Google Firebase ID 토큰으로 간편로그인")
def login_google(response: Response,
                 id_token: str = Body(embed=True, min_length=1, max_length=16384,
                                      description="앱의 FirebaseAuth.currentUser.getIdToken() 반환값")) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return finish_identity("google", verified_google_subject(id_token))

# 최종 수정 일 : 2026-10-28
