# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""실제 공급자 호출·DB 쓰기 없이 세 공급자의 router·가입·보안 경계를 검사합니다."""

import os
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch
from urllib.parse import parse_qs, urlsplit

import httpx
import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from python.FastAPI.auth import auth_router, google, kakao, naver, social_account as accounts
from python.FastAPI.auth import social_flow as flows, social_http, register, login
from python.FastAPI.auth.token import decode_token

ENV = {"AUTH_TOKEN_SECRET": "test-only-social-secret-with-at-least-32-bytes",
       "FIREBASE_PROJECT_ID": "test-project",
       "KAKAO_REST_API_KEY": "test-kakao", "KAKAO_CLIENT_SECRET": "test-kakao-secret",
       "KAKAO_REDIRECT_URI": "http://testserver/auth/kakao/callback",
       "NAVER_CLIENT_ID": "test-naver", "NAVER_CLIENT_SECRET": "test-naver-secret",
       "NAVER_REDIRECT_URI": "http://testserver/auth/naver/callback"}


@contextmanager
def harness():
    app = FastAPI()
    app.include_router(auth_router, prefix="/auth")
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = None
    with flows._lock:
        flows._entries.clear()
    with patch.dict(os.environ, ENV), patch.object(accounts, "connect", return_value=connection), TestClient(app) as api:
        yield api, connection, cursor
    with flows._lock:
        flows._entries.clear()


def signup_payload(ticket):
    return {"signup_ticket": ticket, "c_name": "회원", "c_address": "서울",
            "c_phone": "01012345678", "c_gender": "남성", "c_birthday": "2000-01-01",
            "preferred_stocks": [3, 1], "c_position": {"1": "FW", "3": "투수"}}


def start(api, provider):
    response = api.get(f"/auth/{provider}/login")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    state = parse_qs(urlsplit(response.json()["authorization_url"]).query)["state"][0]
    return state


def test_full_hash_id_is_stable_and_fits_existing_pk_and_jwt():
    for provider, prefix in [("google", "g_"), ("kakao", "k_"), ("naver", "n_")]:
        base = accounts.social_base(provider, "long-original-provider-id" * 20)
        assert len(base) == 45 and len(base + "_04") == 48 and base.startswith(prefix)
        assert base == accounts.social_base(provider, "long-original-provider-id" * 20)
        assert base != accounts.social_base(provider, "different-user")
    assert accounts.social_base("google", "123") != accounts.social_base("kakao", "123")


def test_kakao_callback_and_atomic_signup_without_user_password():
    with harness() as (api, connection, cursor):
        state = start(api, "kakao")
        with patch.object(kakao, "provider_request", side_effect=[{"access_token": "provider-token"}, {"id": 12345}]) as request:
            response = api.get("/auth/kakao/callback", params={"state": state, "code": "test-code"})
        assert response.status_code == 200, response.text
        assert request.call_args_list[0].kwargs["data"]["client_secret"] == ENV["KAKAO_CLIENT_SECRET"]
        assert "provider-token" not in response.text
        body = response.json()
        assert body["signup_required"] and "access_token" not in body
        response = api.post("/auth/social/register", json=signup_payload(body["signup_ticket"]))
        assert response.status_code == 201, response.text
        result = response.json()
        assert result["preferred_stocks"] == [1, 3]
        assert result["c_login_type"] == "kakao" and not result["signup_required"]
        assert decode_token(result["access_token"])["member_ids"] == result["member_ids"]
        rows = cursor.executemany.call_args.args[1]
        assert len(rows) == 2 and rows[0][0].endswith("_01") and rows[1][0].endswith("_03")
        assert all(row[1] == "kakao" and row[3] == accounts.PASSWORD_UNSUPPORTED and row[-1] == 1500 for row in rows)
        assert all(row[9] == "무소속" for row in rows)
        assert "c_category" not in cursor.executemany.call_args.args[0]
        assert api.post("/auth/social/register", json=signup_payload(body["signup_ticket"])).status_code == 400
        connection.rollback.assert_not_called()


