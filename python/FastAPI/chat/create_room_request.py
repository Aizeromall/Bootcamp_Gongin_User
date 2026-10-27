# 2026-10-27
# 작업자 : 양태건

"""채팅방 생성 요청 모델과 생성 router를 함께 관리합니다."""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import Field

from .chat_request import ChatRequest
from .chat_room import chat_connection, current_member

router = APIRouter()

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 요청 클래스와 이 클래스를 사용하는 API를 같은 파일로 모았습니다.
class CreateRoomRequest(ChatRequest):
    # 생략하면 customer.c_team을 방 이름으로 사용합니다.
    me_name: Optional[str] = Field(default=None, min_length=1, max_length=100)

# 소속팀명을 기본 이름으로 사용하고 생성자를 최초 참여자로 등록합니다.
# 수정 일 : 2026-10-27 / 작업자 : 양태건
# Swagger에서 기본 팀명 생성과 직접 이름 지정 예시를 선택해 테스트할 수 있습니다.
@router.post(
    "/rooms", status_code=status.HTTP_201_CREATED, summary="채팅방 생성",
    description="먼저 /chat/token에서 토큰을 발급받아 Authorize에 설정하세요. 기본 팀명으로 만들려면 {}를 전송합니다.",
)
def create_room(
    payload: CreateRoomRequest = Body(openapi_examples={
        "team_name": {"summary": "회원 소속팀명으로 채팅방 생성", "value": {}},
        "custom_name": {"summary": "직접 지정한 이름으로 생성", "value": {"me_name": "우리 팀 채팅방"}},
    }),
    member_id: str = Depends(current_member),
):
    with chat_connection(write=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT c_name, c_team FROM customer WHERE c_id_seq = %s AND c_deletdate IS NULL FOR UPDATE", (member_id,))
            member = cursor.fetchone()
            if member is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
            team_name = (member["c_team"] or "").strip()
            default_name = team_name if team_name not in ("", "무소속", "없음") else f"{member['c_name']}님의 채팅방"
            name = payload.me_name or default_name
            cursor.execute("INSERT INTO messenger (me_name, me_state, me_creation_time) VALUES (%s, '활성', NOW())", (name,))
            me_id = cursor.lastrowid
            if not isinstance(me_id, int) or me_id <= 0:
                raise RuntimeError("채팅방 번호를 가져오지 못했습니다.")
            cursor.execute("INSERT INTO participate (c_id_seq, me_id) VALUES (%s, %s)", (member_id, me_id))
    return {"result": "OK", "me_id": me_id, "me_name": name, "me_state": "활성", "owner_id": member_id}

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
