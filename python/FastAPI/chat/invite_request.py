# 2026-10-27
# 작업자 : 양태건

"""회원 초대 요청 모델과 초대 router를 함께 관리합니다."""
from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import Field, field_validator

from .chat_request import ChatRequest
from .chat_room import chat_connection, current_member, require_room

router = APIRouter()

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 요청 클래스와 이 클래스를 사용하는 API를 같은 파일로 모았습니다.
class InviteRequest(ChatRequest):
    member_ids: list[str] = Field(min_length=1, max_length=50, description="초대할 종목별 회원 ID 목록")

    @field_validator("member_ids")
    @classmethod
    def validate_members(cls, values: list[str]) -> list[str]:
        values = [value.strip() for value in values]
        if any(not value or len(value) > 50 for value in values):
            raise ValueError("회원 ID는 1~50자로 입력해 주세요.")
        return list(dict.fromkeys(values))

# 방장만 초대할 수 있으며 회원은 초대 즉시 참여합니다.
@router.post("/rooms/{me_id}/invite", summary="방장의 회원 초대")
def invite_members(payload: InviteRequest, me_id: int = Path(gt=0), member_id: str = Depends(current_member)):
    with chat_connection(write=True) as connection:
        with connection.cursor() as cursor:
            require_room(cursor, me_id, member_id, write=True, owner=True)
            added = []
            existing = []
            for target in payload.member_ids:
                cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s AND c_deletdate IS NULL", (target,))
                if cursor.fetchone() is None:
                    raise HTTPException(status_code=404, detail=f"존재하지 않는 회원입니다: {target}")
                cursor.execute("SELECT 1 FROM participate WHERE me_id = %s AND c_id_seq = %s", (me_id, target))
                if cursor.fetchone() is not None:
                    existing.append(target)
                    continue
                cursor.execute("INSERT INTO participate (c_id_seq, me_id) VALUES (%s, %s)", (target, me_id))
                added.append(target)
    return {"result": "OK", "me_id": me_id, "invited": added, "already_joined": existing}

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
