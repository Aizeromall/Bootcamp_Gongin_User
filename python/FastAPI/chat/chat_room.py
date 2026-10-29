# 2026-10-27
# 작업자 : 양태건

"""채팅 공통 인증·DB 처리와 방 조회·나가기·종료.

DB 컬럼 추가 없이 최초 participate_seq의 회원을 방장으로 사용합니다.
방장은 나갈 수 없으며 방을 종료할 수 있습니다. 참여 기록을 직접 삭제하면 방장 판단이 달라집니다.
"""
import logging
import os
import secrets
from contextlib import contextmanager
from typing import Optional

import jwt
import pymysql
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..database import connect
from ..auth.token import decode_token as decode_account_token

router = APIRouter()
logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
TOKEN_SECONDS = 1800
# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 미설정이면 프로세스마다 임시 키를 생성합니다. 재시작 시 재로그인이 필요합니다.
# 운영 시 CHAT_TOKEN_SECRET을 환경변수에 지정하고 실시간 연결은 단일 worker로 실행합니다.
TOKEN_SECRET = os.getenv("CHAT_TOKEN_SECRET") or secrets.token_urlsafe(48)
TOKEN_AUDIENCE = "gongin-chat"
TOKEN_ISSUER = "gongin-user-api"


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 채팅 기능의 DB 연결·트랜잭션은 이 파일에서 관리하고 메시지 기능에서도 사용합니다.
@contextmanager
def chat_connection(write: bool = False):
    connection = None
    try:
        connection = connect()
        yield connection
        if write:
            connection.commit()
    except HTTPException:
        if connection is not None and write:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None and write:
            connection.rollback()
        logger.exception("채팅 정보 충돌")
        raise HTTPException(status_code=409, detail="회원 또는 채팅방 정보를 확인해 주세요.")
    except Exception:
        if connection is not None and write:
            connection.rollback()
        logger.exception("채팅 DB 처리 실패")
        raise HTTPException(status_code=500, detail="채팅 처리 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


# JWT는 알고리즘·용도·발급자를 고정하여 확인하며 발신 회원은 토큰에서만 가져옵니다.
def decode_chat_token(token: str) -> dict:
    try:
        claims = jwt.decode(
            token, TOKEN_SECRET, algorithms=["HS256"], audience=TOKEN_AUDIENCE, issuer=TOKEN_ISSUER,
            options={"require": ["sub", "exp", "iat", "aud", "iss"]},
        )
        if not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 50:
            raise ValueError("회원 ID 오류")
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        # 일반 로그인 JWT도 사용하되 기존 채팅 전용 JWT의 서명키·audience는 그대로 보존합니다.
        # 채팅은 기존과 같이 종목별 ID 단위이며 기본값은 로그인 응답의 c_id_seq입니다.
        try:
            claims = decode_account_token(token)
        except HTTPException as error:
            # 공통 인증 미설정이어도 기존 채팅의 잘못된 JWT는 401로 처리합니다.
            raise HTTPException(status_code=401, detail="로그인이 필요하거나 토큰이 만료되었습니다.",
                                headers={"WWW-Authenticate": "Bearer"}) from error
        return {**claims, "sub": claims["c_id_seq"]}


def current_member(credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)) -> str:
    if credentials is None:
        raise HTTPException(status_code=401, detail="채팅 로그인이 필요합니다.", headers={"WWW-Authenticate": "Bearer"})
    return decode_chat_token(credentials.credentials)["sub"]


# 방장 ID는 참여 순서로 산출하며 이름·팀명으로 권한을 판단하지 않습니다.
ROOM_SELECT = """
    SELECT m.me_id, m.me_name, m.me_state, m.me_creation_time,
           (SELECT owner.c_id_seq FROM participate owner WHERE owner.me_id = m.me_id
            ORDER BY owner.participate_seq LIMIT 1) AS owner_id
    FROM messenger m
"""