def test_naver_existing_member_login_and_provider_binding():
    with harness() as (api, connection, cursor):
        base = accounts.social_base("naver", "naver-user")
        cursor.fetchall.return_value = [{"c_id_seq": base + "_04", "c_login_type": "naver",
                                        "c_name": "회원", "c_prefer_stock": "4", "c_deletdate": None}]
        state = start(api, "naver")
        with patch.object(naver, "provider_request", side_effect=[{"access_token": "provider-token"},
                                 {"resultcode": "00", "response": {"id": "naver-user"}}]):
            response = api.get("/auth/naver/callback", params={"state": state, "code": "code"})
        assert response.status_code == 200, response.text
        assert response.json()["member_ids"] == [base + "_04"]
        cursor.executemany.assert_not_called()


def test_state_missing_wrong_browser_provider_replay_and_expiry():
    with harness() as (api, connection, cursor):
        state = start(api, "kakao")
        saved = api.cookies.get("oauth_kakao")
        api.cookies.clear()
        with patch.object(kakao, "provider_request") as request:
            assert api.get("/auth/kakao/callback", params={"state": state, "code": "code"}).status_code == 400
            api.cookies.set("oauth_kakao", "wrong-cookie")
            assert api.get("/auth/kakao/callback", params={"state": state, "code": "code"}).status_code == 400
            api.cookies.clear()
            api.cookies.set("oauth_kakao", saved)
            assert api.get("/auth/kakao/callback", params={"state": "wrong-state", "code": "code"}).status_code == 400
            # 같은 state를 다른 공급자의 콜백으로 전용할 수 없습니다.
            api.cookies.set("oauth_naver", saved)
            assert api.get("/auth/naver/callback", params={"state": state, "code": "code"}).status_code == 400
            assert api.get("/auth/kakao/callback", params={"state": state, "error": "access_denied"}).status_code == 400
            assert api.get("/auth/kakao/callback", params={"state": state, "code": "code"}).status_code == 400
            request.assert_not_called()
        expired = start(api, "kakao")
        with flows._lock:
            for entry in flows._entries.values():
                entry["until"] = 0
        assert api.get("/auth/kakao/callback", params={"state": expired, "code": "code"}).status_code == 400
        cursor.execute.assert_not_called()


def test_google_requires_verified_google_provider_and_returns_signup_ticket():
    with harness() as (api, connection, cursor), patch.object(google, "firebase_app", return_value=MagicMock()), \
            patch.object(google.auth, "verify_id_token") as verify:
        verify.return_value = {"firebase": {"sign_in_provider": "google.com", "identities": {"google.com": ["google-sub"]}}}
        response = api.post("/auth/google/login", json={"id_token": "test-firebase-id-token"})
        assert response.status_code == 200 and response.json()["signup_required"]
        assert verify.call_args.kwargs["check_revoked"] is True
        for claims in [{}, {"firebase": {"sign_in_provider": "password"}},
                       {"firebase": {"sign_in_provider": "google.com", "identities": {}}}]:
            verify.return_value = claims
            assert api.post("/auth/google/login", json={"id_token": "not-google"}).status_code == 401
        verify.side_effect = google.auth.InvalidIdTokenError("test-invalid")
        assert api.post("/auth/google/login", json={"id_token": "expired"}).status_code == 401


def test_signup_validation_does_not_consume_ticket_and_rejects_override():
    with harness() as (api, connection, cursor):
        ticket = accounts.finish_identity("kakao", "user")["signup_ticket"]
        for changes in [{"c_name": " "}, {"preferred_stocks": [1, 1]}, {"c_position": {"1": "투수"}},
                        {"c_birthday": "not-a-date"}, {"c_birthday": "2999-01-01"}, {"c_phone": "1" * 21}]:
            assert api.post("/auth/social/register", json={**signup_payload(ticket), **changes}).status_code == 422
        assert api.post("/auth/social/register", json=signup_payload(ticket)).status_code == 201
        cursor.executemany.assert_called_once()


