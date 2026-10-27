# 2026-10-27
# 작업자 : 양태건

"""채팅 기능별 router 통합. 모델과 해당 API는 각 기능 파일에 함께 정의합니다."""
from fastapi import APIRouter

from .chat_login_request import router as login_router
from .create_room_request import router as create_room_router
from .invite_request import router as invite_router
from .chat_room import router as room_router
from .socket_message import router as message_router

# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 기존 /chat API 주소와 Swagger 분류를 유지합니다.
router = APIRouter(prefix="/chat")
router.include_router(login_router, tags=["Chat Room"])
router.include_router(create_room_router, tags=["Chat Room"])
router.include_router(invite_router, tags=["Chat Room"])
router.include_router(room_router, tags=["Chat Room"])
router.include_router(message_router, tags=["Chat Message"])


# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
