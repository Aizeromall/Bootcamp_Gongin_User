# 작업자 : 최현준
# 최초 작업 일 : 2026-10-27
"""일반 로그인 JWT로 본인의 FCM 기기 토큰을 등록·해제합니다. 새 클래스는 사용하지 않습니다."""

from contextlib import contextmanager
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException

from ..auth.token import current_account
from ..database import connect

router = APIRouter(prefix="/notifications", tags=["Notifications"])
ERRORS = {
    401: {"description": "인증 토큰 누락·위조·만료"},
    403: {"description": "본인에게 속하지 않은 종목별 회원 ID"},
    404: {"description": "탈퇴했거나 존재하지 않는 회원"},
    422: {"description": "기기 토큰 또는 플랫폼 입력값 오류"},
    500: {"description": "기기 정보 DB 처리 실패"},
    503: {"description": "서버 JWT 서명키 설정 필요"},
}


@contextmanager
def device_connection():
    connection = None
    try:
        connection = connect()
        yield connection
        connection.commit()
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except Exception:
        if connection is not None:
            connection.rollback()
        # 예외 SQL에 FCM 토큰이 포함될 수 있어 원문이나 토큰을 응답·로그에 남기지 않습니다.
        raise HTTPException(status_code=500, detail="기기 정보 DB 처리에 실패했습니다.") from None
    finally:
        if connection is not None:
            connection.close()


def verified_member(cursor, account: dict, requested: str | None) -> str:
    member = requested if requested is not None else account["c_id_seq"]
    if member not in account["member_ids"]:
        raise HTTPException(status_code=403, detail="본인의 종목별 회원 ID만 사용할 수 있습니다.")
    # JWT 발급 이후 탈퇴한 회원도 등록할 수 없도록 현재 DB 상태를 재검사합니다.
    cursor.execute("SELECT c_id_seq FROM customer WHERE c_id_seq = %s AND c_deletdate IS NULL FOR UPDATE", (member,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail="이용 가능한 회원 정보가 없습니다.")
    return member


@router.post("/devices", responses=ERRORS, summary="본인 FCM 기기 토큰 등록·갱신")
def register_device(
    f_token: str = Body(min_length=1, max_length=2048, pattern=r"^[!-~]+$",
                        description="Flutter FirebaseMessaging.getToken()으로 받은 문자열"),
    f_platform: Literal["android", "ios", "web"] = Body(),
    c_id_seq: str | None = Body(default=None, min_length=1, max_length=50,
                               description="생략하면 로그인 응답의 기본 종목별 회원 ID"),
    account: dict = Depends(current_account),
) -> dict:
    with device_connection() as connection:
        with connection.cursor() as cursor:
            member = verified_member(cursor, account, c_id_seq)
            # 토큰 UNIQUE 키로 중복 행을 막고 재로그인·토큰 갱신 시 현재 회원으로 연결합니다.
            cursor.execute(
                """INSERT INTO fcm_device (c_id_seq, f_token, f_platform, f_active, f_last_seen_at)
                   VALUES (%s, %s, %s, 1, NOW())
                   ON DUPLICATE KEY UPDATE c_id_seq = VALUES(c_id_seq),
                       f_platform = VALUES(f_platform), f_active = 1, f_last_seen_at = NOW()""",
                (member, f_token, f_platform),
            )
    return {"result": "OK", "c_id_seq": member, "active": True}


@router.post("/devices/deactivate", responses=ERRORS, summary="로그아웃 시 본인 기기 알림 해제")
def deactivate_device(
    f_token: str = Body(embed=True, min_length=1, max_length=2048, pattern=r"^[!-~]+$"),
    account: dict = Depends(current_account),
) -> dict:
    with device_connection() as connection:
        with connection.cursor() as cursor:
            # 토큰이 다른 회원에게 재등록되었다면 이전 회원의 로그아웃 요청으로 해제되지 않습니다.
            placeholders = ",".join(["%s"] * len(account["member_ids"]))
            cursor.execute(
                "UPDATE fcm_device SET f_active = 0 WHERE f_token = %s AND c_id_seq IN ("
                + placeholders + ")", (f_token, *account["member_ids"]),
            )
    return {"result": "OK", "active": False}

# 최종 수정 일 : 2026-10-27
