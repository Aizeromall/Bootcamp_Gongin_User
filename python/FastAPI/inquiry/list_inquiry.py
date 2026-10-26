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


# 수정 일 : 2026-10-26 / 작업자 : 양태건
# 디버그: 재귀 호출 없이 부모 관계를 따라 답변을 원글별로 묶어 깊은 대화도 표시합니다.
def group_threads(rows: list[dict]) -> list[dict]:
    children: dict[int, list[dict]] = {}
    roots = []
    for row in rows:
        row["title"] = make_title(row)
        if row["level"] == 0 and row["i_comment_seq"] is None:
            roots.append(row)
        elif row["i_comment_seq"] is not None:
            children.setdefault(row["i_comment_seq"], []).append(row)
    for root in roots:
        replies = []
        stack = list(reversed(children.get(root["i_seq"], [])))
        seen = {root["i_seq"]}
        while stack:
            row = stack.pop()
            if row["i_seq"] in seen:
                continue
            seen.add(row["i_seq"])
            replies.append(row)
            stack.extend(reversed(children.get(row["i_seq"], [])))
        root["replies"] = replies
        root["reply_count"] = len(replies)
    return list(reversed(roots))


# 내 원글과 그에 연결된 모든 깊이의 답변을 조회합니다.
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
                       q.c_id_seq, q.level, q.i_comment_seq,
                       q.inquiry_detail, q.i_answer_date, q.h_id, h.h_name
                FROM inquiry q
                LEFT JOIN headquarter h ON h.h_id = q.h_id
                WHERE q.c_id_seq = %s
                ORDER BY q.i_date ASC, q.i_seq ASC
                """,
                (c_id_seq,),
            )
            rows = cursor.fetchall()

        # 수정 일 : 2026-10-26 / 작업자 : 양태건
        # total은 원글 건수를 유지하고 답변은 각 원글의 replies에 담습니다.
        threads = group_threads(rows)
        return {"total": len(threads), "results": threads}
    except HTTPException:
        raise
    except Exception:
        logger.exception("문의 조회 실패")
        raise HTTPException(status_code=500, detail="문의 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
