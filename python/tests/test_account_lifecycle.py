# 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
"""실제 DB 변경·공급자 요청 없이 Swagger 계약과 종목별 수명주기를 검증합니다."""
import copy
import os
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import jwt
import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from python.FastAPI.auth import account, account_lifecycle as life, account_retention as retention
from python.FastAPI.auth import login, social_account, token

AT = datetime(2026, 10, 29, 12, 0, 0)
KEY = "test-only-account-lifecycle-signing-key-123456"


def member(sport=1, deleted=None, provider="local", base="member_with_underscore"):
    return {"c_id_seq": f"{base}_{sport:02d}", "c_login_type": provider, "c_pw": "stored-hash",
            "c_name": "회원", "c_address": "서울", "c_phone": "01012345678", "c_gender": "남",
            "c_birthday": AT.date() - timedelta(days=7000), "c_signupdate": AT - timedelta(days=100),
            "c_deletdate": deleted, "c_prefer_stock": str(sport), "c_team": "무소속",
            "c_position": "FW" if sport == 1 else "센터", "c_category": None, "c_rating": 1500}


@contextmanager
def harness(rows=None):
    data = copy.deepcopy(rows if rows is not None else [member()])
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = lambda: data
    cursor.rowcount = 1
    app = FastAPI()
    app.include_router(account.router, prefix="/auth")
    app.include_router(login.router, prefix="/auth")
    with patch.dict(os.environ, AUTH_TOKEN_SECRET=KEY), \
            patch.object(life, "connect", return_value=connection), \
            patch.object(login, "connect", return_value=connection), \
            patch.object(life, "now_kst", return_value=AT), \
            patch.object(account, "now_kst", return_value=AT), TestClient(app) as api:
        yield api, connection, cursor, data


def authorization(ids=None, base="member_with_underscore"):
    return {"Authorization": "Bearer " + token.issue_token(base, ids or [base + "_01"])["access_token"]}


def sql_writes(cursor):
    return [c.args for c in cursor.execute.call_args_list if c.args[0].startswith(("UPDATE", "INSERT", "DELETE"))]


def test_profile_requires_service_token_and_never_returns_password():
    with harness() as (api, conn, cursor, _):
        assert api.get("/auth/account").status_code == 401
        cursor.execute.assert_not_called()
        r = api.get("/auth/account", headers=authorization())
        assert r.status_code == 200 and "stored-hash" not in r.text and '"c_pw"' not in r.text
        assert r.json()["sports"][0]["state"] == "active"
        assert cursor.execute.call_args.args[1] == tuple(f"member_with_underscore_{s:02d}" for s in range(1, 5))
        conn.commit.assert_not_called()


def test_profile_forbidden_null_blank_unknown_and_lengths():
    with harness() as (api, _, cursor, _):
        for body in [{}, {"c_rating": 2000}, {"c_login_type": "local"}, {"c_signupdate": "2020-01-01"},
                     {"c_deletdate": None}, {"c_deletedate": None}, {"c_id_seq": "other_01"},
                     {"c_team": "임의팀"}, {"c_category": "가입"}, {"preferred_stocks": [2]},
                     {"c_phone": None}, {"c_name": " "}, {"c_name": "가" * 51},
                     {"c_address": "가" * 256}, {"c_phone": "1" * 21}, {"c_gender": "가" * 11},
                     {"c_birthday": "2999-01-01"}, {"c_birthday": None},
                     {"c_position": {}}, {"c_position": {"1": "투수"}}, {"c_position": {"5": "FW"}},
                     {"current_password": "password123"}, {"c_pw": "password123"}]:
            r = api.patch("/auth/account/profile", headers=authorization(), json=body)
            assert r.status_code == 422, (body, r.text)
        assert sql_writes(cursor) == []


def test_profile_shared_fields_and_per_sport_position_atomic():
    with harness([member(), member(2, AT - timedelta(days=2)), member(4)]) as (api, conn, cursor, rows):
        r = api.patch("/auth/account/profile", headers=authorization(), json={
            "c_name": "새이름", "c_phone": "01098765432", "c_position": {"4": "세터"}})
        assert r.status_code == 200, r.text
        assert all(row["c_name"] == "새이름" for row in rows)
        assert rows[2]["c_position"] == "세터" and rows[0]["c_position"] == "FW"
        assert r.json()["session"]["preferred_stocks"] == [1, 4]
        assert "FOR UPDATE" in cursor.execute.call_args_list[0].args[0]
        conn.commit.assert_called_once()


