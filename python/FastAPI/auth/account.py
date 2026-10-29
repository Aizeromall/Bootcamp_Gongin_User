# 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
"""내 정보·종목별 삭제 신청·복구 router. 클래스와 실제 DB 마이그레이션은 추가하지 않습니다."""
from datetime import date
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Path
from fastapi.security import HTTPAuthorizationCredentials

from .account_lifecycle import (ERRORS, account_db, authentication_result, decode_recovery,
                                fingerprint, load_members, now_kst, owned_active, sport_state, summary)
from .login import verify_password
from .register import POSITION_OPTIONS, hash_password
from .token import current_account, security, signing_key

router = APIRouter(prefix="/account", tags=["Auth Account"])


def public_profile(rows: list[dict]) -> dict:
    # 비밀번호 해시를 포함한 SELECT 결과를 그대로 반환하지 않습니다.
    fields = ("c_id_seq", "c_login_type", "c_name", "c_address", "c_phone", "c_gender", "c_birthday",
              "c_prefer_stock", "c_position", "c_team", "c_category", "c_rating", "c_signupdate", "c_deletdate")
    return {"members": [{key: row.get(key) for key in fields} for row in rows], **summary(rows)}


def fresh_result(account: dict, rows: list[dict]) -> dict:
    return authentication_result(account["sub"], rows[0]["c_login_type"], rows)


@router.get("", responses=ERRORS, summary="내 프로필 및 종목별 삭제·복구 상태")
def get_account(account: dict = Depends(current_account)) -> dict:
    with account_db() as connection, connection.cursor() as cursor:
        rows = load_members(cursor, account["sub"])
        owned_active(rows, account)
        return public_profile(rows)


