# 2026-10-26
# 작업자 : 양태건

"""게시글 삭제를 담당합니다."""

import logging

import pymysql
from fastapi import APIRouter, HTTPException, Path, Query


from ..database import connect
from ..team_match.lineup import unpack

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 실제 DB board_a_write 사용: comment_seq=0은 게시글, 양수는 댓글입니다.
# 모든 댓글 식별·변경은 게시글 번호와 댓글 번호의 복합 PK를 사용합니다.
router = APIRouter()
logger = logging.getLogger(__name__)

# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 게시글 삭제만 담당하며 댓글 개별 삭제 API는 comment.py에서 관리합니다.
# 4. 게시글 삭제: 작성자만 삭제할 수 있으며 댓글까지 함께 삭제합니다.
# 자기 참조 FK는 먼저 연결을 해제한 뒤 삭제하고, 어느 단계든 실패하면 전체 rollback합니다.
@router.delete("/delete/{bulletin_seq}", summary="본인 게시글 삭제")
def delete_board(
    bulletin_seq: int = Path(gt=0),
    c_id_seq: str = Query(min_length=1, max_length=50),
):
    c_id_seq = c_id_seq.strip()
    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 이 기능에서 직접 연결하고, 실패 시 롤백한 뒤 연결을 해제합니다.
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 작성 회원이 실제로 존재하는지 확인합니다.
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
            # 게시글 존재 확인 및 쓰기 충돌 방지를 위한 행 잠금입니다.
            cursor.execute('SELECT bulletin_seq, c_id_seq, board_content FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = 0 FOR UPDATE', (bulletin_seq,))
            row = cursor.fetchone()
            if row is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 게시글입니다.")
            if row["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 게시글만 삭제할 수 있습니다.")
            if unpack(row.get('board_content')):
                raise HTTPException(409, '출전 예약이 연결된 매칭 글은 삭제할 수 없습니다.')
            cursor.execute("UPDATE board_a_write SET reply_to_comment_seq = NULL WHERE bulletin_seq = %s", (bulletin_seq,))
            cursor.execute("DELETE FROM board_a_write WHERE bulletin_seq = %s AND comment_seq > 0", (bulletin_seq,))
            comments_deleted = cursor.rowcount
            cursor.execute("DELETE FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = 0", (bulletin_seq,))
        connection.commit()
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("게시판 참조 관계 충돌")
        raise HTTPException(status_code=409, detail="연결된 게시글 또는 댓글 정보를 확인해 주세요.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("게시판 처리 실패")
        raise HTTPException(status_code=500, detail="게시판 처리 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()
    return {"result": "OK", "bulletin_seq": bulletin_seq, "comments_deleted": comments_deleted}

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
