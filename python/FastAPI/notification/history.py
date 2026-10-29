# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""본인 계정의 이벤트·발송 상태 조회. 실제 기기 도착/읽음 상태는 제공하지 않습니다."""

from fastapi import APIRouter, Depends, Query

from ..auth.token import current_account
from .device import device_connection, ERRORS

router = APIRouter()


@router.get("/events", responses=ERRORS, summary="본인 알림 이벤트·FCM 접수 상태 조회")
def select_events(limit: int = Query(default=50, ge=1, le=100), account: dict = Depends(current_account)) -> dict:
    placeholders = ",".join(["%s"] * len(account["member_ids"]))
    with device_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT n.n_seq,n.c_id_seq,n.n_type,n.r_seq,n.s_me_id,n.n_due_at,n.n_expires_at,n.n_state,
                          (SELECT COUNT(*) FROM notification_delivery d WHERE d.n_seq=n.n_seq AND d.d_state='accepted') AS accepted_devices,
                          (SELECT COUNT(*) FROM notification_delivery d WHERE d.n_seq=n.n_seq AND d.d_state='failed') AS failed_devices
                   FROM notification_event n JOIN customer c ON c.c_id_seq=n.c_id_seq
                   WHERE c.c_deletdate IS NULL AND n.c_id_seq IN (""" + placeholders + ") ORDER BY n.n_seq DESC LIMIT %s",
                (*account["member_ids"], limit),
            )
            rows = list(cursor.fetchall())
    return {"results": rows, "limit": limit, "accepted_means": "FCM 접수 성공이며 기기 도착/읽음 보장은 아닙니다."}

# 최종 수정 일 : 2026-10-28