@router.patch("/profile", responses=ERRORS, summary="내 공통 개인정보·일반 비밀번호·종목별 포지션 수정")
# ************************
# 버그 확인 일 : 2026-10-29 / 작업자 : 최현준
# 1. 버그 발생 위치 : 회원정보 수정 API의 선호 종목 저장 계약
# 2. 버그 내용 : 개별 종목 API만 있고 회원정보 화면에서 최종 선택 목록을 일괄 저장할 수 없었음
# 3. 디버깅 내용 : 선택 유지/해제/복구/신규 생성을 동일 회원 잠금·트랜잭션 안에서 처리
# 4. 테스트 사항 : 추가+해제+복구 동시 저장, 전체 해제, 30일 만료, INSERT 실패 롤백
# 5. 결과 및 추후 보완 사항 : 기존 신청일·선택일 보존, 신규만 선택일/1500 부여, FK 만료 행 덮어쓰기 금지
# ************************
def update_profile(
    changes: dict = Body(description="허용: c_name(50), c_address(255), c_phone(20), c_gender(10), "
                        "c_birthday(YYYY-MM-DD), c_position(종목번호별 객체). 일반 비밀번호는 c_pw와 current_password 동시 입력. "
                        "preferred_stocks: 최종 선택 종목번호 목록(빈 목록은 전체 삭제 신청). "
                        "종목 변경 시 c_position은 선택 종목 전체의 포지션 객체. ID·팀·등급·로그인 방식·날짜 직접 수정 불가.",
                         examples=[{"preferred_stocks": [1, 4], "c_position": {"1": "FW", "4": "세터"}}]),
    account: dict = Depends(current_account),
) -> dict:
    allowed = {"c_name": 50, "c_address": 255, "c_phone": 20, "c_gender": 10}
    if not changes or set(changes) - (set(allowed) | {"c_birthday", "c_position", "c_pw", "current_password", "preferred_stocks"}):
        raise HTTPException(status_code=422, detail="허용된 수정 항목만 입력해 주세요.")
    values = {}
    for key, limit in allowed.items():
        if key in changes:
            text = changes[key]
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= limit:
                raise HTTPException(status_code=422, detail=f"{key}는 공백을 제외해 1~{limit}자로 입력해 주세요.")
            values[key] = text.strip()
    if "c_birthday" in changes:
        try:
            birthday = date.fromisoformat(changes["c_birthday"])
            if birthday > now_kst().date():
                raise ValueError("future birthday")
            values["c_birthday"] = birthday
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="생년월일은 오늘 이전의 YYYY-MM-DD로 입력해 주세요.") from None
    positions = changes.get("c_position", {})
    stocks = changes.get("preferred_stocks")
    if "preferred_stocks" in changes and (not isinstance(stocks, list) or len(stocks) > 4
            or any(type(s) is not int or s not in POSITION_OPTIONS for s in stocks)
            or len(stocks) != len(set(stocks))):
        raise HTTPException(status_code=422, detail="선호 종목은 1~4 중 중복 없이 선택해 주세요.")
    if (not isinstance(positions, dict) or ("c_position" in changes and not positions and stocks != [])
            or any(str(s) not in {"1", "2", "3", "4"} or not isinstance(p, str)
                   or p not in POSITION_OPTIONS[int(s)] for s, p in positions.items())):
        raise HTTPException(status_code=422, detail="종목별 허용 포지션을 입력해 주세요.")
    if stocks is not None and {int(s) for s in positions} != set(stocks):
        raise HTTPException(status_code=422, detail="선택한 모든 종목의 포지션을 하나씩 입력해 주세요.")
    if ("c_pw" in changes) != ("current_password" in changes):
        raise HTTPException(status_code=422, detail="현재 비밀번호와 새 비밀번호를 함께 입력해 주세요.")
    if "c_pw" in changes and any(not isinstance(changes[k], str) or not 8 <= len(changes[k]) <= 128
                                for k in ("c_pw", "current_password")):
        raise HTTPException(status_code=422, detail="비밀번호는 8~128자로 입력해 주세요.")
    signing_key()
    with account_db(write=True) as connection, connection.cursor() as cursor:
        rows = load_members(cursor, account["sub"], lock=True)
        owned_active(rows, account)
        if stocks is None and any(not any(r["c_prefer_stock"] in (s, int(s)) and r["c_deletdate"] is None for r in rows)
               for s in positions):
            raise HTTPException(status_code=409, detail="활성화된 가입 종목의 포지션만 변경할 수 있습니다.")
        at = now_kst().replace(microsecond=0)
        if stocks is not None and any(int(r["c_prefer_stock"]) in stocks and sport_state(r, at) == "expired" for r in rows):
            raise HTTPException(status_code=409, detail="복구 기간이 지난 종목은 기존 이력 정리 후 다시 선택할 수 있습니다.")
        source = next(r for r in rows if r["c_deletdate"] is None)
        if "c_pw" in changes:
            if rows[0]["c_login_type"] != "local":
                raise HTTPException(status_code=422, detail="간편가입자는 서비스 비밀번호를 설정할 수 없습니다.")
            if not verify_password(changes["current_password"], rows[0]["c_pw"]):
                raise HTTPException(status_code=401, detail="현재 비밀번호가 올바르지 않습니다.")
            values["c_pw"] = hash_password(changes["c_pw"])
        for row in rows:
            updates = dict(values)
            if stocks is not None:
                chosen = int(row["c_prefer_stock"]) in stocks
                if chosen and row["c_deletdate"] is not None:
                    updates["c_deletdate"] = None
                elif not chosen and row["c_deletdate"] is None:
                    updates["c_deletdate"] = at
            position = positions.get(str(row["c_prefer_stock"]), positions.get(int(row["c_prefer_stock"])))
            if position is not None:
                updates["c_position"] = position
            updates = {key: value for key, value in updates.items() if row.get(key) != value}
            if updates:
                # 컬럼명은 위 고정 허용 목록에서만 생성하고 모든 값은 바인딩합니다.
                cursor.execute("UPDATE customer SET " + ",".join(f"{key}=%s" for key in updates)
                               + " WHERE c_id_seq=%s", (*updates.values(), row["c_id_seq"]))
                row.update(updates)
        if stocks is not None:
            existing = {int(r["c_prefer_stock"]) for r in rows}
            for sport in sorted(set(stocks) - existing):
                rows.append(insert_sport(cursor, account["sub"], sport, positions.get(str(sport), positions.get(sport)), source, at))
            rows.sort(key=lambda r: r["c_id_seq"])
        return {"result": "OK", **public_profile(rows), "session": fresh_result(account, rows)}


