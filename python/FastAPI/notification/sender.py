# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""Android FCM 메시지 구성·발송. FCM accepted는 기기 표시/읽음 완료를 뜻하지 않습니다."""

import os
from datetime import timedelta
from threading import Lock

import firebase_admin
from firebase_admin import messaging

from .events import now_kst

_lock = Lock()
COPY = {
    "message": ("새 메시지", "참여 중인 채팅방에 메시지가 도착했습니다."),
    "match_confirmed": ("매치 성사", "예약한 경기의 매치가 성사되었습니다."),
    "before10": ("경기 시작 10분 전", "경기 시작이 곧 예정되어 있습니다. 예약을 확인해 주세요."),
    "absence10": ("출석 확인 안내", "경기 시작 10분이 지났습니다. 출석을 확인해 주세요."),
}


def firebase_app():
    project = os.getenv("FIREBASE_PROJECT_ID", "").strip()
    if not project:
        raise RuntimeError("FIREBASE_PROJECT_ID 설정이 필요합니다.")
    with _lock:
        try:
            return firebase_admin.get_app("gongin-notifications")
        except ValueError:
            return firebase_admin.initialize_app(options={"projectId": project, "httpTimeout": 15}, name="gongin-notifications")


def send(event: dict, token: str, app=None) -> str:
    title, body = COPY[event["n_type"]]
    remaining = int((event["n_expires_at"] - now_kst()).total_seconds())
    if remaining <= 0:
        raise ValueError("알림 유효 시간이 지났습니다.")
    # 상세 채팅 본문·회원 개인정보는 잠금 화면으로 보내지 않습니다.
    # 앱이 계정 전환 전의 알림을 열지 않도록 수신 회원 FK를 data에만 포함합니다.
    data = {"event_id": str(event["n_seq"]), "type": event["n_type"], "c_id_seq": event["c_id_seq"]}
    if event["r_seq"] is not None:
        data["r_seq"] = str(event["r_seq"])
    if event["s_me_id"] is not None:
        data["s_me_id"] = str(event["s_me_id"])
    message = messaging.Message(
        token=token, notification=messaging.Notification(title=title, body=body), data=data,
        android=messaging.AndroidConfig(priority="high", ttl=timedelta(seconds=remaining),
                                        notification=messaging.AndroidNotification(tag="event-" + str(event["n_seq"]))),
    )
    return messaging.send(message, app=app or firebase_app())

# 최종 수정 일 : 2026-10-28