def test_password_change_verifies_local_and_updates_hash_all_sports():
    with harness([member(), member(4)]) as (api, conn, _, rows), \
            patch.object(account, "verify_password", return_value=True), \
            patch.object(account, "hash_password", return_value="new-hash"):
        r = api.patch("/auth/account/profile", headers=authorization(),
                      json={"current_password": "password123", "c_pw": "newpassword"})
        assert r.status_code == 200 and all(row["c_pw"] == "new-hash" for row in rows)
        assert "new-hash" not in r.text and "newpassword" not in r.text
        conn.commit.assert_called_once()
    with harness() as (api, conn, cursor, _), patch.object(account, "verify_password", return_value=False):
        assert api.patch("/auth/account/profile", headers=authorization(),
                         json={"current_password": "password123", "c_pw": "newpassword"}).status_code == 401
        assert sql_writes(cursor) == []
        conn.rollback.assert_called_once()
    with harness([member(provider="naver")]) as (api, _, cursor, _):
        assert api.patch("/auth/account/profile", headers=authorization(),
                         json={"current_password": "password123", "c_pw": "newpassword"}).status_code == 422
        assert sql_writes(cursor) == []


def test_cannot_access_other_deleted_or_unjoined_sport():
    with harness([member(1, AT - timedelta(days=1)), member(4)]) as (api, _, cursor, _):
        assert api.get("/auth/account", headers=authorization()).status_code == 403
        assert api.get("/auth/account", headers=authorization(["other_01"], base="other")).status_code == 409
        assert api.patch("/auth/account/profile", headers=authorization(["member_with_underscore_04"]),
                         json={"c_position": {"1": "FW"}}).status_code == 409
        assert sql_writes(cursor) == []


def test_new_sport_fixed_suffix_initial_rating_and_no_team_authority():
    with harness() as (api, conn, cursor, _):
        r = api.post("/auth/account/sports", headers=authorization(), json={"sport": 4, "c_position": "세터"})
        assert r.status_code == 201, r.text
        assert r.json()["created_customer_id"] == "member_with_underscore_04"
        write = sql_writes(cursor)[0]
        assert write[0].startswith("INSERT INTO customer") and "c_category" not in write[0]
        assert write[1][0] == "member_with_underscore_04" and write[1][-1] == 1500
        assert write[1][-3] == "무소속" and write[1][8] == AT
        assert r.json()["session"]["preferred_stocks"] == [1, 4]
        conn.commit.assert_called_once()


def test_existing_active_pending_expired_sport_not_overwritten():
    for deleted, state in [(None, "ACTIVE"), (AT - timedelta(days=29), "RECOVERABLE"),
                           (AT - timedelta(days=30), "EXPIRED")]:
        with harness([member(), member(4, deleted)]) as (api, conn, cursor, _):
            r = api.post("/auth/account/sports", headers=authorization(), json={"sport": 4, "c_position": "세터"})
            assert r.status_code == 409 and state in r.text
            assert sql_writes(cursor) == []
            conn.commit.assert_not_called()


def test_withdraw_one_preserves_other_sports_and_selected_time():
    with harness([member(), member(4)]) as (api, conn, cursor, rows):
        old_selected = rows[0]["c_signupdate"]
        r = api.delete("/auth/account/sports/1", headers=authorization())
        assert r.status_code == 200 and rows[0]["c_deletdate"] == AT and rows[1]["c_deletdate"] is None
        assert rows[0]["c_signupdate"] == old_selected
        assert r.json()["session"]["preferred_stocks"] == [4]
        assert r.json()["account_deletion_due_at"] is None
        assert len(sql_writes(cursor)) == 1 and sql_writes(cursor)[0][0].startswith("UPDATE customer")
        conn.commit.assert_called_once()


def test_repeated_withdraw_does_not_restart_grace():
    deleted = AT - timedelta(days=10)
    with harness([member(1, deleted), member(4)]) as (api, _, cursor, rows):
        r = api.delete("/auth/account/sports/1", headers=authorization(["member_with_underscore_04"]))
        assert r.status_code == 409 and rows[0]["c_deletdate"] == deleted and sql_writes(cursor) == []


def test_withdraw_all_preserves_prior_date_and_last_sport_drives_deadline():
    deleted = AT - timedelta(days=10)
    with harness([member(1, deleted), member(4)]) as (api, conn, cursor, rows):
        r = api.post("/auth/account/withdraw", headers=authorization(["member_with_underscore_04"]))
        assert r.status_code == 200, r.text
        assert rows[0]["c_deletdate"] == deleted and rows[1]["c_deletdate"] == AT
        assert r.json()["account_deletion_due_at"] == (AT + life.GRACE).isoformat()
        recovery = r.json()["session"]
        assert recovery["recovery_required"] and "access_token" not in recovery
        assert len(sql_writes(cursor)) == 1
        conn.commit.assert_called_once()