def insert_sport(cursor, base, sport, position, source, at):
    """프로필 일괄 저장·개별 추가에서 같은 PK/초기값 정책을 재사용합니다."""
    columns = ("c_id_seq", "c_login_type", "c_pw", "c_name", "c_address", "c_phone", "c_gender",
               "c_birthday", "c_signupdate", "c_deletdate", "c_prefer_stock", "c_team", "c_position", "c_rating")
    row = {key: source.get(key) for key in columns}
    row.update(c_id_seq=f"{base}_{sport:02d}", c_signupdate=at, c_deletdate=None, c_prefer_stock=str(sport),
               c_team="무소속", c_position=position, c_rating=1500)
    if any(row[k] is None for k in columns if k != "c_deletdate"):
        raise HTTPException(status_code=409, detail="기존 회원의 필수 개인정보를 먼저 확인해 주세요.")
    cursor.execute("INSERT INTO customer (" + ",".join(columns) + ") VALUES ("
                   + ",".join(["%s"] * len(columns)) + ")", tuple(row[k] for k in columns))
    return row


@router.post("/sports", status_code=201, responses=ERRORS, summary="기존 계정에 고정 suffix 종목 추가")
def add_sport(sport: Literal[1, 2, 3, 4] = Body(), c_position: str = Body(min_length=1, max_length=50),
              account: dict = Depends(current_account)) -> dict:
    if c_position not in POSITION_OPTIONS[sport]:
        raise HTTPException(status_code=422, detail="해당 종목의 허용 포지션을 선택해 주세요.")
    signing_key()
    with account_db(write=True) as connection, connection.cursor() as cursor:
        rows = load_members(cursor, account["sub"], lock=True)
        owned_active(rows, account)
        member = f"{account['sub']}_{sport:02d}"
        existing = next((r for r in rows if r["c_id_seq"] == member), None)
        if existing:
            state = sport_state(existing, now_kst())
            raise HTTPException(status_code=409, detail={"code": "SPORT_" + state.upper(),
                                "message": "활성 종목은 중복 추가할 수 없고, 유예 종목은 복구 API를 사용합니다. "
                                           "기간이 지난 종목은 기존 FK 이력 정리 후 재가입할 수 있습니다."})
        source = next(r for r in rows if r["c_deletdate"] is None)
        row = insert_sport(cursor, account["sub"], sport, c_position, source, now_kst())
        rows.append(row)
        rows.sort(key=lambda r: r["c_id_seq"])
        return {"result": "OK", "created_customer_id": member, "session": fresh_result(account, rows)}


def withdraw(account: dict, sport: int | None) -> dict:
    signing_key()
    with account_db(write=True) as connection, connection.cursor() as cursor:
        rows = load_members(cursor, account["sub"], lock=True)
        owned_active(rows, account)
        selected = [r for r in rows if sport is None or r["c_id_seq"] == f"{account['sub']}_{sport:02d}"]
        if not selected:
            raise HTTPException(status_code=404, detail="가입하지 않은 종목입니다.")
        active = [r for r in selected if r["c_deletdate"] is None]
        if not active:
            raise HTTPException(status_code=409, detail="이미 삭제 신청된 종목입니다. 유예 시작일은 변경하지 않습니다.")
        at = now_kst().replace(microsecond=0)
        for row in active:
            cursor.execute("UPDATE customer SET c_deletdate=%s WHERE c_id_seq=%s AND c_deletdate IS NULL",
                           (at, row["c_id_seq"]))
            row["c_deletdate"] = at
        # 예약/결제/팀/채팅 이력과 FK는 삭제하거나 재배정하지 않습니다.
        # 송신 worker·채팅은 회원의 활성 상태를 다시 확인합니다.
        return {"result": "OK", **summary(rows, at), "session": fresh_result(account, rows)}


@router.delete("/sports/{sport}", responses=ERRORS, summary="한 종목 삭제 신청 (30일 유예)")
# ************************
# 버그 확인 일 : 2026-10-29 / 위치 : 종목 경로 매개변수 검증
# 1. 버그 발생 위치 : Literal[int]를 사용한 URL의 /sports/{sport}
# 2. 버그 내용 : URL 문자열 '1'/'4'가 정수 Literal로 변환되지 않아 정상 요청도 422
# 3. 디버깅 내용 : Path(ge=1, le=4) 정수 변환 및 범위 검증으로 변경
# 4. 테스트 사항 : 종목 삭제, 중복 신청, 30일 직전/경계/직후 복구 회귀 검사
# 5. 결과 및 추후 보완 사항 : Mock 통과, 실제 DB 쓰기·프론트 연결은 별도 승인 후 검증
# ************************
def withdraw_sport(sport: int = Path(ge=1, le=4), account: dict = Depends(current_account)) -> dict:
    return withdraw(account, sport)


