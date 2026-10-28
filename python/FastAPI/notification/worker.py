# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""DB outbox 소비자. 기본 실행은 조회만 하며 실제 발송에는 --send가 필요합니다."""

import argparse
import json
import time
from datetime import timedelta

from firebase_admin import exceptions as firebase_errors, messaging

from ..database import connect
from . import sender
from .events import eligible, now_kst, plan_timers

LOCK_NAME = "gongin-notification-worker"
MAX_ATTEMPTS = 3


def preview() -> dict:
    """실제 DB에서도 안전하게 실행할 수 있는 읽기 전용 점검입니다. 토큰·회원 ID를 출력하지 않습니다."""
    connection = connect()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT n_type, n_state, COUNT(*) AS count FROM notification_event GROUP BY n_type,n_state")
            events = list(cursor.fetchall())
            cursor.execute("SELECT f_platform, COUNT(*) AS count FROM fcm_device WHERE f_active=1 GROUP BY f_platform")
            devices = list(cursor.fetchall())
        return {"mode": "preview", "time_kst": now_kst().isoformat(), "events": events, "active_devices": devices}
    finally:
        connection.rollback()
        connection.close()


def record_result(cursor, delivery: dict, at, state: str, error=None, message_id=None) -> None:
    retry = at + timedelta(seconds=60 * delivery["d_attempts"]) if state == "pending" else None
    cursor.execute(
        """UPDATE notification_delivery SET d_state=%s, d_retry_at=%s, d_lease_until=NULL,
                  d_error_code=%s, d_fcm_message_id=%s WHERE d_seq=%s""",
        (state, retry, error, message_id, delivery["d_seq"]),
    )


def deliver(connection, event: dict, delivery: dict, send_fn) -> str:
    at = now_kst()
    with connection.cursor() as cursor:
        if not eligible(cursor, event, at):
            record_result(cursor, delivery, at, "skipped", "ineligible")
            connection.commit()
            return "skipped"
        # 기기 토큰을 다른 회원에게 재연결하거나 해제하는 트랜잭션과 순서를 맞춥니다.
        # 수정 일 : 2026-10-28 / 작업자 : 최현준
        # 마지막 _01~_04만 제거해 동일 계정의 모든 가입 종목을 허용합니다.
        # LIKE를 사용하지 않아 소셜 ID의 '_'나 해시 대소문자를 와일드카드로 취급하지 않습니다.
        cursor.execute(
            """SELECT f.f_token FROM fcm_device f
               JOIN customer owner ON BINARY owner.c_id_seq=BINARY f.c_id_seq
               JOIN customer recipient ON BINARY LEFT(owner.c_id_seq,LENGTH(owner.c_id_seq)-3)
                   =BINARY LEFT(recipient.c_id_seq,LENGTH(recipient.c_id_seq)-3)
                   AND owner.c_login_type=recipient.c_login_type
               WHERE f.f_seq=%s AND BINARY recipient.c_id_seq=BINARY %s
                 AND RIGHT(owner.c_id_seq,3) IN ('_01','_02','_03','_04')
                 AND RIGHT(recipient.c_id_seq,3) IN ('_01','_02','_03','_04')
                 AND owner.c_deletdate IS NULL AND recipient.c_deletdate IS NULL
                 AND f.f_active=1 AND f.f_platform='android' FOR UPDATE""", (delivery["f_seq"], event["c_id_seq"]),
        )
        device = cursor.fetchone()
        if device is None:
            record_result(cursor, delivery, at, "skipped", "inactive_or_reassigned")
            connection.commit()
            return "skipped"
        try:
            message_id = send_fn(event, device["f_token"])
        except messaging.UnregisteredError:
            cursor.execute("UPDATE fcm_device SET f_active=0 WHERE f_seq=%s", (delivery["f_seq"],))
            record_result(cursor, delivery, at, "failed", "unregistered")
            state = "failed"
        except (messaging.SenderIdMismatchError, firebase_errors.InvalidArgumentError, ValueError):
            # 잘못된 payload일 수도 있으므로 UNREGISTERED 외 오류로 기기 자체를 비활성화하지 않습니다.
            record_result(cursor, delivery, at, "failed", "invalid_sender_or_payload")
            state = "failed"
        except Exception:
            # 네트워크 오류의 원문에는 토큰이 포함될 수 있으므로 고정 코드만 저장합니다.
            state = "pending" if delivery["d_attempts"] < MAX_ATTEMPTS else "failed"
            record_result(cursor, delivery, at, state, "send_error")
        else:
            record_result(cursor, delivery, at, "accepted", message_id=message_id)
            state = "accepted"
        connection.commit()
        return state


