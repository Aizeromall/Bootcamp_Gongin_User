# 2026-10-27
# 작업자 : 양태건

"""WebSocket 인증 프레임 모델 클래스만 정의합니다."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 파일당 클래스 하나 원칙에 맞춰 기존 구현을 이동했습니다.
class SocketAuth(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)
    type: Literal["auth"]
    access_token: str = Field(min_length=1, max_length=4096)

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
