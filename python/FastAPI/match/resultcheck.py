# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 회원 경기결과 조회 API (match_router에 묶여 실제 주소 앞에 /match 가 붙음)
#   GET /match/result/customer/{c_id_seq}        회원이 참여한 경기결과 목록 (?e_code= 로 종목 필터 가능)
#   GET /match/result/{c_r_r_seq}                경기결과 1건 상세
# 결과는 경기매니저가 c_result_record(개인 결과기록)에 기록한 내용을 조회
# 조회만 하고 받는 값(body)이 없어서 BaseModel class 없음
import logging
from typing import Optional

import pymysql
from fastapi import APIRouter, HTTPException

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

# 이 파일의 API들을 담는 라우터 (__init__.py에서 match_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)


# DB에서 받은 결과 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄
def result_to_dict(row: dict) -> dict:
    return {
        "c_r_r_seq": row["c_r_r_seq"],              # 결과기록 번호
        "c_id_seq": row["c_id_seq"],                # 경기에 참여한 회원
        "c_r_r_team": row["c_r_r_team"],            # 경기팀
        "c_r_r_code": row["c_r_r_code"],            # 경기코드
        "c_r_r_score": row["c_r_r_score"],          # 경기 스코어
        "c_r_r_date": row["c_r_r_date"],            # 기록일
        "e_code": row["e_code"],                    # 종목코드
        "c_r_r_statcode": row["c_r_r_statcode"],    # 스탯코드
        "g_code": row["g_code"],                    # 구장코드
        "g_name": row["g_name"],                    # 구장명 (ground JOIN)
        "g_address": row["g_address"],              # 구장 주소 (ground JOIN)
        "m_id": row["m_id"],                        # 기록한 경기매니저
        "m_name": row["m_name"],                    # 경기매니저 이름 (match_manager JOIN)
    }


# 결과 조회에서 공통으로 쓰는 SELECT
# c / g / m 은 테이블 별칭 (c_result_record / ground / match_manager)
# INNER JOIN ground : 경기한 구장의 이름·주소를 함께 가져옴
# INNER JOIN match_manager : 결과를 기록한 매니저 이름을 함께 가져옴
RESULT_SELECT = """
    SELECT c.c_r_r_seq, c.c_id_seq, c.c_r_r_team, c.c_r_r_code, c.c_r_r_score, c.c_r_r_date,
        c.e_code, c.c_r_r_statcode, c.g_code, g.g_name, g.g_address, c.m_id, m.m_name
    FROM c_result_record AS c
    INNER JOIN ground AS g ON g.g_code = c.g_code
    INNER JOIN match_manager AS m ON m.m_id = c.m_id
"""


# 회원이 참여한 경기결과 목록 조회
# e_code가 있으면 해당 종목의 결과만 조회
# 예: /match/result/customer/hong_01?e_code=01
@router.get("/result/customer/{c_id_seq}")
def select_results_by_customer(c_id_seq: str, e_code: Optional[str] = None):
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            sql = RESULT_SELECT + " WHERE c.c_id_seq = %s"
            params = (c_id_seq,)
            if e_code and e_code.strip():
                sql += " AND c.e_code = %s"
                params = (c_id_seq, e_code.strip())
            sql += " ORDER BY c.c_r_r_date DESC, c.c_r_r_seq DESC"  # 최근 경기부터
            cursor.execute(sql, params)  # %s 자리에 값이 순서대로 들어감 (SQL 인젝션 방지)
            rows = cursor.fetchall()  # 결과 전체를 dict 목록으로 받음
        # 경기결과가 하나도 없으면 빈 리스트 [] 가 나감 (에러 아님)
        return {"results": [result_to_dict(row) for row in rows]}
    except pymysql.MySQLError:
        logger.exception("회원 경기결과 DB 조회 실패")
        raise HTTPException(status_code=500, detail="경기결과 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("회원 경기결과 조회 실패")
        raise HTTPException(status_code=500, detail="경기결과 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 경기결과 1건 상세 조회
# 주의: "/result/customer/.." 보다 아래에 있어야 "customer"가 c_r_r_seq로 잘못 인식되지 않음
@router.get("/result/{c_r_r_seq}")
def select_result(c_r_r_seq: int):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = RESULT_SELECT + " WHERE c.c_r_r_seq = %s"
            cursor.execute(sql, (c_r_r_seq,))  # 값이 1개여도 튜플이라 (c_r_r_seq,) 처럼 쉼표 필요
            row = cursor.fetchone()  # 1건만 받음 (없으면 None)
        if row is None:
            raise HTTPException(status_code=404, detail="존재하지 않는 경기결과 번호입니다.")
        return result_to_dict(row)
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("경기결과 상세 DB 조회 실패")
        raise HTTPException(status_code=500, detail="경기결과 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("경기결과 상세 조회 실패")
        raise HTTPException(status_code=500, detail="경기결과 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-23
