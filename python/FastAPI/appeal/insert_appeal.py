# 작업자 : 김병재
# 최초 작업 일 : 2026-10-27

# 이의신청 접수 API (main.py의 prefix="/appeal"와 appeal.py의 prefix="/insert"가 붙어 실제 주소는 /appeal/insert)
#   POST /appeal/insert    제재 내역 화면의 [이의신청 하기] → 이의신청 화면의 [이의신청 제출]
# 저장 테이블: appeal (컬럼 추가/삭제 없이 기존 컬럼만 사용)
#   c_id_seq   이의신청 회원 아이디 (제재를 받은 본인)
#   a_reason   "[제재:번호][사유:종류][증빙:링크1,링크2] 상세 내용" 형태 (태그 형식은 appeal_common.py 참고)
#   a_evidence 50자 제한이라 사용하지 않고 빈 값('')으로 저장 (NOT NULL 컬럼)
#   a_date     신청일 (NOW())
#   h_id       처리자(본사). 접수 시점에는 NULL → 본사가 [재심의 시작]을 누르면 값이 들어감
# 조회 테이블: customer(회원 확인), c_sanction(대상 제재 확인), appeal(제재 1건당 1회 확인)
#
# [접수 조건] 화면의 "이의신청은 제재 1건당 1회 가능"과 제재 내역의 이의신청 규칙을 서버에서도 확인
#   - 본인에게 부여된 제재일 것
#   - 소멸되지 않은 경고 또는 이용정지일 것 (그 외 종류는 불가)
#   - 제재일부터 7일 안일 것
#   - 같은 제재에 이미 이의신청을 한 적이 없을 것 (인용/기각으로 끝난 건도 다시 신청 불가)
import logging
import re
from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
from .appeal_common import APPEAL_TYPES, TAG_PATTERN, parse_appeal_reason

router = APIRouter()
logger = logging.getLogger(__name__)

# 사용자 앱 sanction/list_sanction.py와 같은 기준
WARNING_EXPIRE_DAYS = 90  # 경고는 제재일로부터 90일 후 소멸
APPEAL_DAYS = 7           # 이의신청은 제재일부터 7일까지 가능
DETAIL_PATTERN = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)  # cs_detail의 "[제재종류] 내용" 분리용
APPEALABLE_TYPES = ("경고", "이용정지")  # 이의신청이 가능한 제재 종류

# 증빙 링크 제한: 화면에 "증빙 자료 링크 (1/3)"로 최대 3개
EVIDENCE_MAX_COUNT = 3
EVIDENCE_MAX_LENGTH = 300
# 링크는 http(s)로 시작해야 하고, 저장 형식(쉼표·대괄호 구분)을 깨는 문자와 공백은 쓸 수 없음
LINK_PATTERN = re.compile(r"^https?://[^\s,\[\]]+$")


