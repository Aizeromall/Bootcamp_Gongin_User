# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""공급자 검증 이후의 MySQL 회원 조회·가입. 공급자 ID와 이메일 원문은 저장하지 않습니다."""

import base64
import hashlib
from contextlib import contextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pymysql
from fastapi import APIRouter, Body, HTTPException, Response
from pydantic import ValidationError

from ..database import connect
from .register import RegisterRequest
from .social_flow import put_flow, take_flow, FLOW_SECONDS
from .social_http import SOCIAL_ERRORS
from .token import signing_key
from .account_lifecycle import authentication_result

router = APIRouter()
PASSWORD_UNSUPPORTED = "간편로그인_비밀번호미지원"


def social_base(provider: str, subject: str) -> str:
    if provider not in ("google", "kakao", "naver") or not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=401, detail="공급자 회원 ID를 확인할 수 없습니다.")
    # 전체 SHA-256 32바이트 → 패딩 없는 URL-safe Base64 43자. 절단하지 않습니다.
    # 접두어 2 + 해시 43 + 종목 suffix 3 = 48자로 기존 PK/FK 길이를 유지합니다.
    digest = hashlib.sha256((provider + ":" + subject).encode("utf-8")).digest()
    return {"google": "g_", "kakao": "k_", "naver": "n_"}[provider] + base64.urlsafe_b64encode(digest).decode().rstrip("=")


@contextmanager
def account_connection():
    connection = None
    try:
        connection = connect()
        yield connection
        connection.commit()
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=409, detail="이미 가입되었거나 회원 정보가 충돌합니다.") from None
    except Exception:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=500, detail="간편로그인 회원 DB 처리에 실패했습니다.") from None
    finally:
        if connection is not None:
            connection.close()


def select_members(cursor, base: str, provider: str, lock: bool = False) -> list:
    expected = [f"{base}_{sport:02d}" for sport in range(1, 5)]
    cursor.execute(
        """SELECT c_id_seq, c_login_type, c_name, c_prefer_stock, c_deletdate
           FROM customer WHERE c_id_seq IN (%s, %s, %s, %s) ORDER BY c_id_seq"""
        + (" FOR UPDATE" if lock else ""), tuple(expected),
    )
    rows = list(cursor.fetchall())
    # DB의 대소문자 무시 collation으로 유사 해시가 조회돼도 다른 계정에 로그인하지 않습니다.
    if any(row["c_id_seq"] not in expected or row["c_login_type"] != provider for row in rows):
        raise HTTPException(status_code=409, detail="회원 식별자가 충돌합니다. 운영자에게 문의해 주세요.")
    return rows


def login_response(base: str, provider: str, rows: list) -> dict:
    # 수정 일 : 2026-10-29 / 작업자 : 최현준
    # 모든 간편로그인 공급자에 같은 종목별 30일 유예·복구 정책을 적용합니다.
    return authentication_result(base, provider, rows)


def finish_identity(provider: str, subject: str) -> dict:
    signing_key()  # 설정 오류가 있으면 가입 대기 티켓이나 DB 변경 전에 차단합니다.
    base = social_base(provider, subject)
    with account_connection() as connection:
        with connection.cursor() as cursor:
            rows = select_members(cursor, base, provider)
    if rows:
        return login_response(base, provider, rows)
    ticket = put_flow("signup", {"base": base, "provider": provider})
    return {"result": "SIGNUP_REQUIRED", "signup_required": True,
            "signup_ticket": ticket, "expires_in": FLOW_SECONDS,
            "c_login_type": provider, "next_endpoint": "/auth/social/register"}


@router.post("/social/register", status_code=201, responses=SOCIAL_ERRORS,
             summary="간편가입 추가 정보 입력 및 종목별 회원 생성")
def register_social(
    response: Response,
    signup_ticket: str = Body(min_length=1, max_length=256, description="공급자 인증 후 받은 일회용 티켓"),
    c_name: str = Body(min_length=1, max_length=45),
    c_address: str = Body(min_length=1, max_length=255),
    c_phone: str = Body(min_length=1, max_length=20),
    c_gender: str = Body(min_length=1, max_length=10),
    c_birthday: str = Body(description="YYYY-MM-DD"),
    preferred_stocks: list[int] = Body(min_length=1, max_length=4),
    c_position: dict[int, str] = Body(description="종목별 포지션. 예: {\"1\": \"FW\"}"),
) -> dict:
    # 새 요청 클래스를 만들지 않고 기존 회원가입 모델의 공백·날짜·종목·포지션 검증을 재사용합니다.
    try:
        profile = RegisterRequest(c_id="social_validation", c_pw="not-a-user-password",
                                  c_name=c_name, c_address=c_address, c_phone=c_phone,
                                  c_gender=c_gender, c_birthday=c_birthday, c_team="무소속",
                                  preferred_stocks=preferred_stocks, c_position=c_position)
    except ValidationError as error:
        details = [{"loc": ["body", *item["loc"]], "msg": item["msg"], "type": item["type"]}
                   for item in error.errors(include_input=False, include_url=False)]
        raise HTTPException(status_code=422, detail=details) from None
    if profile.c_birthday > datetime.now(ZoneInfo("Asia/Seoul")).date():
        raise HTTPException(status_code=422, detail="생년월일은 미래 날짜일 수 없습니다.")
    signing_key()
    identity = take_flow(signup_ticket, "signup")
    base, provider = identity["base"], identity["provider"]
    # 어떤 오류가 발생해도 티켓은 재사용하지 않습니다. 인증을 다시 시작해야 합니다.
    with account_connection() as connection:
        with connection.cursor() as cursor:
            if select_members(cursor, base, provider, lock=True):
                raise HTTPException(status_code=409, detail="이미 가입한 회원입니다. 다시 간편로그인해 주세요.")
            signup_date = datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)
            rows = [(f"{base}_{sport:02d}", provider, sport, PASSWORD_UNSUPPORTED, profile.c_name,
                     profile.c_address, profile.c_phone, profile.c_gender, profile.c_birthday,
                     "무소속", profile.c_position[sport], signup_date, 1500)
                    for sport in profile.preferred_stocks]
            cursor.executemany(
                """INSERT INTO customer
                   (c_id_seq, c_login_type, c_prefer_stock, c_pw, c_name, c_address, c_phone,
                    c_gender, c_birthday, c_team, c_position, c_signupdate, c_rating)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""", rows,
            )
            # 가입·JWT 발급이 모두 성공해야 commit합니다. 팀 가입 전 c_category는 설정하지 않습니다.
            result = login_response(base, provider, [
                {"c_id_seq": row[0], "c_name": profile.c_name, "c_prefer_stock": row[2], "c_deletdate": None}
                for row in rows])
    response.headers["Cache-Control"] = "no-store"
    return result

# 최종 수정 일 : 2026-10-28
# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준 (종목별 유예 및 복구 전용 로그인)
