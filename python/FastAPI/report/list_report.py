# 작업자 : 김병재
# 최초 작업 일 : 2026-10-26

# 내 신고 내역 조회 API (main.py의 prefix="/report"와 report.py의 prefix="/list"가 붙어 실제 주소는 /report/list)
#   GET /report/list?c_id_seq=...    내가 신고한 목록을 최신순으로 조회
# 조회 테이블: report(신고), customer(신고 대상 이름), ground(경기 구장명), c_sanction(제재 여부)
# 처리 상태: 본사가 신고 대상에게 제재(c_sanction)를 등록하면 "처리완료", 아직 없으면 "심의중"
#   (신고일 r_date 이후에 등록된 제재만 인정)
import logging
import re

from fastapi import APIRouter, HTTPException, Query, status

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

router = APIRouter()
logger = logging.getLogger(__name__)

# 신고 유형 번호 매핑 (insert_report.py와 동일, r_option에는 번호 문자열이 저장됨)
REPORT_OPTION = {
    "1": "폭언·욕설",
    "2": "폭행·위협",
    "3": "고의적 거친 플레이",
    "4": "노쇼·지각",
    "5": "기타",
}

# r_reason 앞에 붙어 있는 "[경기:경기코드] 상황 설명" 분리용
# 경기코드 = 구장코드_날짜_시작시간 (예: 1_20261026_180000)
REASON_PATTERN = re.compile(r"^\[경기:(\d+)_(\d{8})_(\d{6})\]\s*(.*)$", re.DOTALL)


# DB에서 받은 신고 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# ground_names: {구장코드(int): 구장명} (경기 구장명 표시용)
def report_to_dict(row: dict, ground_names: dict) -> dict:
    reason = row["r_reason"] or ""
    match = REASON_PATTERN.match(reason)

    match_code = None
    match_title = None
    match_date = None
    match_time = None
    content = reason
    if match:
        g_code, ymd, hms = int(match.group(1)), match.group(2), match.group(3)
        match_code = f"{g_code}_{ymd}_{hms}"
        match_title = ground_names.get(g_code)  # 구장이 삭제된 경우 None
        match_date = f"{ymd[:4]}-{ymd[4:6]}-{ymd[6:]}"
        match_time = f"{hms[:2]}:{hms[2:4]}"
        content = match.group(4)  # [경기:...] 부분을 뺀 순수 상황 설명

    processed = bool(row["sanctioned"])
    return {
        "r_seq": row["r_seq"],                                         # 신고번호
        "r_date": row["r_date"],                                       # 신고일
        "r_option": row["r_option"],                                   # 신고 유형 번호
        "r_option_name": REPORT_OPTION.get(row["r_option"] or "", "기타"),  # 신고 유형명
        "r_person": row["r_person"],                                   # 신고 대상 회원 아이디
        "r_person_name": row["r_person_name"],                         # 신고 대상 회원 이름
        "c_r_r_code": match_code,                                      # 경기코드
        "match_title": match_title,                                    # 경기 구장명
        "match_date": match_date,                                      # 경기 날짜
        "match_time": match_time,                                      # 경기 시작시간
        "r_reason": content,                                           # 상황 설명
        "r_evidence": row["r_evidence"].split(",") if row["r_evidence"] else [],  # 증거 자료 목록
        "state": 1 if processed else 0,                                # 0 = 심의중 / 1 = 처리완료
        "state_text": "처리완료" if processed else "심의중",
    }


# 내 신고 내역 조회: 회원 아이디(c_id_seq)로 본인이 접수한 신고를 최신순으로 조회
@router.get(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 아이디"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "신고 내역 조회 실패"},
    },
)
def list_report(
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

            # 신고 대상 이름은 customer에서, 처리 여부는 신고일 이후 c_sanction이 있는지로 판단
            # (EXISTS라서 제재가 여러 건이어도 신고 1건이 중복으로 나오지 않음)
            cursor.execute(
                """
                SELECT r.r_seq, r.r_date, r.r_option, r.r_person, c.c_name AS r_person_name,
                       r.r_reason, r.r_evidence,
                       EXISTS (
                           SELECT 1 FROM c_sanction AS s
                           WHERE s.c_id_seq = r.r_person AND s.cs_date >= r.r_date
                       ) AS sanctioned
                FROM report AS r
                LEFT JOIN customer AS c ON c.c_id_seq = r.r_person
                WHERE r.c_id_seq = %s
                ORDER BY r.r_date DESC, r.r_seq DESC
                """,
                (c_id_seq,),
            )
            rows = cursor.fetchall()

            # 신고에 적힌 경기코드의 구장코드로 구장명을 한 번에 조회 (신고마다 쿼리하지 않음)
            g_codes = set()
            for row in rows:
                found = REASON_PATTERN.match(row["r_reason"] or "")
                if found:
                    g_codes.add(int(found.group(1)))
            ground_names = {}
            if g_codes:
                placeholders = ", ".join(["%s"] * len(g_codes))
                cursor.execute(
                    f"SELECT g_code, g_name FROM ground WHERE g_code IN ({placeholders})",
                    tuple(g_codes),
                )
                ground_names = {g["g_code"]: g["g_name"] for g in cursor.fetchall()}

        # total: 신고 내역 건수 표시용
        return {"total": len(rows), "results": [report_to_dict(row, ground_names) for row in rows]}
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except Exception:
        logger.exception("신고 내역 조회 실패")
        raise HTTPException(status_code=500, detail="신고 내역 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-26