def test_unknown_or_expired_ticket_is_rejected_before_db():
    with harness() as (api, connection, cursor):
        assert api.post("/auth/social/register", json=signup_payload("unknown")).status_code == 400
        cursor.executemany.assert_not_called()
        ticket = flows.put_flow("signup", {"base": accounts.social_base("google", "u"), "provider": "google"})
        with flows._lock:
            for entry in flows._entries.values():
                entry["until"] = 0
        assert api.post("/auth/social/register", json=signup_payload(ticket)).status_code == 400
        cursor.execute.assert_not_called()


def test_duplicate_deleted_and_case_insensitive_collisions_fail_closed():
    with harness() as (api, connection, cursor):
        base = accounts.social_base("kakao", "123")
        row = {"c_id_seq": base + "_01", "c_login_type": "kakao", "c_name": "회원", "c_prefer_stock": 1, "c_deletdate": None}
        for changed, expected in [({"c_login_type": "local"}, 409),
                                  ({"c_id_seq": base.swapcase() + "_01"}, 409), ({"c_deletdate": "2026-01-01"}, 403)]:
            cursor.fetchall.return_value = [{**row, **changed}]
            try:
                accounts.finish_identity("kakao", "123")
                raise AssertionError("must reject")
            except HTTPException as error:
                assert error.status_code == expected
        cursor.fetchall.return_value = [row]
        ticket = flows.put_flow("signup", {"base": base, "provider": "kakao"})
        assert api.post("/auth/social/register", json=signup_payload(ticket)).status_code == 409
        cursor.executemany.assert_not_called()


def test_database_failure_rolls_back_and_does_not_leak_parameters():
    with harness() as (api, connection, cursor):
        ticket = flows.put_flow("signup", {"base": accounts.social_base("kakao", "123"), "provider": "kakao"})
        cursor.executemany.side_effect = pymysql.IntegrityError("secret-test-parameters")
        response = api.post("/auth/social/register", json=signup_payload(ticket))
        assert response.status_code == 409 and "secret-test" not in response.text
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()


def test_provider_http_errors_and_timeout_are_sanitized():
    for status_code, expected in [(400, 401), (401, 401), (429, 503), (500, 503), (302, 502)]:
        with patch.object(social_http.httpx, "Client") as client:
            response = client.return_value.__enter__.return_value.request.return_value
            response.status_code = status_code
            try:
                social_http.provider_request("GET", "https://example.invalid")
                raise AssertionError("must reject")
            except HTTPException as error:
                assert error.status_code == expected
    with patch.object(social_http.httpx, "Client") as client:
        client.return_value.__enter__.return_value.request.side_effect = httpx.ConnectTimeout("secret")
        try:
            social_http.provider_request("GET", "https://example.invalid")
            raise AssertionError("must reject")
        except HTTPException as error:
            assert error.status_code == 503 and "secret" not in error.detail


def test_missing_settings_and_swagger_paths():
    with harness() as (api, connection, cursor):
        with patch.dict(os.environ, KAKAO_CLIENT_SECRET=""):
            assert api.get("/auth/kakao/login").status_code == 503
        with patch.dict(os.environ, NAVER_REDIRECT_URI="http://testserver/docs"):
            assert api.get("/auth/naver/login").status_code == 503
        assert api.get("/docs").status_code == 200
        paths = api.get("/openapi.json").json()["paths"]
        assert all(p in paths for p in ["/auth/google/login", "/auth/kakao/login", "/auth/kakao/callback",
                                       "/auth/naver/login", "/auth/naver/callback", "/auth/social/register"])


def test_reserved_prefix_and_password_sentinel_are_not_normal_credentials():
    assert not login.verify_password(accounts.PASSWORD_UNSUPPORTED, accounts.PASSWORD_UNSUPPORTED)
    with harness() as (api, connection, cursor), patch.object(register, "connect") as connect:
        payload = {**signup_payload("unused"), "c_id": "k_reserved", "c_pw": "password123", "c_team": "무소속"}
        del payload["signup_ticket"]
        assert api.post("/auth/register", json=payload).status_code == 422
        connect.assert_not_called()
    with harness() as (api, connection, cursor), patch.object(login, "connect", return_value=connection):
        assert api.post("/auth/login", json={"c_id": "member", "c_pw": "password123"}).status_code == 401
        assert "c_login_type = 'local'" in cursor.execute.call_args.args[0]


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-28