def test_restore_before_but_not_at_30_day_boundary():
    for elapsed, status in [(life.GRACE - timedelta(seconds=1), 200), (life.GRACE, 409),
                            (life.GRACE + timedelta(seconds=1), 409)]:
        with harness([member(), member(4, AT - elapsed)]) as (api, _, cursor, rows):
            old_signup = rows[1]["c_signupdate"]
            r = api.post("/auth/account/sports/4/restore", headers=authorization())
            assert r.status_code == status, r.text
            assert rows[1]["c_signupdate"] == old_signup
            if status == 200:
                assert rows[1]["c_deletdate"] is None
                assert r.json()["session"]["preferred_stocks"] == [1, 4]
            else:
                assert sql_writes(cursor) == []


def test_local_login_requires_password_even_for_recovery():
    with harness([member(1, AT - timedelta(days=2))]) as (api, _, _, _), \
            patch.object(login, "verify_password", return_value=False):
        r = api.post("/auth/login", json={"c_id": "member_with_underscore", "c_pw": "password123"})
        assert r.status_code == 401 and "recovery_token" not in r.text
    with harness([member(1, AT - timedelta(days=2))]) as (api, _, _, _), \
            patch.object(login, "verify_password", return_value=True):
        r = api.post("/auth/login", json={"c_id": "member_with_underscore", "c_pw": "password123"})
        assert r.status_code == 200 and r.json()["recovery_required"] and "access_token" not in r.json()


def test_social_deleted_login_uses_same_recovery_and_expired_denied():
    with harness([member(1, AT - timedelta(days=2), "naver")]) as (_, _, _, rows):
        r = social_account.login_response("member_with_underscore", "naver", rows)
        assert r["recovery_required"] and "access_token" not in r
    with harness([member(1, AT - life.GRACE)]) as (_, _, _, rows):
        try:
            life.authentication_result("member_with_underscore", "local", rows)
            raise AssertionError("expired recovery must fail")
        except HTTPException as error:
            assert error.status_code == 403


def test_all_social_providers_keep_identity_verification_and_return_recovery():
    for provider in ("google", "kakao", "naver"):
        base = social_account.social_base(provider, "provider-subject")
        with harness([member(1, AT - timedelta(days=1), provider, base)]) as (_, conn, _, _), \
                patch.object(social_account, "connect", return_value=conn), \
                patch.object(social_account, "put_flow") as signup:
            response = social_account.finish_identity(provider, "provider-subject")
            assert response["recovery_required"] and "access_token" not in response
            assert life.decode_recovery(response["recovery_token"])["provider"] == provider
            signup.assert_not_called()


def test_recovery_audience_separation_preview_and_restore_replay():
    with harness([member(1, AT - timedelta(days=1)), member(4, AT - timedelta(days=31))]) as (api, conn, cursor, rows):
        result = life.authentication_result("member_with_underscore", "local", rows)
        headers = {"Authorization": "Bearer " + result["recovery_token"]}
        assert api.get("/auth/account", headers=headers).status_code == 401
        assert api.get("/auth/account/recovery", headers=authorization()).status_code == 401
        preview = api.get("/auth/account/recovery", headers=headers)
        assert preview.status_code == 200 and "정말로" in preview.json()["confirmation"]
        assert sql_writes(cursor) == []  # 아니오/미선택은 DB 변경 없음
        assert api.post("/auth/account/recovery/restore", headers=headers, json={"sports": [4]}).status_code == 409
        assert api.post("/auth/account/recovery/restore", headers=headers, json={"sports": [2]}).status_code == 404
        assert api.post("/auth/account/recovery/restore", headers=headers, json={"sports": [1, 1]}).status_code == 422
        response = api.post("/auth/account/recovery/restore", headers=headers, json={"sports": [1]})
        assert response.status_code == 200 and response.json()["session"]["preferred_stocks"] == [1]
        assert response.json()["account_deletion_due_at"] is None
        assert api.post("/auth/account/recovery/restore", headers=headers, json={"sports": [1]}).status_code == 401


