# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""업무 트랜잭션의 알림 outbox와 경기 시간 계산. 여기서는 FCM을 호출하지 않습니다."""

from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo



def now_kst() -> datetime:
    """DB의 업무 시각은 한국 시각의 naive DATETIME으로 저장합니다."""
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)


def match_times(row: dict) -> tuple[datetime, datetime]:
    def offset(value):
        if isinstance(value, timedelta):
            return value
        if isinstance(value, time):
            return timedelta(hours=value.hour, minutes=value.minute, seconds=value.second)
        parts = str(value).split(":")
        return timedelta(hours=int(parts[0]), minutes=int(parts[1]), seconds=int(parts[2]) if len(parts) > 2 else 0)
    midnight = datetime.combine(row["r_date"], time.min)
    start, end = midnight + offset(row["rs_time"]), midnight + offset(row["re_time"])
    if end <= start:
        end += timedelta(days=1)
    return start, end


def valid_match(row: dict) -> bool:
    # 이번 단계는 회원 1명당 예약 행이 있는 실력 매칭입니다. 팀 매칭은 별도 확장 대상입니다.
    # match 패키지를 import하지 않아 reservation → notification → reservation 순환을 방지합니다.
    canceled = str(row.get("r_category") or "").strip() == "2" or str(row.get("r_c_category") or "").strip() not in ("", "0")
    return row.get("r_check") == 1 and not canceled and row.get("reservation_category") == "1"


def enqueue(cursor, key: str, member: str, kind: str, due: datetime, expires: datetime,
            reservation=None, message=None) -> None:
    # UNIQUE(n_key,c_id_seq)로 반복 worker/중복 업무 호출을 멱등 처리합니다. 다른 SQL 오류는 숨기지 않습니다.
    cursor.execute(
        """INSERT INTO notification_event
           (n_key, c_id_seq, n_type, r_seq, s_me_id, n_due_at, n_expires_at, n_state)
           VALUES (%s,%s,%s,%s,%s,%s,%s,'pending')
           ON DUPLICATE KEY UPDATE n_key = VALUES(n_key)""",
        (key, member, kind, reservation, message, due, expires),
    )


def enqueue_message(cursor, message_id: int, sender: str, participants: set[str], at=None) -> None:
    at = at or now_kst()
    for member in sorted(participants - {sender}):
        enqueue(cursor, f"message:{message_id}", member, "message", at, at + timedelta(hours=24), message=message_id)


def enqueue_match(cursor, row: dict, confirmed: bool = False, at=None) -> None:
    if not valid_match(row):
        return
    at = at or now_kst()
    start, end = match_times(row)
    key = f"{row['r_seq']}:{start.isoformat()}"
    if confirmed and at < start:
        enqueue(cursor, "confirmed:" + key, row["c_id_seq"], "match_confirmed", at, start, reservation=row["r_seq"])
    if at < start:
        enqueue(cursor, "before10:" + key, row["c_id_seq"], "before10", start - timedelta(minutes=10), start,
                reservation=row["r_seq"])
    if at < end:
        enqueue(cursor, "absence10:" + key, row["c_id_seq"], "absence10", start + timedelta(minutes=10), end,
                reservation=row["r_seq"])


def enqueue_confirmed_slot(cursor, ground, day, start) -> None:
    cursor.execute(
        """SELECT r_seq, c_id_seq, g_code, r_date, rs_time, re_time, r_check,
                  r_category, r_c_category, reservation_category
           FROM reservation WHERE g_code=%s AND r_date=%s AND rs_time=%s AND r_check=1""",
        (ground, day, start),
    )
    for row in cursor.fetchall():
        enqueue_match(cursor, row, confirmed=True)


def plan_timers(cursor, at: datetime) -> int:
    # 기존 미래 성사 경기에도 시간 알림을 연결합니다. 과거 성사 알림은 소급 발송하지 않습니다.
    cursor.execute(
        """SELECT r_seq, c_id_seq, g_code, r_date, rs_time, re_time, r_check,
                  r_category, r_c_category, reservation_category
           FROM reservation WHERE r_check=1 AND reservation_category='1' AND r_date BETWEEN %s AND %s""",
        ((at - timedelta(days=1)).date(), (at + timedelta(days=1)).date()),
    )
    rows = cursor.fetchall()
    for row in rows:
        enqueue_match(cursor, row, at=at)
    return len(rows)


def eligible(cursor, event: dict, at: datetime) -> bool:
    if not event["n_due_at"] <= at < event["n_expires_at"]:
        return False
    member = event["c_id_seq"]
    if event["n_type"] == "message":
        cursor.execute(
            """SELECT s.me_id FROM send_message s
               JOIN messenger m ON m.me_id=s.me_id
               JOIN participate p ON p.me_id=s.me_id AND p.c_id_seq=%s
               JOIN customer c ON c.c_id_seq=p.c_id_seq
               WHERE s.s_me_id=%s AND s.c_id_seq<>%s AND c.c_deletdate IS NULL
                 AND COALESCE(m.me_state,'활성')<>'종료' LIMIT 1""", (member, event["s_me_id"], member),
        )
        return cursor.fetchone() is not None
    cursor.execute(
        """SELECT r.* FROM reservation r JOIN customer c ON c.c_id_seq=r.c_id_seq
           WHERE r.r_seq=%s AND r.c_id_seq=%s AND c.c_deletdate IS NULL""", (event["r_seq"], member),
    )
    row = cursor.fetchone()
    if row is None or not valid_match(row):
        return False
    start, end = match_times(row)
    # 예약 시각이 바뀐 경우 예전 시각으로 만든 이벤트는 폐기합니다.
    if event["n_key"].split(":", 1)[-1] != f"{row['r_seq']}:{start.isoformat()}":
        return False
    kind = event["n_type"]
    if kind == "match_confirmed":
        return at < start
    if kind == "before10":
        return start - timedelta(minutes=10) <= at < start
    if kind != "absence10" or not start + timedelta(minutes=10) <= at < end:
        return False
    cursor.execute(
        """SELECT c_r_r_attendance FROM c_result_record
           WHERE r_seq=%s AND c_id_seq=%s AND g_code=%s ORDER BY c_r_r_seq DESC LIMIT 1""",
        (event["r_seq"], member, row["g_code"]),
    )
    record = cursor.fetchone()
    # NULL·기록 없음은 결석으로 추정하지 않습니다. 여러 기록이면 최신 기록으로 판단합니다.
    return record is not None and record["c_r_r_attendance"] == 0

# 최종 수정 일 : 2026-10-28
