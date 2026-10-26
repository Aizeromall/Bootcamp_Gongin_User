# 작업자 : 김병재
# 최초 작업 일 : 2026-10-26

# 신고 작성 API (main.py의 prefix="/report"와 report.py의 prefix="/insert"가 붙어 실제 주소는 /report/insert)
#   POST /report/insert    경기 결과 화면에서 회원 이름 옆 [신고] 버튼을 눌러 신고 접수
# 저장 테이블: report (컬럼 추가/삭제 없이 기존 컬럼만 사용)
#   c_id_seq   신고자 회원 아이디
#   r_person   신고 대상 회원 아이디
#   r_option   신고 유형 번호 (문자열 "1"~"5")
#   r_reason   "[경기:경기코드] 상황 설명" 형태 (report에 경기코드 컬럼이 없어서 앞에 붙여 저장)
#   r_evidence 증거 자료 경로/URL (최대 3개를 쉼표로 이어서 저장, 선택)
#   r_date     신고일 (NOW())
#   h_id       처리자(본사). 접수 시점에는 NULL
import logging
import re
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

router = APIRouter()
logger = logging.getLogger(__name__)

# 신고 유형 번호 매핑 (r_option 컬럼에는 번호를 문자열로 저장)
REPORT_OPTION = {
    "1": "폭언·욕설",
    "2": "폭행·위협",
    "3": "고의적 거친 플레이",
    "4": "노쇼·지각",
    "5": "기타",
}

# 경기코드 형식: 구장코드_날짜_시작시간 (예: 1_20261026_180000)
MATCH_CODE_PATTERN = r"^\d+_\d{8}_\d{6}$"

# 증거 자료 컬럼(r_evidence)이 varchar(255)라서 넘지 않도록 제한
EVIDENCE_MAX_COUNT = 3
EVIDENCE_MAX_LENGTH = 255


class InsertReportRequest(BaseModel):
    """신고 작성 요청입니다. 신고자·신고대상 회원 아이디, 경기코드, 신고유형, 상황 설명을 보냅니다."""

    # Swagger Try it out 화면에 보이는 기본 예시 값
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "c_id_seq": "customer1_01",
                "r_person": "min_01",
                "c_r_r_code": "1_20261026_180000",
                "r_option": 2,
                "r_reason": "경기 중 상대 선수가 몸싸움을 하며 위협했습니다.",
                "r_evidence": ["https://example.com/evidence1.jpg"],
            }
        },
    )

    c_id_seq: str = Field(min_length=1, max_length=50, description="신고자 회원 아이디(customer PK)")
    r_person: str = Field(min_length=1, max_length=50, description="신고 대상 회원 아이디(customer PK)")
    c_r_r_code: str = Field(pattern=MATCH_CODE_PATTERN, description="대상 경기코드 (c_result_record의 c_r_r_code)")
    # r_option: 1 = 폭언·욕설 / 2 = 폭행·위협 / 3 = 고의적 거친 플레이 / 4 = 노쇼·지각 / 5 = 기타
    r_option: int = Field(ge=1, le=5, description="신고 유형 번호")
    r_reason: str = Field(min_length=5, max_length=2000, description="상황 설명 (5자 이상)")
    # 사진·영상 최대 3개 (선택). 업로드된 파일의 경로나 URL을 보냄
    r_evidence: Optional[list[str]] = Field(default=None, max_length=EVIDENCE_MAX_COUNT, description="증거 자료 경로/URL (최대 3개, 선택)")

    @field_validator("c_id_seq", "r_person", "c_r_r_code", "r_reason", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("r_evidence")
    @classmethod
    def check_evidence(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        if value is None:
            return None
        # 공백뿐인 항목은 버리고, 쉼표로 이어 저장하므로 항목 안에 쉼표가 들어가면 거절
        items = [item.strip() for item in value if item and item.strip()]
        if any("," in item for item in items):
            raise ValueError("증거 자료 경로에는 쉼표(,)를 사용할 수 없습니다.")
        if len(",".join(items)) > EVIDENCE_MAX_LENGTH:
            raise ValueError(f"증거 자료 경로는 합쳐서 {EVIDENCE_MAX_LENGTH}자 이하여야 합니다.")
        return items or None


# 신고 작성: 신고자/대상 회원 확인 → 두 회원이 같은 경기에 참여했는지 확인 → report 저장
# 같은 회원을 중복 신고하는 것은 막지 않음
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "본인 신고 또는 같은 경기 참여 기록 없음"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 아이디"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "신고 등록 실패"},
    },
)
def insert_report(payload: InsertReportRequest) -> dict:
    # 본인은 신고할 수 없음 (DB 조회 전에 먼저 걸러냄)
    if payload.c_id_seq == payload.r_person:
        raise HTTPException(status_code=400, detail="본인은 신고할 수 없습니다.")

    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 신고자·신고 대상 회원 존재 여부 확인 (c_id_seq가 customer PK)
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (payload.c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 신고자입니다.")
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (payload.r_person,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 신고 대상 회원입니다.")

            # 신고자와 대상 모두 해당 경기코드(c_result_record.c_r_r_code)에 기록이 있어야 신고 가능
            cursor.execute(
                """
                SELECT COUNT(DISTINCT c_id_seq) AS cnt
                FROM c_result_record
                WHERE c_r_r_code = %s AND c_id_seq IN (%s, %s)
                """,
                (payload.c_r_r_code, payload.c_id_seq, payload.r_person),
            )
            if cursor.fetchone()["cnt"] < 2:
                raise HTTPException(status_code=400, detail="신고자와 신고 대상이 함께 참여한 경기가 아닙니다.")

            # report에는 경기코드 컬럼이 없어서 r_reason 앞에 [경기:코드]를 붙여 저장
            reason = f"[경기:{payload.c_r_r_code}] {payload.r_reason}"
            evidence = ",".join(payload.r_evidence) if payload.r_evidence else None
            cursor.execute(
                """
                INSERT INTO report (c_id_seq, r_date, r_reason, r_person, r_evidence, r_option)
                VALUES (%s, NOW(), %s, %s, %s, %s)
                """,
                (payload.c_id_seq, reason, payload.r_person, evidence, str(payload.r_option)),
            )
            r_seq = cursor.lastrowid

        connection.commit()
        return {"result": "OK", "r_seq": r_seq}
    except HTTPException:
        raise  # 위에서 만든 400/404는 500으로 바뀌지 않게 그대로 전달
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("신고 등록 실패")
        raise HTTPException(status_code=500, detail="신고 등록에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-26
