# 2026-10-26
# 작업자 : 양태건

"""기능별 게시판 router를 모아 main.py에 전달합니다.

게시글 조회: select.py / 작성: insert.py / 수정: update.py / 삭제: delete.py
댓글 조회·작성·수정·삭제: comment.py
각 기능 파일이 database.py의 connect()를 직접 사용합니다.
main.py의 prefix="/board"와 결합합니다.
실제 저장은 board_a_write 통합 테이블을 사용합니다.
댓글 수정·삭제는 게시글 번호 bulletin_seq를 쿼리로 함께 전달해야 합니다.
"""
from fastapi import APIRouter

from .select import router as select_router
from .insert import router as insert_router
from .update import router as update_router
from .delete import router as delete_router
from .comment import router as comment_router

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# board.py는 router 통합만 담당하고 각 기능은 해당 이름의 파일에서 구현합니다.
router = APIRouter()
router.include_router(select_router)
router.include_router(insert_router)
router.include_router(update_router)
router.include_router(delete_router)
router.include_router(comment_router)


# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
