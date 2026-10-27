# 2026-10-27
# 작업자 : 양태건

"""채팅 요청의 공통 검증 설정 클래스만 정의합니다."""
from pydantic import BaseModel, ConfigDict

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 파일당 클래스 하나 원칙에 맞춰 기존 구현을 이동했습니다.
class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, hide_input_in_errors=True)

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
