# 작업자 : 김병재
# 최초 작업 일 : 2026-10-27

# 내 제재 내역 조회 API (main.py의 prefix="/sanction"과 sanction.py의 prefix="/list"가 붙어 실제 주소는 /sanction/list)
#   GET /sanction/list?c_id_seq=...    내가 받은 제재 목록(최신순)과 화면 상단 "현재 상태" 배너 정보를 조회
# 조회 테이블: customer(회원 확인), c_sanction(제재), headquarter(제재 처리자 이름)
#
# [cs_detail 저장 형식] 본사가 제재를 등록할 때 "[제재종류] 제재 내용" 형태로 저장 (예: "[경고] 폭언으로 인한 비매너 행위")
#   제재종류 : 경고 / 이용정지 등. 앞의 대괄호가 없으면 종류를 "기타"로 내려줌
#   (report.r_reason의 "[경기:코드] 내용" 방식과 같은 패턴)
#
# [화면 규칙] 아래 상수만 고치면 기준이 바뀜
#   - 경고는 제재일로부터 90일이 지나면 소멸
#   - 현재 경고 횟수 = 아직 소멸되지 않은 경고 건수
#   - 이의신청은 제재일부터 7일까지 가능 (소멸되지 않은 경고/이용정지만)
#   - 경고 3회 누적 시 14일 이용 정지 (안내 문구는 고정)
# 이의신청 내역·이의신청 접수는 추후 작업 (appeal 테이블 저장 방식이 정해진 뒤)
import logging
import re
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Query, status

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

router = APIRouter()
logger = logging.getLogger(__name__)

WARNING_EXPIRE_DAYS = 90   # 경고 소멸까지 걸리는 일수
APPEAL_DAYS = 7            # 이의신청 가능 일수 (제재일부터)
SUSPEND_WARNING_COUNT = 3  # 이 횟수만큼 경고가 쌓이면 이용 정지
SUSPEND_DAYS = 14          # 이용 정지 일수 (안내 문구용)

# 제재 종류 이름
TYPE_WARNING = "경고"
TYPE_SUSPEND = "이용정지"
TYPE_ETC = "기타"
TYPE_EXPIRED = "소멸"  # 소멸된 경고의 화면 태그

# cs_detail 앞에 붙어 있는 "[제재종류] 제재 내용" 분리용
DETAIL_PATTERN = re.compile(r"^\[([^\]]+)\]\s*(.*)$", re.DOTALL)


# DB에서 받은 제재 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# now: 소멸/이의신청 가능 여부를 판단하는 기준 시각 (목록 전체에서 같은 값을 써야 해서 밖에서 받음)
def sanction_to_dict(row: dict, now: datetime) -> dict:
    detail = row["cs_detail"] or ""
    found = DETAIL_PATTERN.match(detail)
    sanction_type = found.group(1).strip() if found else TYPE_ETC
    content = found.group(2) if found else detail  # [제재종류] 부분을 뺀 순수 제재 내용

    cs_date = row["cs_date"]
    # 소멸은 경고에만 적용 (이용정지 등은 소멸일이 없음)
    expire_at = cs_date + timedelta(days=WARNING_EXPIRE_DAYS) if sanction_type == TYPE_WARNING else None
    expired = expire_at is not None and expire_at <= now

    # 이의신청: 소멸되지 않은 경고/이용정지를 제재일부터 7일 안에만 가능
    appeal_deadline = cs_date + timedelta(days=APPEAL_DAYS)
    can_appeal = sanction_type in (TYPE_WARNING, TYPE_SUSPEND) and not expired and now <= appeal_deadline

    return {
        "cs_seq": row["cs_seq"],                                          # 제재번호
        "cs_date": cs_date,                                               # 제재일
        "sanction_type": sanction_type,                                   # 제재 종류 (경고 / 이용정지 / 기타)
        "tag": TYPE_EXPIRED if expired else sanction_type,                # 카드 왼쪽 위 태그 (소멸된 경고는 "소멸")
        "expired": expired,                                               # 소멸 여부
        "expire_date": expire_at.date().isoformat() if expire_at else None,  # 경고 소멸일
        "cs_detail": content,                                             # 제재 내용
        "h_id": row["h_id"],                                              # 제재 처리 본사 직원 아이디
        "h_name": row["h_name"],                                          # 제재 처리 본사 직원 이름
        "appeal_deadline": appeal_deadline.date().isoformat(),            # 이의신청 가능 기한 (이 날짜까지)
        "can_appeal": can_appeal,                                         # [이의신청 하기] 버튼 노출 여부
    }


# 내 제재 내역 조회: 회원 아이디(c_id_seq)로 받은 제재를 최신순으로 조회
@router.get(
    "",
    responses={
        status.HTTP_404_NOT_FOUND: {"description": "존재하지 않는 회원 아이디"},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"description": "요청 값 검증 실패"},
        status.HTTP_500_INTERNAL_SERVER_ERROR: {"description": "제재 내역 조회 실패"},
    },
)
def list_sanction(
    c_id_seq: str = Query(min_length=1, max_length=50, description="회원 아이디(customer PK, 예: customer1_01)"),
) -> dict:
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 회원 존재 여부 확인 (c_id_seq가 customer PK)
            c_id_seq = c_id_seq.strip()
            cursor.execute("SELECT 1 FROM customer WHERE c_id_seq = %s", (c_id_seq,))
            if cursor.fetchone() is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")

            # 제재 처리자 이름은 headquarter에서 가져옴
            cursor.execute(
                """
                SELECT s.cs_seq, s.cs_date, s.cs_detail, s.h_id, h.h_name
                FROM c_sanction AS s
                LEFT JOIN headquarter AS h ON h.h_id = s.h_id
                WHERE s.c_id_seq = %s
                ORDER BY s.cs_date DESC, s.cs_seq DESC
                """,
                (c_id_seq,),
            )
            rows = cursor.fetchall()

        now = datetime.now()
        results = [sanction_to_dict(row, now) for row in rows]

        # 현재 상태 배너: 아직 소멸되지 않은 경고 건수와, 가장 먼저 소멸하는 경고의 소멸일
        active_warnings = [r for r in results if r["sanction_type"] == TYPE_WARNING and not r["expired"]]
        next_expire = min((r["expire_date"] for r in active_warnings), default=None)
        return {
            "c_id_seq": c_id_seq,
            "warning_count": len(active_warnings),   # "현재 상태 · 경고 N회"의 N
            "next_expire_date": next_expire,         # "경고는 90일 후 소멸돼요 (날짜)"의 날짜 (경고가 없으면 None)
            "notice": f"경고 {SUSPEND_WARNING_COUNT}회 누적 시 {SUSPEND_DAYS}일 이용 정지돼요. 경고는 {WARNING_EXPIRE_DAYS}일 후 소멸돼요.",
            "total": len(results),
            "results": results,
        }
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except Exception:
        logger.exception("제재 내역 조회 실패")
        raise HTTPException(status_code=500, detail="제재 내역 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료

# 최종 수정 일 : 2026-10-27
