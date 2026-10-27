# 2026-10-27
# 작업자 : 양태건

"""채팅방별 실시간 연결과 메시지 전송 관리 클래스만 정의합니다."""
import asyncio
import time
from weakref import WeakValueDictionary

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 파일당 클래스 하나 원칙에 맞춰 기존 구현을 이동했습니다.
class ConnectionManager:
    def __init__(self):
        self.rooms: dict[int, dict[WebSocket, dict]] = {}
        self.message_locks: WeakValueDictionary[int, asyncio.Lock] = WeakValueDictionary()
        self.socket_locks: dict[WebSocket, asyncio.Lock] = {}

    def register(self, me_id: int, websocket: WebSocket, member_id: str, expires_at: int):
        # 연결 또는 발송 작업이 참조하는 동안만 잠금을 유지하여 빈 방의 잠금이 쌓이지 않게 합니다.
        message_lock = self.message_locks.get(me_id)
        if message_lock is None:
            message_lock = asyncio.Lock()
            self.message_locks[me_id] = message_lock
        self.rooms.setdefault(me_id, {})[websocket] = {
            "member_id": member_id, "expires_at": expires_at, "message_lock": message_lock,
        }
        self.socket_locks[websocket] = asyncio.Lock()

    def disconnect(self, me_id: int, websocket: WebSocket):
        room = self.rooms.get(me_id)
        if room is not None:
            room.pop(websocket, None)
            if not room:
                self.rooms.pop(me_id, None)
        self.socket_locks.pop(websocket, None)

    async def send(self, websocket: WebSocket, event: dict):
        lock = self.socket_locks.get(websocket)
        if lock is None:
            return
        async with lock:
            await asyncio.wait_for(websocket.send_json(jsonable_encoder(event)), timeout=5)

    async def broadcast(self, me_id: int, message: dict, recipients: set[str]):
        async def deliver(websocket, data):
            try:
                if data["member_id"] not in recipients or data["expires_at"] <= time.time():
                    await websocket.close(code=1008)
                    self.disconnect(me_id, websocket)
                    return
                await self.send(websocket, {"type": "message", "message": message})
            except Exception:
                self.disconnect(me_id, websocket)
                try:
                    await websocket.close(code=1011)
                except Exception:
                    pass
        await asyncio.gather(*(deliver(socket, data) for socket, data in list(self.rooms.get(me_id, {}).items())))

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
