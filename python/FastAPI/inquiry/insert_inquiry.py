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

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    # 디버그: 부모 문의 ID만 받고 깊이는 서버에서 계산하여 임의 깊이 입력을 막습니다.
    i_comment_seq: Optional[int] = Field(default=None, gt=0, description="답변 대상 문의의 i_seq")

    @field_validator("c_id_seq", "post", mode="before")
    @classmethod
    def strip_text(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


# 신규 문의는 level=0, 재답변은 부모의 level+1로 별도 행에 보존합니다.
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

            # 수정 일 : 2026-10-26 / 작업자 : 양태건
            # 원글/기존 답변을 덮어쓰지 않고 같은 소유자의 부모 행에 연결합니다.
            level = 0
            option = None if payload.i_option is None else str(payload.i_option)
            if payload.i_comment_seq is not None:
                cursor.execute(
                    """SELECT i_seq, c_id_seq, level, i_option FROM inquiry
                       WHERE i_seq = %s FOR UPDATE""",
                    (payload.i_comment_seq,),
                )
                parent = cursor.fetchone()
                if parent is None:
                    raise HTTPException(status_code=404, detail="답변할 문의가 존재하지 않습니다.")
                if parent["c_id_seq"] != payload.c_id_seq:
                    raise HTTPException(status_code=403, detail="본인 문의에만 답변할 수 있습니다.")
                if not 0 <= parent["level"] < 2147483647:
                    raise HTTPException(status_code=409, detail="문의 깊이 정보를 확인해 주세요.")
                level = parent["level"] + 1
                option = parent["i_option"]
            cursor.execute(
                """INSERT INTO inquiry
                   (c_id_seq, post, i_date, i_state, level, i_option, i_comment_seq)
                   VALUES (%s, %s, NOW(), '0', %s, %s, %s)""",
                (payload.c_id_seq, payload.post, level, option, payload.i_comment_seq),
            )
            i_seq = cursor.lastrowid

        connection.commit()
        return {"result": "OK", "i_seq": i_seq, "level": level,
                "i_comment_seq": payload.i_comment_seq}
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("문의 등록 실패")
        raise HTTPException(status_code=500, detail="문의 등록에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
