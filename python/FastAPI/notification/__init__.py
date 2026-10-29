# 작업자 : 최현준
# 최초 작업 일 : 2026-10-27
"""사용자 푸시 알림 router."""
from .device import router as notification_router
from .history import router as history_router

# 기기 등록·해제와 본인 발송 상태 조회만 노출합니다. 임의 발송 API는 제공하지 않습니다.
notification_router.include_router(history_router)

# 최종 수정 일 : 2026-10-28
