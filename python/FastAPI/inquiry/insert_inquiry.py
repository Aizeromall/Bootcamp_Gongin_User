# 작업자 : 김병재
# 최초 작업 일 : 2026-10-23

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)


class InsertInquiryRequest(BaseModel):
    """문의 작성 요청입니다. 회원 아이디(PK)와 문의 내용을 보냅니다."""

    # Swagger Try it out 화면에 보이는 기본 예시 값
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "example": {
                "c_id_seq": "customer1_01",
                "i_option": 1,
                "post": "문의 내용을 입력해주세요.",
            }
        },
    )

    c_id_seq: str = Field(min_length=1, max_length=50, description="회원 아이디(customer PK, 예: customer1_01)")
    # i_option: 1 = 매니저 신고 문의 / 2 = 구장 예약 문의 / 3 = 환불 문의 / 4 = 기타 문의
    # 생략하면 문의 내용 앞부분이 제목으로 표시됨
    i_option: Optional[int] = Field(default=None, ge=1, le=4, description="문의 옵션 (제목으로 사용, 선택)")
    post: str = Field(min_length=1, max_length=5000, description="문의 내용")

    @field_validator("c_id_seq", "post", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


# 문의 작성: 회원 아이디(c_id_seq)와 문의 내용을 받아 원글(level 0)로 등록
# i_state '0'(답변 대기)으로 시작
@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 아이디"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "문의 등록 실패"},
    },
)
def insert_inquiry(payload: InsertInquiryRequest) -> dict:
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 회원 존재 여부 확인 (c_id_seq가 customer PK)
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (payload.c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 문의 저장 (i_option을 생략하면 NULL)
            cursor.execute(
                """
                INSERT INTO inquiry (c_id_seq, post, i_date, i_state, level, i_option)
                VALUES (%s, %s, NOW(), '0', 0, %s)
                """,
                (
                    payload.c_id_seq,
                    payload.post,
                    None if payload.i_option is None else str(payload.i_option),
                ),
            )
            i_seq = cursor.lastrowid

        connection.commit()
        return {"result": "OK", "i_seq": i_seq}
    except HTTPException:
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("문의 등록 실패")
        raise HTTPException(status_code=500, detail="문의 등록에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()