def test_changed_deletion_snapshot_forged_and_expired_recovery_rejected():
    with harness([member(1, AT - timedelta(days=1))]) as (api, _, _, rows):
        encoded = life.authentication_result("member_with_underscore", "local", rows)["recovery_token"]
        claims = life.decode_recovery(encoded)
        for changed, key in [({**claims, "exp": 0}, KEY), (claims, KEY + "wrong"),
                             ({**claims, "aud": token.AUDIENCE}, KEY)]:
            invalid = jwt.encode(changed, key, algorithm="HS256")
            assert api.get("/auth/account/recovery", headers={"Authorization": "Bearer " + invalid}).status_code == 401
        rows[0]["c_deletdate"] -= timedelta(seconds=1)
        assert api.get("/auth/account/recovery", headers={"Authorization": "Bearer " + encoded}).status_code == 401


def test_database_failure_integrity_and_missing_secret_roll_back():
    with harness() as (api, conn, cursor, _):
        cursor.execute.side_effect = pymysql.IntegrityError(1451, "private SQL diagnostic")
        r = api.get("/auth/account", headers=authorization())
        assert r.status_code == 409 and "private" not in r.text
        conn.rollback.assert_called_once()
    with harness() as (api, conn, cursor, _):
        cursor.execute.side_effect = RuntimeError("private diagnostic")
        r = api.get("/auth/account", headers=authorization())
        assert r.status_code == 500 and "private" not in r.text
        conn.rollback.assert_called_once()
    with harness() as (api, _, cursor, _):
        headers = authorization()
        with patch.dict(os.environ, AUTH_TOKEN_SECRET=""):
            assert api.get("/auth/account", headers=headers).status_code == 503
        cursor.execute.assert_not_called()


def test_retention_preview_never_writes_and_blocks_cascade_too():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[{"c_id_seq": "member_01"}, {"c_id_seq": "member_04"}],
                                 [{"TABLE_SCHEMA": "test", "TABLE_NAME": "pay", "CONSTRAINT_NAME": "fk_pay",
                                   "COLUMN_NAME": "c_id_seq", "REFERENCED_COLUMN_NAME": "c_id_seq"}]]
    cursor.fetchone.side_effect = [{"1": 1}, None]
    with patch.object(life, "connect", return_value=conn), patch.object(retention, "now_kst", return_value=AT):
        report = retention.run_retention()
    assert report["mode"] == "preview" and report["deleted"] == []
    assert report["eligible"] == ["member_04"] and report["blocked"][0]["tables"] == ["pay"]
    assert sql_writes(cursor) == []
    assert cursor.execute.call_args_list[2].args[1][0] == AT - life.GRACE
    conn.commit.assert_not_called()


def test_retention_explicit_delete_only_unreferenced_expired_rows():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[{"c_id_seq": "member_01"}], []]
    cursor.rowcount = 1
    with patch.object(life, "connect", return_value=conn), patch.object(retention, "now_kst", return_value=AT):
        report = retention.run_retention(delete=True)
    assert report["deleted"] == ["member_01"]
    write = sql_writes(cursor)[0]
    assert "c_deletdate<=%s" in write[0] and write[1] == ("member_01", AT - life.GRACE)
    conn.commit.assert_called_once()


def test_swagger_main_registration_docs_and_request_validation_no_database():
    from python.FastAPI.main import app
    spec = app.openapi()
    expected = {"/auth/account": "get", "/auth/account/profile": "patch", "/auth/account/sports": "post",
                "/auth/account/sports/{sport}": "delete", "/auth/account/withdraw": "post",
                "/auth/account/sports/{sport}/restore": "post", "/auth/account/recovery": "get",
                "/auth/account/recovery/restore": "post"}
    with TestClient(app) as api, patch.object(life, "connect") as connect:
        assert api.get("/docs").status_code == 200 and api.get("/openapi.json").status_code == 200
        for path, method in expected.items():
            operation = spec["paths"][path][method]
            assert operation["security"] and set(map(str, life.ERRORS)).issubset(operation["responses"])
            assert ("201" if path == "/auth/account/sports" else "200") in operation["responses"]
        assert api.post("/auth/account/sports", json={}).status_code == 401
        connect.assert_not_called()


def test_unknown_member_invalid_path_and_missing_payload():
    with harness([]) as (api, _, _, _):
        assert api.get("/auth/account", headers=authorization()).status_code == 404
    with harness() as (api, _, cursor, _):
        for sport in (0, 5, "invalid"):
            assert api.delete(f"/auth/account/sports/{sport}", headers=authorization()).status_code == 422
        for body in ({}, {"sport": 5, "c_position": "FW"}, {"sport": 1, "c_position": None}):
            assert api.post("/auth/account/sports", headers=authorization(), json=body).status_code == 422
        assert sql_writes(cursor) == []