# 모든 조회·송신에서 참여 여부를 검사합니다. 쓰기 시 방을 잠가 초대·탈퇴·종료와 순서를 맞춥니다.
def require_room(cursor, me_id: int, member_id: str, write: bool = False, owner: bool = False) -> dict:
    cursor.execute(ROOM_SELECT + " WHERE m.me_id = %s" + (" FOR UPDATE" if write else ""), (me_id,))
    room = cursor.fetchone()
    if room is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 채팅방입니다.")
    cursor.execute(
        """SELECT p.participate_seq FROM participate p
           INNER JOIN customer c ON c.c_id_seq = p.c_id_seq
           WHERE p.me_id = %s AND p.c_id_seq = %s AND c.c_deletdate IS NULL""",
        (me_id, member_id),
    )
    if cursor.fetchone() is None:
        raise HTTPException(status_code=403, detail="채팅방 참여자만 사용할 수 있습니다.")
    if room["me_state"] == "종료":
        raise HTTPException(status_code=409, detail="종료된 채팅방입니다.")
    if owner and room["owner_id"] != member_id:
        raise HTTPException(status_code=403, detail="방장만 사용할 수 있습니다.")
    return room



# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 내가 참여 중인 방만 조회합니다.
@router.get("/rooms", summary="내 채팅방 목록")
def select_rooms(member_id: str = Depends(current_member), limit: int = Query(default=20, ge=1, le=100),
                 offset: int = Query(default=0, ge=0)):
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                ROOM_SELECT + """ INNER JOIN participate p ON p.me_id = m.me_id
                    INNER JOIN customer c ON c.c_id_seq = p.c_id_seq
                    WHERE p.c_id_seq = %s AND c.c_deletdate IS NULL AND COALESCE(m.me_state, '활성') <> '종료'
                    ORDER BY m.me_id DESC LIMIT %s OFFSET %s""", (member_id, limit, offset),
            )
            rows = cursor.fetchall()
    return {"results": rows, "limit": limit, "offset": offset}


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 참여 권한을 확인한 뒤 방과 참여자 정보를 조회합니다.
@router.get("/rooms/{me_id}", summary="채팅방 및 참여자 조회")
def select_room(me_id: int = Path(gt=0), member_id: str = Depends(current_member)):
    with chat_connection() as connection:
        with connection.cursor() as cursor:
            room = require_room(cursor, me_id, member_id)
            cursor.execute(
                """SELECT p.c_id_seq, c.c_name FROM participate p
                   INNER JOIN customer c ON c.c_id_seq = p.c_id_seq
                   WHERE p.me_id = %s ORDER BY p.participate_seq""", (me_id,),
            )
            participants = cursor.fetchall()
    return {**room, "participants": participants}


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 방장은 나가기를 차단하고 일반 회원의 참여 기록만 삭제합니다.
@router.delete("/rooms/{me_id}/leave", summary="채팅방 나가기 (방장 제외)")
def leave_room(me_id: int = Path(gt=0), member_id: str = Depends(current_member)):
    with chat_connection(write=True) as connection:
        with connection.cursor() as cursor:
            room = require_room(cursor, me_id, member_id, write=True)
            if room["owner_id"] == member_id:
                raise HTTPException(status_code=409, detail="방장은 나갈 수 없습니다. 채팅방 종료를 사용해 주세요.")
            cursor.execute("DELETE FROM participate WHERE me_id = %s AND c_id_seq = %s", (me_id, member_id))
    return {"result": "OK", "me_id": me_id}


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 방장만 방을 종료할 수 있으며 메시지·최초 참여 이력은 보존합니다.
@router.delete("/rooms/{me_id}", summary="방장의 채팅방 종료")
def close_room(me_id: int = Path(gt=0), member_id: str = Depends(current_member)):
    with chat_connection(write=True) as connection:
        with connection.cursor() as cursor:
            require_room(cursor, me_id, member_id, write=True, owner=True)
            cursor.execute("UPDATE messenger SET me_state = '종료' WHERE me_id = %s", (me_id,))
    return {"result": "OK", "me_id": me_id, "me_state": "종료"}

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-27 / 작업자 : 최현준 (일반 로그인 JWT 호환)
