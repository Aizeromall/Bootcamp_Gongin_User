# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""FCM·MySQL은 mock으로 대체하며 실제 토큰 등록/푸시는 수행하지 않습니다."""

import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from firebase_admin import messaging

from python.FastAPI.notification import events, sender, worker, notification_router, history
from python.FastAPI.auth.token import current_account
from python.FastAPI.chat import socket_message, chat_room
from python.FastAPI.match import reservation as reservation_api

AT = datetime(2026, 10, 28, 10, 0)


def reservation(**changes):
    return {"r_seq": 7, "g_code": 3, "c_id_seq": "member_01", "r_date": date(2026, 10, 28),
            "rs_time": timedelta(hours=10), "re_time": timedelta(hours=12), "r_check": 1,
            "r_category": "1", "r_c_category": "", "reservation_category": "1", **changes}


def event(kind="before10", **changes):
    due = {"before10": AT - timedelta(minutes=10), "absence10": AT + timedelta(minutes=10),
           "match_confirmed": AT - timedelta(minutes=20), "message": AT - timedelta(minutes=1)}[kind]
    prefix = "confirmed" if kind == "match_confirmed" else kind
    return {"n_seq": 1, "n_key": f"{prefix}:7:{AT.isoformat()}", "n_type": kind, "c_id_seq": "member_01",
            "r_seq": None if kind == "message" else 7, "s_me_id": 9 if kind == "message" else None,
            "n_due_at": due, "n_expires_at": AT + timedelta(hours=2) if kind in ("absence10", "message") else AT,
            **changes}


def db():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.rowcount = 1
    return connection, cursor


def test_times_include_midnight_and_string_times():
    start, end = events.match_times(reservation(rs_time="22:00", re_time="24:00"))
    assert start == AT.replace(hour=22) and end == datetime(2026, 10, 29)
    assert events.match_times(reservation(rs_time="22:00", re_time="00:00"))[1] == end


def test_message_enqueue_excludes_sender_and_has_unique_key():
    cursor = MagicMock()
    events.enqueue_message(cursor, 9, "sender_01", {"sender_01", "a_01", "b_01"}, at=AT)
    calls = cursor.execute.call_args_list
    assert len(calls) == 2
    assert {c.args[1][1] for c in calls} == {"a_01", "b_01"}
    assert all(c.args[1][0] == "message:9" and "ON DUPLICATE KEY" in c.args[0] for c in calls)


def test_confirmed_event_and_timers_use_reservation_start_not_record_time():
    cursor = MagicMock()
    events.enqueue_match(cursor, reservation(), confirmed=True, at=AT - timedelta(hours=1))
    calls = cursor.execute.call_args_list
    assert [c.args[1][2] for c in calls] == ["match_confirmed", "before10", "absence10"]
    assert calls[1].args[1][5] == AT - timedelta(minutes=10)
    assert calls[2].args[1][5] == AT + timedelta(minutes=10)
    assert all(c.args[1][3] == 7 for c in calls)


def test_canceled_unconfirmed_and_rental_do_not_create_match_events():
    for changes in [{"r_check": 0}, {"r_category": "2"}, {"r_c_category": "우천"}, {"reservation_category": "2"}]:
        cursor = MagicMock()
        events.enqueue_match(cursor, reservation(**changes), confirmed=True, at=AT - timedelta(hours=1))
        cursor.execute.assert_not_called()


def test_before10_time_boundaries_and_changed_schedule():
    for at, expected in [(AT - timedelta(minutes=11), False), (AT - timedelta(minutes=10), True),
                         (AT - timedelta(seconds=1), True), (AT, False)]:
        cursor = MagicMock()
        cursor.fetchone.return_value = reservation()
        assert events.eligible(cursor, event(), at) is expected
    cursor = MagicMock()
    cursor.fetchone.return_value = reservation(rs_time="12:00", re_time="14:00")
    assert not events.eligible(cursor, event(), AT - timedelta(minutes=5))


def test_absence_exact_zero_only_and_reservation_fk():
    for record, expected in [(None, False), ({"c_r_r_attendance": None}, False),
                             ({"c_r_r_attendance": 1}, False), ({"c_r_r_attendance": 0}, True)]:
        cursor = MagicMock()
        cursor.fetchone.side_effect = [reservation(), record]
        assert events.eligible(cursor, event("absence10"), AT + timedelta(minutes=10)) is expected
        assert cursor.execute.call_args.args[1] == (7, "member_01", 3)
        assert "ORDER BY c_r_r_seq DESC" in cursor.execute.call_args.args[0]
    cursor = MagicMock()
    assert not events.eligible(cursor, event("absence10"), AT + timedelta(minutes=9))
    cursor.execute.assert_not_called()