def test_recovery_preview_checks_deadline_even_with_unexpired_jwt():
    with harness([member(1, AT - timedelta(days=29))]) as (api, _, _, rows):
        recovery = life.authentication_result("member_with_underscore", "local", rows)["recovery_token"]
        with patch.object(account, "now_kst", return_value=AT + timedelta(days=1)):
            response = api.get("/auth/account/recovery", headers={"Authorization": "Bearer " + recovery})
            assert response.status_code == 403


def test_retention_next_cursor_can_skip_blocked_first_batch():
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchall.side_effect = [[{"c_id_seq": "member_04"}], []]
    with patch.object(life, "connect", return_value=conn):
        report = retention.run_retention(limit=1, after="member_01")
    assert report["next_cursor"] == "member_04"
    assert cursor.execute.call_args_list[2].args[1][1:] == ("member_01", 1)


def test_local_signup_uses_sport_selection_timestamp_and_fixed_rating():
    from python.FastAPI.auth import register
    app = FastAPI()
    app.include_router(register.router, prefix="/auth")
    conn = MagicMock()
    cursor = conn.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    body = {"c_id": "member", "c_pw": "password123", "c_name": "회원", "c_address": "서울",
            "c_phone": "01012345678", "c_gender": "남", "c_birthday": "2000-01-01",
            "c_team": "무소속", "preferred_stocks": [4], "c_position": {"4": "세터"}}
    with TestClient(app) as api, patch.object(register, "connect", return_value=conn), \
            patch.object(register, "now_kst", return_value=AT), patch.object(register, "hash_password", return_value="hash"):
        response = api.post("/auth/register", json=body)
    assert response.status_code == 201
    row = cursor.executemany.call_args.args[1][0]
    assert row[0] == "member_04" and row[10] == AT and row[11] == 1500


def test_profile_sport_selection_add_remove_restore_in_one_transaction():
    with harness([member(), member(4, AT - timedelta(days=3))]) as (api, conn, cursor, rows):
        selected_at = rows[1]["c_signupdate"]
        result = api.patch("/auth/account/profile", headers=authorization(), json={
            "c_name": "변경회원", "preferred_stocks": [2, 4], "c_position": {"2": "가드", "4": "세터"}})
        assert result.status_code == 200, result.text
        assert rows[0]["c_deletdate"] == AT
        assert rows[1]["c_deletdate"] is None and rows[1]["c_signupdate"] == selected_at
        inserts = [args for args in sql_writes(cursor) if args[0].startswith("INSERT")]
        assert len(inserts) == 1 and inserts[0][1][0] == "member_with_underscore_02"
        assert inserts[0][1][3] == "변경회원" and inserts[0][1][8] == AT
        assert result.json()["session"]["preferred_stocks"] == [2, 4]
        assert len([c for c in cursor.execute.call_args_list if c.args[0].startswith("SELECT")]) == 1
        conn.commit.assert_called_once()


def test_profile_empty_sports_means_all_withdrawn_without_resetting_existing_date():
    deleted = AT - timedelta(days=2)
    with harness([member(), member(4, deleted)]) as (api, conn, _, rows):
        result = api.patch("/auth/account/profile", headers=authorization(),
                           json={"preferred_stocks": [], "c_position": {}})
        assert result.status_code == 200 and result.json()["session"]["recovery_required"]
        assert rows[0]["c_deletdate"] == AT and rows[1]["c_deletdate"] == deleted
        conn.commit.assert_called_once()


def test_profile_invalid_sports_and_expired_restore_fail_before_writes():
    with harness([member(), member(4, AT - life.GRACE)]) as (api, _, cursor, _):
        for chosen in (None, [True], [1, 1], [5], "1"):
            assert api.patch("/auth/account/profile", headers=authorization(),
                             json={"preferred_stocks": chosen}).status_code == 422
        result = api.patch("/auth/account/profile", headers=authorization(),
                           json={"preferred_stocks": [1, 4], "c_position": {"1": "FW", "4": "세터"}})
        assert result.status_code == 409 and sql_writes(cursor) == []


def test_profile_sport_add_failure_rolls_back_profile_and_withdraw():
    with harness() as (api, conn, cursor, _):
        def execute(sql, params):
            if sql.startswith("INSERT"):
                raise pymysql.IntegrityError(1062, "private diagnostic")
        cursor.execute.side_effect = execute
        result = api.patch("/auth/account/profile", headers=authorization(),
                           json={"c_name": "변경회원", "preferred_stocks": [4], "c_position": {"4": "세터"}})
        assert result.status_code == 409 and "private" not in result.text
        conn.rollback.assert_called_once()
        conn.commit.assert_not_called()


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