def process_event(connection, event: dict, send_fn) -> list[str]:
    at = now_kst()
    with connection.cursor() as cursor:
        if not eligible(cursor, event, at):
            cursor.execute("UPDATE notification_event SET n_state='canceled' WHERE n_seq=%s", (event["n_seq"],))
            cursor.execute(
                """UPDATE notification_delivery SET d_state='skipped', d_lease_until=NULL, d_error_code='ineligible'
                   WHERE n_seq=%s AND d_state IN ('pending','processing')""", (event["n_seq"],),
            )
            connection.commit()
            return ["canceled"]
        cursor.execute(
            """INSERT INTO notification_delivery (n_seq,f_seq,d_state)
               SELECT %s,f.f_seq,'pending' FROM fcm_device f
               JOIN customer owner ON BINARY owner.c_id_seq=BINARY f.c_id_seq
               JOIN customer recipient ON BINARY LEFT(owner.c_id_seq,LENGTH(owner.c_id_seq)-3)
                   =BINARY LEFT(recipient.c_id_seq,LENGTH(recipient.c_id_seq)-3)
                   AND owner.c_login_type=recipient.c_login_type
               WHERE BINARY recipient.c_id_seq=BINARY %s
                 AND RIGHT(owner.c_id_seq,3) IN ('_01','_02','_03','_04')
                 AND RIGHT(recipient.c_id_seq,3) IN ('_01','_02','_03','_04')
                 AND owner.c_deletdate IS NULL AND recipient.c_deletdate IS NULL
                 AND f.f_active=1 AND f.f_platform='android'
               ON DUPLICATE KEY UPDATE n_seq=VALUES(n_seq)""", (event["n_seq"], event["c_id_seq"]),
        )
        cursor.execute(
            """SELECT d_seq,f_seq,d_attempts FROM notification_delivery WHERE n_seq=%s
               AND d_state='pending' AND (d_retry_at IS NULL OR d_retry_at<=%s) ORDER BY d_seq LIMIT 100""",
            (event["n_seq"], at),
        )
        deliveries = list(cursor.fetchall())
    results = []
    for delivery in deliveries:
        with connection.cursor() as cursor:
            cursor.execute(
                """UPDATE notification_delivery SET d_state='processing', d_attempts=d_attempts+1,
                          d_lease_until=%s WHERE d_seq=%s AND d_state='pending'""",
                (now_kst() + timedelta(seconds=120), delivery["d_seq"]),
            )
            if cursor.rowcount != 1:
                continue
            connection.commit()  # 외부 FCM 호출 전에 처리 의도를 영속화합니다.
        delivery["d_attempts"] += 1
        results.append(deliver(connection, event, delivery, send_fn))
    with connection.cursor() as cursor:
        cursor.execute(
            """SELECT COUNT(*) AS total,
                      SUM(d_state IN ('pending','processing')) AS waiting,
                      SUM(d_state='failed') AS failed
               FROM notification_delivery WHERE n_seq=%s""", (event["n_seq"],),
        )
        totals = cursor.fetchone()
        if totals["total"] and not totals["waiting"]:
            state = "failed" if totals["failed"] else "completed"
            cursor.execute("UPDATE notification_event SET n_state=%s WHERE n_seq=%s", (state, event["n_seq"]))
        else:
            # 미등록 기기·재시도 대기 이벤트가 첫 100건을 계속 점유하지 않도록 다음 점검을 분산합니다.
            cursor.execute("UPDATE notification_event SET n_due_at=%s WHERE n_seq=%s",
                           (now_kst() + timedelta(seconds=15), event["n_seq"]))
        # 기기 미등록이면 만료까지 pending을 유지해 뒤늦은 기기 등록을 허용합니다.
        connection.commit()
    return results


