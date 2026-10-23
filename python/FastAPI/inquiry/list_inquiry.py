# 작업자 : 김병재
# 최초 작업 일 : 2026-10-23

import logging

from fastapi import APIRouter, HTTPException, Query, status

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)

# i_option 매핑 (관리자앱과 동일). 문의 제목으로 사용
# i_option 컬럼이 varchar라 키를 문자열로 관리
INQUIRY_OPTION = {
    "1": "매니저 신고 문의",
    "2": "구장 예약 문의",
    "3": "환불 문의",
    "4": "기타 문의",
}


# 문의 제목 생성: 옵션이 있으면 옵션명, 없으면 문의 내용 앞 30자
def make_title(row: dict) -> str:
    return INQUIRY_OPTION.get(row["i_option"]) or (row["post"] or "")[:30]


# 내 문의 목록 조회: 회원 아이디(c_id_seq)로 본인이 작성한 원글(level 0)만 최신순으로 조회
@router.get(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 아이디"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "문의 조회 실패"},
    },
)
def list_inquiry(
    c_id_seq: str = Query(min_length=1, max_length=50, description="회원 아이디(customer PK, 예: customer1_01)"),
) -> dict:
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 회원 존재 여부 확인 (c_id_seq가 customer PK)
            c_id_seq = c_id_seq.strip()
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 답변자 이름은 headquarter에서 가져옴 (미답변이면 NULL)
            cursor.execute(
                """
                SELECT q.i_seq, q.i_option, q.post, q.i_date, q.i_state,
                       q.inquiry_detail, q.i_answer_date, q.h_id, h.h_name
                FROM inquiry q
                LEFT JOIN headquarter h ON h.h_id = q.h_id
                WHERE q.level = 0 AND q.c_id_seq = %s
                ORDER BY q.i_date DESC, q.i_seq DESC
                """,
                (c_id_seq,),
            )
            rows = cursor.fetchall()

        for row in rows:
            row["title"] = make_title(row)
        # total: 문의 내역 탭의 건수 배지용
        return {"total": len(rows), "results": rows}
    except HTTPException:
        raise
    except Exception:
        logger.exception("문의 조회 실패")
        raise HTTPException(status_code=500, detail="문의 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()