@router.post("/withdraw", responses=ERRORS, summary="활성 종목 전체 삭제 신청 (기존 신청일 유지)")
def withdraw_all(account: dict = Depends(current_account)) -> dict:
    return withdraw(account, None)


@router.post("/sports/{sport}/restore", responses=ERRORS, summary="활성 계정에서 30일 내 삭제 신청 종목 복구")
def restore_sport(sport: int = Path(ge=1, le=4), account: dict = Depends(current_account)) -> dict:
    signing_key()
    with account_db(write=True) as connection, connection.cursor() as cursor:
        rows = load_members(cursor, account["sub"], lock=True)
        owned_active(rows, account)
        row = next((r for r in rows if r["c_id_seq"] == f"{account['sub']}_{sport:02d}"), None)
        if row is None:
            raise HTTPException(status_code=404, detail="가입하지 않은 종목입니다.")
        restore_rows(cursor, [row], now_kst())
        return {"result": "OK", "session": fresh_result(account, rows), **summary(rows)}


def recovery_claims(credentials: HTTPAuthorizationCredentials | None = Depends(security)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="로그인으로 발급받은 복구 전용 Bearer 토큰이 필요합니다.")
    return decode_recovery(credentials.credentials)


def checked_recovery(cursor, claims: dict, lock: bool = False) -> list[dict]:
    rows = load_members(cursor, claims["sub"], lock)
    if (not rows or rows[0]["c_login_type"] != claims["provider"]
            or fingerprint(rows) != claims["snapshot"] or any(r["c_deletdate"] is None for r in rows)):
        raise HTTPException(status_code=401, detail="회원 상태가 변경되었습니다. 다시 로그인해 주세요.")
    return rows


def restore_rows(cursor, rows: list[dict], at) -> None:
    if any(sport_state(row, at) != "recoverable" for row in rows):
        raise HTTPException(status_code=409, detail="30일이 지났거나 복구 대상이 아닌 종목입니다.")
    for row in rows:
        cursor.execute("UPDATE customer SET c_deletdate=NULL WHERE c_id_seq=%s", (row["c_id_seq"],))
        row["c_deletdate"] = None


@router.get("/recovery", responses=ERRORS, summary="복구 전용 인증으로 복구 가능 종목 확인")
def get_recovery(claims: dict = Depends(recovery_claims)) -> dict:
    with account_db() as connection, connection.cursor() as cursor:
        rows = checked_recovery(cursor, claims)
        if not any(sport_state(row, now_kst()) == "recoverable" for row in rows):
            raise HTTPException(status_code=403, detail="복구 가능한 종목의 유예기간이 지났습니다.")
        return {"recovery_required": True, "confirmation": "정말로 복구하시겠습니까?", **summary(rows)}


@router.post("/recovery/restore", responses=ERRORS, summary="복구 확인 예: 선택한 유예 종목 복구 및 정상 JWT 발급")
def restore_account(sports: list[Literal[1, 2, 3, 4]] = Body(embed=True, min_length=1, max_length=4),
                    claims: dict = Depends(recovery_claims)) -> dict:
    if len(sports) != len(set(sports)):
        raise HTTPException(status_code=422, detail="중복 종목은 선택할 수 없습니다.")
    with account_db(write=True) as connection, connection.cursor() as cursor:
        rows = checked_recovery(cursor, claims, lock=True)
        selected = [r for r in rows if int(r["c_prefer_stock"]) in sports]
        if len(selected) != len(sports):
            raise HTTPException(status_code=404, detail="가입하지 않은 종목입니다.")
        restore_rows(cursor, selected, now_kst())
        # 아니오 선택은 이 API를 호출하지 않고 복구 토큰을 폐기합니다. DB는 변경하지 않습니다.
        return {"result": "OK", "session": fresh_result(claims, rows), **summary(rows)}

# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
