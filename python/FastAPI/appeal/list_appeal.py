# 작업자 : 김병재
# 최초 작업 일 : 2026-10-27

# 내 이의신청 내역 조회 API (main.py의 prefix="/appeal"와 appeal.py의 prefix="/list"가 붙어 실제 주소는 /appeal/list)
#   GET /appeal/list?c_id_seq=...    제재 내역 화면 아래쪽 "이의신청 내역" 목록(최신순)을 조회
# 조회 테이블: customer(회원 확인), appeal(이의신청), c_sanction(대상 제재), headquarter(재심의 처리자 이름)
#
# [a_reason 형식] "[제재:번호][사유:종류][증빙:링크들] 상세 내용" (appeal_common.py 참고)
# [상태] 접수 / 재심의 중 / 인용 / 기각 (appeal 테이블에 상태 컬럼이 없어서 h_id와 [결과:...] 태그로 판단)
# [진행 단계] 화면의 "접수 → 재심의 중 → 결과 통보"는 steps로 내려주고, 단계별 날짜는 저장된 곳이 없어서 접수일만 제공
import logging
import re

from fastapi import APIRouter, HTTPException, Query, status

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
from .appeal_common import STATE_REVIEWING, STATE_TEXT, get_state, parse_appeal_reason

router = APIRouter()
logger = logging.getLogger(__name__)

DETAIL_PATTERN = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)  # cs_detail의 "[제재종류] 내용" 분리용


# DB에서 받은 이의신청 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# sanctions: {cs_seq: 제재 1줄}. 대상 제재 이름/내용을 붙이는 데 사용
def appeal_to_dict(row: dict, sanctions: dict) -> dict:
    tags, body = parse_appeal_reason(row["a_reason"])
    state = get_state(row["h_id"], tags)

    # 증빙 링크: [증빙:...] 태그(쉼표로 구분)
    evidence = [link.strip() for link in tags.get("증빙", "").split(",") if link.strip()]

    # 대상 제재: [제재:번호] 태그가 숫자가 아니거나 제재가 없으면 None
    cs_seq = int(tags["제재"]) if tags.get("제재", "").isdigit() else None
    sanction_row = sanctions.get(cs_seq)
    sanction = None
    if sanction_row is not None:
        found = DETAIL_PATTERN.match(sanction_row["cs_detail"] or "")
        sanction = {
            "cs_seq": cs_seq,                                                                # 제재번호
            "cs_date": sanction_row["cs_date"],                                              # 제재일
            "sanction_type": found.group(1).strip() if found else "기타",                    # 제재 종류 (경고 / 이용정지 / 기타)
            "cs_detail": found.group(2) if found else (sanction_row["cs_detail"] or ""),     # 제재 내용 (예: 노쇼 (3/1 마포 소셜매치))
        }

    reason_type = tags.get("사유")
    # 카드 제목 "경고 · 노쇼 (3/1 마포 소셜매치)", 제재를 찾지 못하면 이의신청 상세 내용 앞부분
    title = f"{sanction['sanction_type']} · {sanction['cs_detail']}" if sanction else body[:30]
    # 카드 부제목 "사유 · 사실과 다름 · 증빙 링크 1개"
    parts = []
    if reason_type:
        parts.append(f"사유 · {reason_type}")
    if evidence:
        parts.append(f"증빙 링크 {len(evidence)}개")

    return {
        "a_seq": row["a_seq"],                         # 이의신청번호
        "a_date": row["a_date"],                       # 신청일 ("03.03 신청")
        "state": state,                                # 0 = 접수 / 1 = 재심의 중 / 2 = 인용 / 3 = 기각
        "state_text": STATE_TEXT[state],               # 카드 왼쪽 위 태그
        "title": title,                                # 카드 제목
        "subtitle": " · ".join(parts),                 # 카드 부제목
        "reason_type": reason_type,                    # 이의 사유 종류
        "a_reason": body,                              # 상세 내용
        "a_evidence": evidence,                        # 증빙 링크 목록
        "cs_seq": cs_seq,                              # 대상 제재번호
        "sanction": sanction,                          # 대상 제재 (없으면 None)
        "h_id": row["h_id"],                           # 재심의를 시작한 본사 직원 아이디 (접수면 None)
        "h_name": row["h_name"],                       # 재심의를 시작한 본사 직원 이름
        # 진행 단계: done은 이미 지나간(또는 지금인) 단계. 결과 통보는 인용/기각이 나왔을 때 완료
        "steps": [
            {"name": "접수", "done": True},
            {"name": "재심의 중", "done": state >= STATE_REVIEWING},
            {"name": "결과 통보", "done": state > STATE_REVIEWING},
        ],
    }


# 내 이의신청 내역 조회: 회원 아이디(c_id_seq)로 신청한 이의신청을 최신순으로 조회
@router.get(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 아이디"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "이의신청 내역 조회 실패"},
    },
)
def list_appeal(
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

            # 이의신청 조회 (재심의 처리자 이름은 headquarter에서 가져옴)
            cursor.execute(
                """
                SELECT a.a_seq, a.a_date, a.a_reason, a.h_id, h.h_name
                FROM appeal AS a
                LEFT JOIN headquarter AS h ON h.h_id = a.h_id
                WHERE a.c_id_seq = %s
                ORDER BY a.a_date DESC, a.a_seq DESC
                """,
                (c_id_seq,),
            )
            rows = cursor.fetchall()  # database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄

            # 이 회원의 제재를 한 번에 조회해서 이의신청의 대상 제재와 연결
            cursor.execute(
                "SELECT cs_seq, cs_date, cs_detail FROM c_sanction WHERE c_id_seq = %s",
                (c_id_seq,),
            )
            sanctions = {row["cs_seq"]: row for row in cursor.fetchall()}

        results = [appeal_to_dict(row, sanctions) for row in rows]
        return {
            "c_id_seq": c_id_seq,
            "total": len(results),   # "이의신청 내역 N건"의 N
            "results": results,
        }
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except Exception:
        logger.exception("이의신청 내역 조회 실패")
        raise HTTPException(status_code=500, detail="이의신청 내역 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-27
