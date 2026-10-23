# 작업자 : 최현준
# 최초 작업 일 : 2026-10-22

import base64
import hashlib
import hmac
import logging

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)


class LoginRequest(BaseModel):
    """클라이언트가 보내는 로그인 정보입니다."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    c_id: str = Field(min_length=1, max_length=45, description="seq를 제외한 회원 아이디")
    c_pw: SecretStr = Field(min_length=8, max_length=128)

    @field_validator("c_id", mode="before")
    @classmethod
    def strip_id(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value


def verify_password(plain_password: str, stored_password: str) -> bool:
    """PBKDF2 해시를 검증합니다. 평문 비밀번호는 지원하지 않습니다."""

    try:
        algorithm, iterations, encoded_salt, encoded_digest = stored_password.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(encoded_salt.encode("ascii"))
        expected = base64.urlsafe_b64decode(encoded_digest.encode("ascii"))
        actual = hashlib.pbkdf2_hmac(
            "sha256", plain_password.encode("utf-8"), salt, int(iterations)
        )
        return hmac.compare_digest(actual, expected)
    except (AttributeError, ValueError, TypeError, UnicodeError):
        # 잘못된 저장값도 일반 로그인 실패처럼 처리해 계정 정보를 노출하지 않습니다.
        return False


@router.post(
    "/login",
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_401_UNAUTHORIZED: {"description": "아이디 또는 비밀번호 불일치"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "DB 연결 또는 로그인 처리 실패"},
    },
)
def login_customer(payload: LoginRequest) -> dict:
    """아이디의 첫 customer 레코드로 비밀번호를 확인하고 선호 종목을 반환합니다."""

    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # _는 LIKE에서 와일드카드이므로 ESCAPE 문자를 사용해 문자 그대로 비교합니다.
            escaped_id = payload.c_id.replace("!", "!!").replace("%", "!%").replace("_", "!_")
            cursor.execute(
                """
                SELECT c_id_seq, c_pw, c_name, c_prefer_stock
                FROM customer
                WHERE c_id_seq LIKE %s ESCAPE '!'
                ORDER BY c_id_seq
                """,
                (f"{escaped_id}!_%",),
            )
            customers = cursor.fetchall()

        if not customers or not verify_password(
            payload.c_pw.get_secret_value(), customers[0]["c_pw"]
        ):
            # 존재하지 않는 아이디와 비밀번호 오류를 같은 응답으로 처리합니다.
            raise HTTPException(status_code=401, detail="아이디 또는 비밀번호가 올바르지 않습니다.")

        return {
            "result": "OK",
            "c_id": payload.c_id,
            "c_name": customers[0]["c_name"],
            "preferred_stocks": [row["c_prefer_stock"] for row in customers],
        }
    except HTTPException:
        raise
    except Exception:
        logger.exception("로그인 처리 실패")
        raise HTTPException(status_code=500, detail="로그인 처리에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-23
