# 작업자 : 최현준
# 최초 작업 일 : 2026-10-22

import base64
import hashlib
import logging
import secrets
from datetime import date

import pymysql
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)
PASSWORD_ITERATIONS = 600_000
SPORT_NAMES = {1: "축구", 2: "농구", 3: "야구", 4: "배구"}
POSITION_OPTIONS = {
    1: {"FW", "MF", "DF", "GK"},
    2: {"센터", "가드", "포워드"},
    3: {"투수", "포수", "내야수", "외야수"},
    4: {"세터", "리베로", "센터", "레프트", "라이트"},
}


class RegisterRequest(BaseModel):
    """회원가입에 필요한 값입니다. 필수 입력값은 공백을 허용하지 않습니다."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    c_id: str = Field(min_length=1, max_length=40, description="seq를 제외한 회원 아이디")
    c_pw: SecretStr = Field(min_length=8, max_length=128)
    c_name: str = Field(min_length=1, max_length=45)
    c_address: str = Field(min_length=1, max_length=255)
    # ************************
    # 버그 확인 일 : 2026-10-28 / 작업자 : 최현준
    # 1. 버그 발생 위치 : RegisterRequest의 전화번호·성별·팀명 길이 검증
    # 2. 버그 내용 : 요청 제한 30/20/100자가 DB VARCHAR(20)/(10)/(50)을 초과
    # 3. 디버깅 내용 : 실제 DB 길이 20/10/50자로 요청 최대 길이를 일치
    # 4. 테스트 사항 : 각 필드 최대 길이 허용·1자 초과 422·DB 연결 전 차단 검증
    # 5. 결과 및 추후 보완 사항 : DB 구조·데이터는 변경하지 않음, schema 변경 시 검증도 함께 확인
    # ************************
    c_phone: str = Field(min_length=1, max_length=20)
    c_gender: str = Field(min_length=1, max_length=10)
    c_birthday: date
    c_team: str = Field(min_length=1, max_length=50)
    # 디버그: 요청은 종목번호별 포지션으로 받고 DB 각 행에는 해당 값만 저장합니다.
    # 작업자 : 양태건 / 최종 수정일 : 2026-10-26
    c_position: dict[int, str] = Field(min_length=1, max_length=4)
    preferred_stocks: list[int] = Field(min_length=1, max_length=4)

    @field_validator("c_id", "c_name", "c_address", "c_phone", "c_gender", "c_team", mode="before")
    @classmethod
    def reject_blank_text(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        value = value.strip()
        if not value:
            raise ValueError("빈 값은 입력할 수 없습니다.")
        return value

    @field_validator("preferred_stocks")
    @classmethod
    def validate_preferred_stocks(cls, values: list[int]) -> list[int]:
        if len(values) != len(set(values)) or any(value not in SPORT_NAMES for value in values):
            raise ValueError("선호 종목은 축구(1), 농구(2), 야구(3), 배구(4) 중 중복 없이 선택해야 합니다.")
        return sorted(values)

    @model_validator(mode="after")
    def validate_positions(self) -> "RegisterRequest":
        if set(self.c_position) != set(self.preferred_stocks):
            raise ValueError("선택한 각 종목의 포지션을 하나씩 입력해야 합니다.")
        for sport, position in self.c_position.items():
            if position not in POSITION_OPTIONS[sport]:
                raise ValueError(f"{SPORT_NAMES[sport]}에 맞는 포지션을 선택해야 합니다.")
        return self


def hash_password(plain_password: str) -> str:
    """외부 의존성 없이 c_pw에 저장할 PBKDF2-SHA256 해시를 만듭니다."""

    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", plain_password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return "pbkdf2_sha256${}${}${}".format(
        PASSWORD_ITERATIONS,
        base64.urlsafe_b64encode(salt).decode("ascii"),
        base64.urlsafe_b64encode(digest).decode("ascii"),
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    responses={
        status.HTTP_409_CONFLICT: {"description": "중복 아이디 또는 DB 제약 조건 위반"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "필수값 또는 선호 종목 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "DB 연결 또는 회원가입 처리 실패"},
    },
)
def register_customer(payload: RegisterRequest) -> dict:
    """선택한 종목마다 customer 레코드 하나를 원자적으로 생성합니다."""

    # 소셜 회원용 PK 영역은 일반 가입자가 선점할 수 없습니다. 대소문자 무시 DB도 고려합니다.
    if payload.c_id.lower().startswith(("g_", "k_", "n_", "google_", "kakao_", "naver_")):
        raise HTTPException(status_code=422, detail="간편로그인용으로 예약된 아이디 접두어는 사용할 수 없습니다.")
    connection = None
    try:
        connection = connect()
        password_hash = hash_password(payload.c_pw.get_secret_value())
        # c_id_seq는 c_id_01 형식이므로 같은 c_id의 가입 여부를 먼저 확인합니다.
        escaped_id = payload.c_id.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM customer WHERE c_id_seq LIKE %s ESCAPE '!' LIMIT 1",
                (f"{escaped_id}!_%",),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="이미 사용 중인 아이디입니다.")

            # 가입일은 가입 요청이 처리되는 오늘 날짜로 넣습니다.
            signup_date = date.today()
            rows = [
                (
                    f"{payload.c_id}_{sport:02d}",
                    sport,
                    password_hash,
                    payload.c_name,
                    payload.c_address,
                    payload.c_phone,
                    payload.c_gender,
                    payload.c_birthday,
                    payload.c_team,
                    payload.c_position[sport],
                    signup_date,
                )
                # c_id_seq의 끝 번호는 종목 코드와 같아야 예약 종목을 판별할 수 있습니다.
                for sport in payload.preferred_stocks
            ]
            cursor.executemany(
                """
                INSERT INTO customer (
                    c_id_seq, c_prefer_stock, c_pw, c_name, c_address, c_phone,
                    c_gender, c_birthday, c_team, c_position, c_signupdate
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                rows,
            )
        connection.commit()
        return {
            "result": "OK",
            "c_id": payload.c_id,
            "created_customer_ids": [row[0] for row in rows],
            "preferred_stocks": [SPORT_NAMES[sport] for sport in payload.preferred_stocks],
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.err.IntegrityError:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=409, detail="중복되었거나 유효하지 않은 회원 정보입니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("회원가입 처리 실패")
        raise HTTPException(status_code=500, detail="회원가입 처리에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (간편로그인 ID 영역 보호)
# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (회원가입 입력 길이 DB 기준 적용)