def test_departed_or_deleted_chat_recipient_cannot_receive():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    assert not events.eligible(cursor, event("message"), AT)
    query, args = cursor.execute.call_args.args
    assert "participate" in query and "c_deletdate IS NULL" in query and "s.c_id_seq<>" in query
    assert args == ("member_01", 9, "member_01")


def test_timer_scan_never_backfills_confirmation():
    cursor = MagicMock()
    cursor.fetchall.return_value = [reservation()]
    with patch.object(events, "enqueue_match") as enqueue:
        assert events.plan_timers(cursor, AT) == 1
    enqueue.assert_called_once_with(cursor, reservation(), at=AT)


def test_delivery_accepted_and_device_reassignment_is_rechecked():
    connection, cursor = db()
    cursor.fetchone.return_value = {"f_token": "test-device-token"}
    send = MagicMock(return_value="projects/test/messages/1")
    delivery = {"d_seq": 2, "f_seq": 3, "d_attempts": 1}
    with patch.object(worker, "eligible", return_value=True), patch.object(worker, "now_kst", return_value=AT):
        assert worker.deliver(connection, event("message"), delivery, send) == "accepted"
    assert cursor.execute.call_args.args[1][0] == "accepted"
    assert "FOR UPDATE" in cursor.execute.call_args_list[0].args[0]
    send.assert_called_once()
    cursor.fetchone.return_value = None
    send.reset_mock()
    with patch.object(worker, "eligible", return_value=True):
        assert worker.deliver(connection, event("message"), delivery, send) == "skipped"
    send.assert_not_called()


def test_unregistered_disables_only_that_device_and_transient_errors_retry():
    for attempts, exception, expected in [(1, RuntimeError("secret-token"), "pending"),
                                           (3, RuntimeError("secret-token"), "failed"),
                                           (1, messaging.UnregisteredError("test"), "failed")]:
        connection, cursor = db()
        cursor.fetchone.return_value = {"f_token": "test-device-token"}
        with patch.object(worker, "eligible", return_value=True), patch.object(worker, "now_kst", return_value=AT):
            assert worker.deliver(connection, event("message"), {"d_seq": 2, "f_seq": 3, "d_attempts": attempts},
                                  MagicMock(side_effect=exception)) == expected
        assert "secret-token" not in str(cursor.execute.call_args_list)
        deactivated = any("SET f_active=0" in c.args[0] for c in cursor.execute.call_args_list)
        assert deactivated is isinstance(exception, messaging.UnregisteredError)


def test_processing_event_handles_no_device_without_starving_new_events():
    connection, cursor = db()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = {"total": 0, "waiting": None, "failed": None}
    send = MagicMock()
    with patch.object(worker, "eligible", return_value=True), patch.object(worker, "now_kst", return_value=AT):
        assert worker.process_event(connection, event("message"), send) == []
    assert "n_due_at=%s" in cursor.execute.call_args.args[0]
    send.assert_not_called()


def test_processing_event_claims_persisted_delivery_and_completes():
    connection, cursor = db()
    cursor.fetchall.return_value = [{"d_seq": 2, "f_seq": 3, "d_attempts": 0}]
    cursor.fetchone.side_effect = [{"f_token": "test-token"}, {"total": 1, "waiting": 0, "failed": 0}]
    send = MagicMock(return_value="projects/test/messages/1")
    with patch.object(worker, "eligible", return_value=True), patch.object(worker, "now_kst", return_value=AT):
        assert worker.process_event(connection, event("message"), send) == ["accepted"]
    assert cursor.execute.call_args.args[1] == ("completed", 1)
    assert any("d_attempts=d_attempts+1" in c.args[0] for c in cursor.execute.call_args_list)


def test_single_worker_lock_and_rollback_on_database_error():
    connection, cursor = db()
    cursor.fetchone.return_value = {"acquired": 0}
    send = MagicMock()
    with patch.object(worker, "connect", return_value=connection):
        assert worker.run_cycle(send)["status"] == "another_worker_running"
    send.assert_not_called()
    connection.close.assert_called_once()
    connection, cursor = db()
    cursor.fetchone.return_value = {"acquired": 1}
    with patch.object(worker, "connect", return_value=connection), patch.object(worker, "plan_timers", side_effect=RuntimeError("db")):
        try:
            worker.run_cycle(send)
            raise AssertionError("must fail")
        except RuntimeError:
            pass
    connection.rollback.assert_called_once()
    assert "RELEASE_LOCK" in cursor.execute.call_args.args[0]


