# 작업자 : 신현진
# 최초 작업 일 : 2026-10-23

# 구장 조회 API (match_router에 묶여 실제 주소 앞에 /match 가 붙음)
#   GET /match/ground                  전체 구장 목록 (?keyword= 로 구장명/주소 검색 가능)
#   GET /match/ground/{g_code}         구장 1건 상세
# 조회만 하고 받는 값(body)이 없어서 BaseModel class 없음
import logging
from typing import Optional

import pymysql
from fastapi import APIRouter, HTTPException

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

# 이 파일의 API들을 담는 라우터 (__init__.py에서 match_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)


# DB에서 받은 구장 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
# database.py가 DictCursor를 쓰기 때문에 row["컬럼명"]으로 값을 꺼냄
# (Flutter의 Ground.fromJson 키 이름과 똑같이 맞춤)
def ground_to_dict(row: dict) -> dict:
    return {
        "g_code": row["g_code"],                # 구장코드
        "g_name": row["g_name"],                # 구장명
        "g_address": row["g_address"],          # 주소
        "g_num": row["g_num"],                  # 수용인원
        "g_price": row["g_price"],              # 이용금액
        "g_information": row["g_information"],  # 이용정보
        "g_time": row["g_time"],                # 이용시간
        "g_lat": row["g_lat"],                  # 위도
        "g_lng": row["g_lng"],                  # 경도
    }


# 전체 구장 목록 조회
# keyword가 있으면 구장명 또는 주소에 keyword가 들어간 구장만 조회
# 예: /match/ground?keyword=강남
@router.get("/ground")
def select_grounds(keyword: Optional[str] = None):
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            sql = """
                SELECT g_code, g_name, g_address, g_num, g_price, g_information, g_time, g_lat, g_lng
                FROM ground
            """
            params = ()
            if keyword and keyword.strip():
                # LIKE '%검색어%' : 앞뒤에 무엇이 와도 검색어가 포함되면 조회
                sql += " WHERE g_name LIKE %s OR g_address LIKE %s"
                like_keyword = f"%{keyword.strip()}%"
                params = (like_keyword, like_keyword)
            sql += " ORDER BY g_name"  # 구장명 가나다순 정렬
            cursor.execute(sql, params)  # %s 자리에 값이 순서대로 들어감 (SQL 인젝션 방지)
            rows = cursor.fetchall()  # 결과 전체를 dict 목록으로 받음
        # 구장이 하나도 없으면 빈 리스트 [] 가 나감 (에러 아님)
        return {"results": [ground_to_dict(row) for row in rows]}
    except pymysql.MySQLError:
        logger.exception("구장 목록 DB 조회 실패")
        raise HTTPException(status_code=500, detail="구장 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("구장 목록 조회 실패")
        raise HTTPException(status_code=500, detail="구장 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 구장 1건 상세 조회
# 주의: "/ground" 보다 아래에 있어야 하며, 주소의 g_code로 구장 1곳만 조회
@router.get("/ground/{g_code}")
def select_ground(g_code: str):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            sql = """
                SELECT g_code, g_name, g_address, g_num, g_price, g_information, g_lat, g_lng
                FROM ground
                WHERE g_code = %s
            """
            cursor.execute(sql, (g_code,))  # 값이 1개여도 튜플이라 (g_code,) 처럼 쉼표 필요
            row = cursor.fetchone()  # 1건만 받음 (없으면 None)
        if row is None:
            raise HTTPException(status_code=404, detail="존재하지 않는 구장 코드입니다.")
        return ground_to_dict(row)
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("구장 상세 DB 조회 실패")
        raise HTTPException(status_code=500, detail="구장 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("구장 상세 조회 실패")
        raise HTTPException(status_code=500, detail="구장 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-23