def run_cycle(send_fn=None) -> dict:
    if send_fn is None:
        app = sender.firebase_app()
        app.credential.get_credential()  # 자격 증명 누락은 DB 쓰기 전에 확인합니다.
        send_fn = lambda event, token: sender.send(event, token, app=app)
    connection = connect()
    locked = False
    try:
        with connection.cursor() as cursor:
            # API worker 수와 무관하게 알림 소비자는 한 번에 하나만 실행됩니다.
            cursor.execute("SELECT GET_LOCK(%s,0) AS acquired", (LOCK_NAME,))
            locked = cursor.fetchone()["acquired"] == 1
            if not locked:
                return {"mode": "send", "status": "another_worker_running"}
            at = now_kst()
            plan_timers(cursor, at)
            cursor.execute(
                """UPDATE notification_delivery SET d_state='pending', d_lease_until=NULL
                   WHERE d_state='processing' AND d_lease_until<=%s AND d_attempts<%s""", (at, MAX_ATTEMPTS),
            )
            cursor.execute(
                """UPDATE notification_delivery SET d_state='failed', d_error_code='lease_exhausted', d_lease_until=NULL
                   WHERE d_state='processing' AND d_lease_until<=%s AND d_attempts>=%s""", (at, MAX_ATTEMPTS),
            )
            cursor.execute(
                """UPDATE notification_event SET n_state='canceled'
                   WHERE n_state IN ('pending','processing') AND n_expires_at<=%s""", (at,),
            )
            cursor.execute(
                """UPDATE notification_delivery d JOIN notification_event n ON n.n_seq=d.n_seq
                   SET d.d_state='skipped', d.d_lease_until=NULL, d.d_error_code='expired'
                   WHERE n.n_state='canceled' AND d.d_state IN ('pending','processing')""",
            )
            cursor.execute(
                """SELECT * FROM notification_event WHERE n_state='pending' AND n_due_at<=%s
                   AND n_expires_at>%s ORDER BY n_due_at,n_seq LIMIT 100""", (at, at),
            )
            events = list(cursor.fetchall())
            connection.commit()
        results = []
        for event in events:
            results.extend(process_event(connection, event, send_fn))
        return {"mode": "send", "events_checked": len(events),
                "results": {state: results.count(state) for state in sorted(set(results))}}
    except Exception:
        connection.rollback()
        raise
    finally:
        try:
            if locked:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT RELEASE_LOCK(%s)", (LOCK_NAME,))
        finally:
            connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--send", action="store_true", help="DB 이벤트 처리와 실제 FCM 발송 허용")
    parser.add_argument("--loop", action="store_true", help="5초 간격으로 반복 (--send 필요)")
    args = parser.parse_args()
    if args.loop and not args.send:
        parser.error("--loop에는 --send가 필요합니다.")
    try:
        while True:
            print(json.dumps(run_cycle() if args.send else preview(), ensure_ascii=False), flush=True)
            if not args.loop:
                break
            time.sleep(5)
    except KeyboardInterrupt:
        return
    except Exception:
        # 자격 증명·SQL 파라미터를 노출하지 않고 오류 발생 시 즉시 정지합니다.
        raise SystemExit("알림 worker 중단: DB/Firebase 설정과 연결 상태를 확인해 주세요.") from None


if __name__ == "__main__":
    main()

# 최종 수정 일 : 2026-10-28
