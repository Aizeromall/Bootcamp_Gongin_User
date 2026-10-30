# 2026-10-30
# 작업자 : 김병재

"""로그인 토큰 갱신 API 검증. DB는 mock이며 실제 DB 쓰기는 실행하지 않습니다."""
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.auth import account_lifecycle, token
from python.FastAPI.auth.refresh_token import router

TEST_KEY = "test-only-not-a-production-secret-12345678"


def client():
    app = FastAPI()
    app.include_router(router, prefix="/auth")
    return TestClient(app)


def member(c_id_seq, deleted=None):
    return {"c_id_seq": c_id_seq, "c_login_type": "local", "c_pw": "hash", "c_name": "회원",
            "c_prefer_stock": c_id_seq[-1], "c_signupdate": datetime(2026, 10, 1), "c_deletdate": deleted}


def database_mock(rows):
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = rows
    return connection, cursor


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 만료 시각만 바꾼 로그인 JWT를 만듭니다. 서명·audience·issuer는 실제 발급과 같습니다.
def login_jwt(expired_ago, key=TEST_KEY, **changes):
    now = datetime.now(timezone.utc)
    claims = {"sub": "member", "member_ids": ["member_01", "member_02"], "c_id_seq": "member_01",
              "iat": now - expired_ago - timedelta(seconds=token.TOKEN_SECONDS),
              "exp": now - expired_ago, "aud": token.AUDIENCE, "iss": token.ISSUER, **changes}
    return jwt.encode(claims, key, algorithm="HS256")


def test_expired_token_within_grace_is_reissued_from_current_members():
    connection, cursor = database_mock([member("member_01"), member("member_02"), member("member_03")])
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api, \
            patch.object(account_lifecycle, "connect", return_value=connection):
        # 만료 후 29일 지난 토큰도 30일 유예 안이므로 갱신됩니다.
        response = api.post("/auth/refresh",
                            headers={"Authorization": "Bearer " + login_jwt(timedelta(days=29))})
        assert response.status_code == 200, response.text
        body = response.json()
        # 새 토큰은 DB의 현재 활성 종목 기준이며 로그인 응답과 같은 형식입니다.
        assert body["c_id"] == "member"
        assert body["member_ids"] == ["member_01", "member_02", "member_03"]
        claims = token.decode_token(body["access_token"])
        assert claims["member_ids"] == ["member_01", "member_02", "member_03"]
        sql, params = cursor.execute.call_args.args
        assert sql.strip().startswith("SELECT")
        assert params == ("member_01", "member_02", "member_03", "member_04")
        connection.commit.assert_not_called()
        connection.close.assert_called_once()


def test_deleted_sport_is_removed_and_all_deleted_is_rejected():
    connection, _ = database_mock([member("member_01", deleted=datetime(2026, 10, 29)), member("member_02")])
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api, \
            patch.object(account_lifecycle, "connect", return_value=connection):
        headers = {"Authorization": "Bearer " + login_jwt(timedelta(minutes=1))}
        assert api.post("/auth/refresh", headers=headers).json()["member_ids"] == ["member_02"]
        # 토큰의 종목이 모두 삭제 신청 상태면 새 토큰을 발급하지 않습니다.
        connection.cursor.return_value.__enter__.return_value.fetchall.return_value = [
            member("member_01", deleted=datetime(2026, 10, 29)), member("member_02", deleted=datetime(2026, 10, 29))]
        assert api.post("/auth/refresh", headers=headers).status_code == 403


def test_rejects_old_forged_wrong_audience_and_missing_token():
    # 수정 일 : 2026-10-30 / 작업자 : 김병재 — 갱신 가능 기간 30일 경과(31일) 토큰은 거절
    variants = [login_jwt(timedelta(days=31)),
                login_jwt(timedelta(hours=1), key="wrong-signing-key-with-32-or-more-bytes"),
                login_jwt(timedelta(hours=1), aud="gongin-account-recovery"),
                login_jwt(timedelta(hours=1), member_ids=[])]
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api, \
            patch.object(account_lifecycle, "connect") as connect:
        for encoded in variants:
            assert api.post("/auth/refresh", headers={"Authorization": "Bearer " + encoded}).status_code == 401
        assert api.post("/auth/refresh").status_code == 401
        # 검증에 실패한 토큰으로는 DB에 접근하지 않습니다.
        connect.assert_not_called()


def test_missing_signing_key_is_explicit():
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=""), client() as api:
        assert api.post("/auth/refresh", headers={"Authorization": "Bearer x"}).status_code == 503


def load_tests(loader, tests, pattern):
    # 기존 test_notification_auth.py와 같이 함수형 테스트를 unittest로 실행합니다.
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
