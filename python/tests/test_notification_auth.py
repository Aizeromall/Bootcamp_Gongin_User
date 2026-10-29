# 작업자 : 최현준
# 최초 작업 일 : 2026-10-27
"""실제 DB·FCM 발송 없이 일반 JWT와 기기 등록의 권한 경계를 검증합니다."""

import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.auth import login as login_module
from python.FastAPI.auth import token
from python.FastAPI.chat.chat_room import decode_chat_token
from python.FastAPI.notification import device

TEST_KEY = "test-only-not-a-production-secret-12345678"


def client():
    app = FastAPI()
    app.include_router(login_module.router, prefix="/auth")
    app.include_router(device.router)
    return TestClient(app)


def database_mock():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"c_id_seq": "member_01"}
    return connection, cursor


def test_login_preserves_response_and_issues_exact_members():
    connection, cursor = database_mock()
    cursor.fetchall.return_value = [
        {"c_id_seq": "member_01", "c_pw": "hash", "c_name": "회원", "c_prefer_stock": 1},
        {"c_id_seq": "member_03", "c_pw": "hash", "c_name": "회원", "c_prefer_stock": 3},
    ]
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api:
        with patch.object(login_module, "connect", return_value=connection), \
                patch.object(login_module, "verify_password", return_value=True):
            response = api.post("/auth/login", json={"c_id": "member", "c_pw": "password123"})
        assert response.status_code == 200
        body = response.json()
        assert body["result"] == "OK" and body["preferred_stocks"] == [1, 3]
        claims = token.decode_token(body["access_token"])
        assert claims["sub"] == "member"
        assert claims["member_ids"] == ["member_01", "member_03"]
        assert decode_chat_token(body["access_token"])["sub"] == "member_01"
        assert cursor.execute.call_args.args[1] == ("member_01", "member_02", "member_03", "member_04")
        # 삭제 대기 행도 본인 인증 후 복구 여부를 판정하므로 SQL에서 숨기지 않습니다.
        assert "c_deletdate" in cursor.execute.call_args.args[0]
        assert "c_deletdate IS NULL" not in cursor.execute.call_args.args[0]
        connection.close.assert_called_once()


def test_invalid_login_does_not_issue_token():
    connection, cursor = database_mock()
    cursor.fetchall.return_value = []
    with client() as api, patch.object(login_module, "connect", return_value=connection):
        assert api.post("/auth/login", json={"c_id": "missing", "c_pw": "password123"}).status_code == 401


def test_device_validation_and_ownership():
    connection, cursor = database_mock()
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api:
        headers = {"Authorization": "Bearer " + token.issue_token("member", ["member_01"])["access_token"]}
        with patch.object(device, "connect", return_value=connection) as connect:
            assert api.post("/notifications/devices", json={"f_token": "sample", "f_platform": "android"}).status_code == 401
            connect.assert_not_called()
            assert api.post("/notifications/devices", headers=headers, json={
                "f_token": "sample", "f_platform": "android", "c_id_seq": "other_01"}).status_code == 403
            connection.rollback.assert_called_once()
            for value in ["", "has space", "한글", "a" * 2049, None]:
                assert api.post("/notifications/devices", headers=headers, json={
                    "f_token": value, "f_platform": "android"}).status_code == 422
            assert api.post("/notifications/devices", headers=headers, json={
                "f_token": "test-token", "f_platform": "unknown"}).status_code == 422
            response = api.post("/notifications/devices", headers=headers, json={
                "f_token": "test-token", "f_platform": "android"})
            assert response.status_code == 200
            assert "test-token" not in response.text
            assert cursor.execute.call_args.args[1] == ("member_01", "test-token", "android")
            connection.commit.assert_called_once()


def test_deleted_member_and_database_failure():
    connection, cursor = database_mock()
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api:
        headers = {"Authorization": "Bearer " + token.issue_token("member", ["member_01"])["access_token"]}
        cursor.fetchone.return_value = None
        with patch.object(device, "connect", return_value=connection):
            assert api.post("/notifications/devices", headers=headers, json={
                "f_token": "test-token", "f_platform": "ios"}).status_code == 404
        with patch.object(device, "connect", side_effect=RuntimeError("sensitive database error")):
            response = api.post("/notifications/devices", headers=headers, json={"f_token": "test-token", "f_platform": "web"})
            assert response.status_code == 500 and "sensitive" not in response.text


def test_deactivation_uses_only_signed_member_ids():
    connection, cursor = database_mock()
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api:
        headers = {"Authorization": "Bearer " + token.issue_token("member", ["member_01", "member_03"])["access_token"]}
        with patch.object(device, "connect", return_value=connection):
            assert api.post("/notifications/devices/deactivate", headers=headers, json={"f_token": "test-token"}).status_code == 200
            assert cursor.execute.call_args.args[1] == ("test-token", "member_01", "member_03")


def test_expired_forged_wrong_audience_and_missing_claims():
    now = datetime.now(timezone.utc)
    valid = {"sub": "member", "c_id_seq": "member_01", "member_ids": ["member_01"],
             "iat": now, "exp": now + timedelta(minutes=10), "aud": token.AUDIENCE, "iss": token.ISSUER}
    variants = [({**valid, "exp": now - timedelta(seconds=1)}, TEST_KEY),
                ({**valid, "aud": "other-service"}, TEST_KEY),
                ({k: v for k, v in valid.items() if k != "exp"}, TEST_KEY),
                ({**valid, "member_ids": []}, TEST_KEY), (valid, "wrong-signing-key-with-32-or-more-bytes")]
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY), client() as api, patch.object(device, "connect") as connect:
        for claims, key in variants:
            encoded = jwt.encode(claims, key, algorithm="HS256")
            assert api.post("/notifications/devices", headers={"Authorization": "Bearer " + encoded}, json={
                "f_token": "test-token", "f_platform": "android"}).status_code == 401
        connect.assert_not_called()


def test_missing_configuration_is_explicit_and_swagger_is_available():
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=""), client() as api:
        response = api.post("/notifications/devices", headers={"Authorization": "Bearer invalid"}, json={
            "f_token": "test-token", "f_platform": "android"})
        assert response.status_code == 503
        assert api.get("/docs").status_code == 200
        spec = api.get("/openapi.json").json()
        errors = spec["paths"]["/notifications/devices"]["post"]["responses"]
        assert all(str(code) in errors for code in [200, 401, 403, 404, 422, 500, 503])


def load_tests(loader, tests, pattern):
    # 함수형 테스트를 unittest로 실행합니다. 사용자 승인 없는 새 테스트 클래스도 만들지 않습니다.
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-27
# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준 (삭제 대기 회원 로그인 SQL 계약 검증)