class InsertAppealRequest(BaseModel):
    """이의신청 접수 요청입니다. 회원 아이디, 대상 제재 번호, 이의 사유 종류, 상세 내용, 증빙 링크를 보냅니다."""

    # Swagger Try it out 화면에 보이는 기본 예시 값
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "c_id_seq": "customer1_01",
                "cs_seq": 1,
                "a_type": "사실과 다름",
                "a_reason": "상대 선수와 언쟁이 있었던 건 맞지만 욕설은 하지 않았습니다.",
                "a_evidence": ["https://youtu.be/xK2"],
            }
        },
    )

    c_id_seq: str = Field(min_length=1, max_length=50, description="회원 아이디(customer PK, 예: customer1_01)")
    cs_seq: int = Field(ge=1, description="이의신청할 제재 번호(c_sanction.cs_seq)")
    # 화면의 "이의 사유" 칩: 사실과 다름 / 과도한 제재 / 신고자 오인
    a_type: str = Field(description="이의 사유 종류 (사실과 다름 / 과도한 제재 / 신고자 오인)")
    a_reason: str = Field(min_length=5, max_length=1000, description="상세 내용 (5자 이상)")
    # 증빙 공유 링크 (유튜브 일부 공개, 구글 드라이브 등). 앱에서 파일을 직접 올릴 수 없어서 링크로 받음
    a_evidence: List[str] = Field(default_factory=list, max_length=EVIDENCE_MAX_COUNT, description="증빙 공유 링크 (선택, 최대 3개)")

    @field_validator("c_id_seq", "a_type", "a_reason", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @field_validator("a_type")
    @classmethod
    def check_type(cls, value: str) -> str:
        if value not in APPEAL_TYPES:
            raise ValueError(f"a_type은 {', '.join(APPEAL_TYPES)} 중 하나여야 합니다.")
        return value

    @field_validator("a_reason")
    @classmethod
    def check_reason(cls, value: str) -> str:
        # 본문이 "[결과:인용]" 같은 태그로 시작하면 저장된 태그로 오인될 수 있어 막음
        if TAG_PATTERN.match(value):
            raise ValueError("상세 내용은 '[이름:값]' 형태로 시작할 수 없습니다.")
        return value

    @field_validator("a_evidence", mode="before")
    @classmethod
    def strip_links(cls, value: object) -> object:
        # 앞뒤 공백을 지우고 빈 문자열은 버림 (입력칸을 비워서 보낸 경우)
        if isinstance(value, list):
            return [v.strip() for v in value if isinstance(v, str) and v.strip()]
        return value

    @field_validator("a_evidence")
    @classmethod
    def check_links(cls, value: List[str]) -> List[str]:
        for link in value:
            if len(link) > EVIDENCE_MAX_LENGTH or not LINK_PATTERN.match(link):
                raise ValueError("증빙 링크는 공백·쉼표·대괄호가 없는 http(s):// 주소여야 합니다.")
        if len(set(value)) != len(value):
            raise ValueError("같은 증빙 링크를 중복해서 보낼 수 없습니다.")
        return value


# 이의신청 접수: 조건을 확인한 뒤 appeal에 한 줄 저장 (접수 상태로 시작 = h_id가 NULL)
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_400_BAD_REQUEST: {"description": "이의신청할 수 없는 제재 (종류/기한/소멸)"},
        status.HTTP_403_FORBIDDEN: {"description": "본인에게 부여된 제재가 아님"},
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 또는 제재"},
        status.HTTP_409_CONFLICT: {"description": "이미 이의신청한 제재"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "이의신청 등록 실패"},
    },
)
def insert_appeal(payload: InsertAppealRequest) -> dict:
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 회원 존재 여부 확인 (c_id_seq가 customer PK)
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (payload.c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 대상 제재 확인. FOR UPDATE로 이 제재 행을 잠가서, 같은 제재에 동시에 두 번 접수돼도 한 번만 저장되게 함
            cursor.execute(
                "SELECT c_id_seq, cs_date, cs_detail FROM c_sanction WHERE cs_seq = %s FOR UPDATE",
                (payload.cs_seq,),
            )
            sanction = cursor.fetchone()
            if sanction is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 제재입니다.")
            # database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄
            cs_date, cs_detail = sanction["cs_date"], sanction["cs_detail"]
            if sanction["c_id_seq"] != payload.c_id_seq:
                raise HTTPException(status_code=403, detail="본인에게 부여된 제재만 이의신청할 수 있습니다.")

            # 제재 종류/소멸/기한 확인 (제재 내역 화면의 can_appeal과 같은 기준)
            found = DETAIL_PATTERN.match(cs_detail or "")
            sanction_type = found.group(1).strip() if found else "기타"
            now = datetime.now()
            if sanction_type not in APPEALABLE_TYPES:
                raise HTTPException(status_code=400, detail="경고 또는 이용정지만 이의신청할 수 있습니다.")
            if sanction_type == "경고" and cs_date + timedelta(days=WARNING_EXPIRE_DAYS) <= now:
                raise HTTPException(status_code=400, detail="이미 소멸된 경고는 이의신청할 수 없습니다.")
            if now > cs_date + timedelta(days=APPEAL_DAYS):
                raise HTTPException(status_code=400, detail="이의신청 가능 기간(제재일부터 7일)이 지났습니다.")

            # 제재 1건당 1회: 이 회원의 이의신청 중 같은 제재 번호가 이미 있는지 확인
            cursor.execute("SELECT a_reason FROM appeal WHERE c_id_seq = %s", (payload.c_id_seq,))
            for old in cursor.fetchall():
                old_tags, _ = parse_appeal_reason(old["a_reason"])
                if old_tags.get("제재") == str(payload.cs_seq):
                    raise HTTPException(status_code=409, detail="이미 이의신청한 제재입니다.")

            # a_reason 만들기: "[제재:번호][사유:종류][증빙:링크들] 상세 내용" (증빙이 없으면 증빙 태그는 생략)
            tags = f"[제재:{payload.cs_seq}][사유:{payload.a_type}]"
            if payload.a_evidence:
                tags += f"[증빙:{','.join(payload.a_evidence)}]"

            # 이의신청 저장 (h_id는 NULL = 접수, a_evidence는 NOT NULL 컬럼이라 빈 문자열)
            cursor.execute(
                """
                INSERT INTO appeal (c_id_seq, a_date, a_reason, a_evidence)
                VALUES (%s, NOW(), %s, '')
                """,
                (payload.c_id_seq, f"{tags} {payload.a_reason}"),
            )
            a_seq = cursor.lastrowid

        connection.commit()
        return {"result": "OK", "a_seq": a_seq}
    except HTTPException:
        raise  # 위에서 만든 400/403/404/409는 500으로 바뀌지 않게 그대로 전달
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("이의신청 등록 실패")
        raise HTTPException(status_code=500, detail="이의신청 등록에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-27
