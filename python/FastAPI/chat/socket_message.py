# 2026-10-27
# 작업자 : 양태건

"""메시지 요청 모델, 이력 조회·저장과 WebSocket 송수신 router."""
import asyncio
import logging
import time
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from starlette.concurrency import run_in_threadpool

from .chat_room import chat_connection, current_member, decode_chat_token, require_room
from .socket_auth import SocketAuth
from .connection_manager import ConnectionManager

router = APIRouter()
logger = logging.getLogger(__name__)
manager = ConnectionManager()

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 메시지 클래스와 해당 프레임을 받는 WebSocket을 같은 파일에서 관리합니다.
class SocketMessage(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)
    type: Literal["message"]
    content: str = Field(min_length=1, max_length=10000)

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 참여자에게 최근·과거·재접속 후 메시지 이력을 반환합니다.
@router.get("/rooms/{me_id}/messages", summary="참여 채팅방 메시지 조회")
def select_messages(
    me_id: int = Path(gt=0), member_id: str = Depends(current_member),
    limit: int = Query(default=50, ge=1, le=100),
    before_id: Optional[int] = Query(default=None, gt=0),
    after_id: Optional[int] = Query(default=None, ge=0),
):
    if before_id is not None and after_id is not None:
        raise HTTPException(status_code=422, detail="before_id와 after_id 중 하나만 사용해 주세요.")
    condition = ""
    params = [me_id]
    if before_id is not None:
        condition = " AND s.s_me_id < %s"
        params.append(before_id)
    if after_id is not None:
        condition = " AND s.s_me_id > %s"
        params.append(after_id)
    order = "ASC" if after_id is not None else "DESC"
    params.append(limit)
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            require_room(cursor, me_id, member_id)
            cursor.execute(
                """SELECT s.s_me_id, s.me_id, s.c_id_seq, c.c_name, s.s_me_content, s.s_me_date, s.s_me_confirm
                   FROM send_message s LEFT JOIN customer c ON c.c_id_seq = s.c_id_seq
                   WHERE s.me_id = %s""" + condition + f" ORDER BY s.s_me_id {order} LIMIT %s",
                tuple(params),
            )
            # 수정 일 : 2026-10-27 / 작업자 : 양태건
            # PyMySQL은 빈 조회에서 튜플을 반환할 수 있으므로 리스트로 통일합니다.
            rows = list(cursor.fetchall())
    if after_id is None:
        rows.reverse()
    return {"results": rows, "limit": limit}

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 연결 시와 주기적으로 방 상태·참여 권한을 검사합니다.
def check_socket_access(me_id: int, member_id: str):
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            require_room(cursor, me_id, member_id)

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 메시지를 DB에 저장·commit한 뒤 방송할 데이터와 참여자를 반환합니다.
def store_message(me_id: int, member_id: str, content: str) -> tuple[dict, set[str]]:
    with chat_connection(write=True) as connection:
        with connection.cursor() as cursor:
            require_room(cursor, me_id, member_id, write=True)
            cursor.execute(
                """INSERT INTO send_message (c_id_seq, me_id, s_me_content, s_me_date, s_me_confirm)
                   VALUES (%s, %s, %s, NOW(), 0)""", (member_id, me_id, content),
            )
            message_id = cursor.lastrowid
            if not isinstance(message_id, int) or message_id <= 0:
                raise RuntimeError("메시지 번호를 가져오지 못했습니다.")
            cursor.execute(
                """SELECT s.s_me_id, s.me_id, s.c_id_seq, c.c_name, s.s_me_content, s.s_me_date, s.s_me_confirm
                   FROM send_message s LEFT JOIN customer c ON c.c_id_seq = s.c_id_seq
                   WHERE s.s_me_id = %s AND s.me_id = %s""", (message_id, me_id),
            )
            message = cursor.fetchone()
            if message is None:
                raise RuntimeError("저장된 메시지를 확인하지 못했습니다.")
            cursor.execute(
                """SELECT p.c_id_seq FROM participate p INNER JOIN customer c ON c.c_id_seq = p.c_id_seq
                   WHERE p.me_id = %s AND c.c_deletdate IS NULL""", (me_id,),
            )
            participants = {row["c_id_seq"] for row in cursor.fetchall()}
    return message, participants

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 방송 직전 최신 참여자를 확인합니다.
def active_participants(me_id: int) -> set[str]:
    # 방송 직전 최신 참여자를 다시 확인하여 방을 나간 연결에는 새 메시지를 보내지 않습니다.
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """SELECT p.c_id_seq FROM participate p INNER JOIN messenger m ON m.me_id = p.me_id
                   INNER JOIN customer c ON c.c_id_seq = p.c_id_seq
                   WHERE p.me_id = %s AND c.c_deletdate IS NULL AND COALESCE(m.me_state, '활성') <> '종료'""",
                (me_id,),
            )
            return {row["c_id_seq"] for row in cursor.fetchall()}

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 첫 인증 프레임 검증 후 SocketMessage를 받아 저장·실시간 전달합니다.
@router.websocket("/ws/{me_id}")
async def chat_socket(websocket: WebSocket, me_id: int = Path(gt=0)):
    await websocket.accept()
    try:
        try:
            auth = SocketAuth.model_validate(await asyncio.wait_for(websocket.receive_json(), timeout=10))
            claims = decode_chat_token(auth.access_token)
            member_id = claims["sub"]
            await run_in_threadpool(check_socket_access, me_id, member_id)
        except (ValidationError, ValueError, asyncio.TimeoutError):
            await websocket.close(code=1008, reason="채팅 인증 정보가 필요합니다.")
            return
        manager.register(me_id, websocket, member_id, claims["exp"])
        await manager.send(websocket, {"type": "ready", "me_id": me_id, "c_id_seq": member_id})
        while True:
            remaining = claims["exp"] - time.time()
            if remaining <= 0:
                await websocket.close(code=1008, reason="토큰이 만료되었습니다.")
                break
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=min(30, remaining))
            except asyncio.TimeoutError:
                decode_chat_token(auth.access_token)
                await run_in_threadpool(check_socket_access, me_id, member_id)
                continue
            try:
                payload = SocketMessage.model_validate(data)
            except (ValidationError, ValueError):
                await manager.send(websocket, {"type": "error", "detail": "메시지는 공백 없이 1~10000자로 입력해 주세요."})
                continue
            decode_chat_token(auth.access_token)
            # 같은 방의 저장·방송을 직렬 처리하여 단일 서버 내 메시지 순서를 유지합니다.
            async with manager.message_locks[me_id]:
                message, participants = await run_in_threadpool(store_message, me_id, member_id, payload.content)
                current = await run_in_threadpool(active_participants, me_id)
                await manager.broadcast(me_id, message, participants & current)
    except WebSocketDisconnect:
        pass
    except HTTPException as error:
        try:
            await websocket.close(code=1011 if error.status_code >= 500 else 1008, reason=error.detail)
        except Exception:
            pass
    except (ValueError, RuntimeError, asyncio.TimeoutError):
        try:
            await websocket.close(code=1008, reason="채팅 연결을 확인해 주세요.")
        except Exception:
            pass
    except Exception:
        logger.exception("WebSocket 채팅 처리 실패")
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
    finally:
        manager.disconnect(me_id, websocket)

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
