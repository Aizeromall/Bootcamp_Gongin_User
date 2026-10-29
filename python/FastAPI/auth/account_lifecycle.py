# 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
"""종목별 30일 유예·로그인 응답·복구 전용 인증. 실제 DB 구조는 변경하지 않습니다."""
import hashlib
from contextlib import contextmanager
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import jwt
import pymysql
from fastapi import HTTPException

from ..database import connect
from .token import ISSUER, issue_token, signing_key

RECOVERY_AUDIENCE = "gongin-account-recovery"
RECOVERY_SECONDS = 600
GRACE = timedelta(days=30)
ERRORS = {
    401: {"description": "서비스/복구 토큰 누락·위조·만료 또는 잘못된 용도"},
    403: {"description": "본인 계정이 아님·활성 종목 없음·복구 기간 경과"},
    404: {"description": "회원 또는 해당 종목 없음"},
    409: {"description": "중복 종목·상태 충돌·기존 FK 이력으로 재가입/삭제 불가"},
    422: {"description": "허용되지 않은 필드·입력 길이·종목·포지션 오류"},
    500: {"description": "회원 DB 처리 실패"},
    503: {"description": "서버 JWT 서명키 설정 필요"},
}
FIELDS = """c_id_seq,c_login_type,c_pw,c_name,c_address,c_phone,c_gender,c_birthday,
            c_signupdate,c_deletdate,c_prefer_stock,c_category,c_team,c_position,c_rating"""


def now_kst() -> datetime:
    return datetime.now(ZoneInfo("Asia/Seoul")).replace(tzinfo=None)


def deletion_time(row: dict) -> datetime | None:
    value = row.get("c_deletdate")
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(ZoneInfo("Asia/Seoul")).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, date):
        return datetime.combine(value, time.min)
    return datetime.fromisoformat(str(value))


def sport_state(row: dict, at: datetime) -> str:
    deleted = deletion_time(row)
    return "active" if deleted is None else "recoverable" if at < deleted + GRACE else "expired"


def summary(rows: list[dict], at: datetime | None = None) -> dict:
    at = at or now_kst()
    all_deleted = bool(rows) and all(deletion_time(row) is not None for row in rows)
    return {
        "sports": [{"c_id_seq": row["c_id_seq"], "sport": int(row["c_prefer_stock"]),
                    "state": sport_state(row, at), "selected_at": row.get("c_signupdate"),
                    "withdrawn_at": deletion_time(row),
                    "recovery_deadline": deletion_time(row) + GRACE if deletion_time(row) else None}
                   for row in rows],
        # 한 종목이라도 활성화되어 있으면 계정 전체 삭제 대상이 아닙니다.
        "account_deletion_due_at": max(deletion_time(row) for row in rows) + GRACE if all_deleted else None,
    }


@contextmanager
def account_db(write: bool = False):
    connection = None
    try:
        connection = connect()
        yield connection
        if write:
            connection.commit()
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=409, detail="회원 정보 또는 연결된 이력과 충돌합니다.") from None
    except Exception:
        if connection is not None:
            connection.rollback()
        raise HTTPException(status_code=500, detail="회원 정보를 처리하지 못했습니다.") from None
    finally:
        if connection is not None:
            connection.close()


def load_members(cursor, base: str, lock: bool = False) -> list[dict]:
    expected = [f"{base}_{sport:02d}" for sport in range(1, 5)]
    # LIKE나 split('_')[0]을 쓰지 않아 underscore/소셜 해시 계정 경계를 유지합니다.
    cursor.execute(f"SELECT {FIELDS} FROM customer WHERE c_id_seq IN (%s,%s,%s,%s) ORDER BY c_id_seq"
                   + (" FOR UPDATE" if lock else ""), tuple(expected))
    rows = list(cursor.fetchall())
    if any(row["c_id_seq"] not in expected for row in rows):
        raise HTTPException(status_code=409, detail="회원 식별자가 충돌합니다.")
    if len({row["c_login_type"] for row in rows}) > 1:
        raise HTTPException(status_code=409, detail="계정 로그인 방식이 일치하지 않습니다.")
    return rows


def owned_active(rows: list[dict], account: dict) -> None:
    if not rows:
        raise HTTPException(status_code=404, detail="회원 정보가 없습니다.")
    if not any(row["c_id_seq"] in account["member_ids"] and row.get("c_deletdate") is None for row in rows):
        raise HTTPException(status_code=403, detail="활성 종목으로 다시 로그인하거나 계정을 복구해 주세요.")


def fingerprint(rows: list[dict]) -> str:
    # 복구 후 재삭제, 비밀번호 변경, 다른 종목 변경 시 이전 복구 토큰을 재사용하지 않습니다.
    value = repr(sorted((r["c_id_seq"], str(r.get("c_pw", "")), str(r.get("c_deletdate"))) for r in rows))
    return hashlib.sha256(value.encode()).hexdigest()


def authentication_result(base: str, provider: str, rows: list[dict]) -> dict:
    at = now_kst()
    active = [row for row in rows if row.get("c_deletdate") is None]
    if active:
        return {"result": "OK", "signup_required": False, "recovery_required": False,
                "c_id": base, "c_login_type": provider, "c_name": active[0]["c_name"],
                "c_id_seq": active[0]["c_id_seq"], "member_ids": [r["c_id_seq"] for r in active],
                "preferred_stocks": [int(r["c_prefer_stock"]) for r in active],
                **issue_token(base, [r["c_id_seq"] for r in active])}
    if not any(sport_state(row, at) == "recoverable" for row in rows):
        raise HTTPException(status_code=403, detail="복구 가능한 종목이 없습니다. 삭제 대기 이력은 복구할 수 없습니다.")
    issued = datetime.now(ZoneInfo("UTC"))
    recovery = jwt.encode({"sub": base, "provider": provider, "snapshot": fingerprint(rows),
                           "aud": RECOVERY_AUDIENCE, "iss": ISSUER, "iat": issued,
                           "exp": issued + timedelta(seconds=RECOVERY_SECONDS)}, signing_key(), algorithm="HS256")
    # 정상 access_token을 주지 않습니다. 프론트는 복구 확인 화면 외에 진입시키면 안 됩니다.
    return {"result": "RECOVERY_REQUIRED", "signup_required": False, "recovery_required": True,
            "recovery_token": recovery, "expires_in": RECOVERY_SECONDS,
            "next_endpoint": "/auth/account/recovery", **summary(rows, at)}


def decode_recovery(encoded: str) -> dict:
    key = signing_key()
    try:
        claims = jwt.decode(encoded, key, algorithms=["HS256"], audience=RECOVERY_AUDIENCE, issuer=ISSUER,
                            options={"require": ["sub", "provider", "snapshot", "iat", "exp", "aud", "iss"]})
        if (not isinstance(claims["sub"], str) or not 1 <= len(claims["sub"]) <= 45
                or claims["provider"] not in ("local", "google", "kakao", "naver")
                or not isinstance(claims["snapshot"], str) or len(claims["snapshot"]) != 64):
            raise ValueError("invalid recovery claims")
        return claims
    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise HTTPException(status_code=401, detail="복구 인증이 만료되었거나 올바르지 않습니다. 다시 로그인해 주세요.") from None

# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
