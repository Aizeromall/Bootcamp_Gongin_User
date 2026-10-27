# 2026-10-27
# 작업자 : 양태건

"""회원 팀 개설 API.

POST /team/create
팀 정보·개설 기록·팀 가입·최초 팀장을 하나의 트랜잭션으로 저장합니다.
team_create.c_category: '개설일'은 개설, '폐지일'은 폐지 처리에 사용하는 구분입니다.
이 API는 개설 전용이므로 카테고리와 날짜를 클라이언트가 지정하지 않습니다.
"""

import logging
from typing import Optional

import pymysql
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from ..database import connect

router = APIRouter()
logger = logging.getLogger(__name__)


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 팀 ID·점수·팀장·개설일은 서버에서 정하고, 회원은 팀명과 로고만 입력합니다.
class CreateTeamRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "example": {
                "c_id_seq": "member_01",
                "t_name": "우리 축구팀",
                "t_logo": None,
            }
        },
    )

    c_id_seq: str = Field(min_length=1, max_length=50, description="개설 회원의 종목별 회원 ID")
    t_name: str = Field(min_length=1, max_length=50, description="팀명")
    t_logo: Optional[str] = Field(default=None, min_length=1, max_length=255, description="팀 로고 경로 또는 URL (선택)")


# 수정 일 : 2026-10-27 / 작업자 : 양태건
# 개설 회원이 자동으로 팀원이자 팀장이 됩니다. 실패하면 모든 저장을 취소합니다.
@router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    summary="회원 팀 개설 및 최초 팀장 등록",
    responses={
        404: {"description": "존재하지 않는 회원"},
        409: {"description": "이미 소속 팀이 있거나 팀 개설 정보 충돌"},
        422: {"description": "필수값·글자 수 검증 실패"},
        500: {"description": "팀 개설 처리 실패"},
    },
)
def create_team(payload: CreateTeamRequest):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 같은 회원의 동시 개설 요청은 회원 행을 잠가 순차 처리합니다.
            cursor.execute(
                "SELECT c_id_seq FROM customer WHERE c_id_seq = %s FOR UPDATE",
                (payload.c_id_seq,),
            )
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 회원의 종목별 소속은 t_register로 확인하여 기존 소속을 덮어쓰지 않습니다.
            cursor.execute(
                "SELECT 1 FROM t_register WHERE c_id_seq = %s LIMIT 1 FOR UPDATE",
                (payload.c_id_seq,),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="이미 소속 팀이 있습니다. 탈퇴 후 팀을 개설해 주세요.")

            # 팀 ID는 AUTO_INCREMENT, 초기 팀 점수는 DB 기본값(1500)을 사용합니다.
            cursor.execute(
                "INSERT INTO team (t_name, t_logo) VALUES (%s, %s)",
                (payload.t_name, payload.t_logo),
            )
            t_id = cursor.lastrowid
            if not isinstance(t_id, int) or t_id <= 0:
                raise RuntimeError("team.t_id 자동 증가값을 가져오지 못했습니다.")

            # 개설 기록: c_category는 '개설일', c_date는 실제 DB 처리 시각입니다.
            # 추후 폐지는 '폐지일'과 해당 처리 날짜로 구분하며 이 개설 API에서는 받지 않습니다.
            cursor.execute(
                """INSERT INTO team_create (t_id, c_id_seq, c_category, c_date)
                   VALUES (%s, %s, '개설일', NOW())""",
                (t_id, payload.c_id_seq),
            )

            # 개설자도 팀원 수에 포함되도록 팀 가입 기록을 저장합니다.
            cursor.execute(
                "INSERT INTO t_register (c_id_seq, t_id, tr_date) VALUES (%s, %s, NOW())",
                (payload.c_id_seq, t_id),
            )

            # 최초 팀장 기록을 명시하여 기존 팀 매칭의 최신 팀장 조회와 연결합니다.
            cursor.execute(
                """INSERT INTO team_captain_change (t_id, t_c_captain, t_c_date)
                   VALUES (%s, %s, NOW())""",
                (t_id, payload.c_id_seq),
            )

            # 선택한 종목의 회원 행만 소속 팀명을 갱신합니다. 다른 종목 가입 정보는 유지합니다.
            cursor.execute(
                "UPDATE customer SET c_team = %s WHERE c_id_seq = %s",
                (payload.t_name, payload.c_id_seq),
            )

            # 응답 날짜는 임의 생성하지 않고 실제 저장된 개설 시각을 조회합니다.
            cursor.execute("SELECT c_date FROM team_create WHERE t_id = %s", (t_id,))
            created = cursor.fetchone()
            if created is None:
                raise RuntimeError("팀 개설 기록을 확인하지 못했습니다.")

        connection.commit()
        return {
            "result": "OK",
            "t_id": t_id,
            "t_name": payload.t_name,
            "t_logo": payload.t_logo,
            "c_id_seq": payload.c_id_seq,
            "captain_id": payload.c_id_seq,
            "c_category": "개설일",
            "c_date": created["c_date"],
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.IntegrityError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 개설 정보 충돌")
        raise HTTPException(status_code=409, detail="회원 또는 팀 개설 정보를 확인해 주세요.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀 개설 처리 실패")
        raise HTTPException(status_code=500, detail="팀 개설 중 오류가 발생했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