def test_preview_never_writes_or_calls_firebase():
    connection, cursor = db()
    cursor.fetchall.return_value = []
    with patch.object(worker, "connect", return_value=connection), patch.object(sender, "send") as send:
        assert worker.preview()["mode"] == "preview"
    assert all(c.args[0].lstrip().startswith("SELECT") for c in cursor.execute.call_args_list)
    connection.commit.assert_not_called()
    connection.rollback.assert_called_once()
    send.assert_not_called()


def test_worker_recovers_leases_expires_events_and_releases_lock():
    connection, cursor = db()
    cursor.fetchone.return_value = {"acquired": 1}
    cursor.fetchall.return_value = []
    send = MagicMock()
    with patch.object(worker, "connect", return_value=connection), patch.object(worker, "plan_timers") as plan, \
            patch.object(worker, "now_kst", return_value=AT):
        assert worker.run_cycle(send)["events_checked"] == 0
    plan.assert_called_once_with(cursor, AT)
    queries = [c.args[0] for c in cursor.execute.call_args_list]
    assert any("d_lease_until<=%s AND d_attempts<%s" in sql for sql in queries)
    assert any("lease_exhausted" in sql for sql in queries)
    assert any("n_expires_at<=%s" in sql for sql in queries)
    assert "RELEASE_LOCK" in queries[-1]
    send.assert_not_called()


def test_reservation_confirmation_outbox_is_atomic():
    for fail in (False, True):
        connection, cursor = db()
        cursor.fetchone.side_effect = [{"g_code": 1, "g_num": 2, "g_price": 10000}, {"exists": 1}, None, None, None,
                                       {"reservation_count": 1}]
        cursor.lastrowid = 7
        with patch.object(reservation_api, "connect", return_value=connection), \
                patch.object(reservation_api, "enqueue_confirmed_slot", side_effect=RuntimeError("outbox") if fail else None) as enqueue, \
                patch.object(reservation_api.logger, "exception"):
            if fail:
                try:
                    reservation_api.create_reservation("member_01", "1", AT.date(), "10:00", "카카오페이")
                    raise AssertionError("must rollback")
                except Exception as error:
                    assert getattr(error, "status_code", None) == 500
                connection.rollback.assert_called_once()
                connection.commit.assert_not_called()
            else:
                assert reservation_api.create_reservation("member_01", "1", AT.date(), "10:00", "카카오페이")["r_check"]
                connection.commit.assert_called_once()
            enqueue.assert_called_once_with(cursor, "1", AT.date(), "10:00")


def test_android_payload_privacy_expiry_and_deduplication_key():
    with patch.object(sender, "now_kst", return_value=AT), patch.object(sender.messaging, "send", return_value="accepted") as send:
        assert sender.send(event("message"), "test-token", app=MagicMock()) == "accepted"
    message = send.call_args.args[0]
    assert message.data == {"event_id": "1", "type": "message", "s_me_id": "9", "c_id_seq": "member_01"}
    assert message.android.ttl == timedelta(hours=2)
    assert message.android.notification.tag == "event-1"
    assert "member_01" not in message.notification.body


def test_chat_outbox_error_rolls_back_message_transaction():
    connection, cursor = db()
    cursor.lastrowid = 9
    cursor.fetchone.return_value = {"s_me_id": 9}
    cursor.fetchall.return_value = [{"c_id_seq": "sender_01"}, {"c_id_seq": "member_01"}]
    with patch.object(chat_room, "connect", return_value=connection), patch.object(socket_message, "require_room"), \
            patch.object(socket_message, "enqueue_message", side_effect=RuntimeError("outbox")), \
            patch.object(chat_room.logger, "exception"):
        try:
            socket_message.store_message(1, "sender_01", "message")
            raise AssertionError("must rollback")
        except Exception as error:
            assert getattr(error, "status_code", None) == 500
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_history_uses_authenticated_members_only_and_no_send_endpoint():
    app = FastAPI()
    app.include_router(notification_router)
    connection, cursor = db()
    cursor.fetchall.return_value = []
    with TestClient(app) as api:
        assert api.get("/notifications/events").status_code == 401
        app.dependency_overrides[current_account] = lambda: {"member_ids": ["member_01"]}
        with patch.object(history, "device_connection") as context:
            context.return_value.__enter__.return_value = connection
            assert api.get("/notifications/events").status_code == 200
            assert cursor.execute.call_args.args[1] == ("member_01", 50)
        assert api.post("/notifications/send").status_code == 404


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-28
