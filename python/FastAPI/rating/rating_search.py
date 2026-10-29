# 작업자 : 신현진
# 최초 작업 일 : 2026-10-29

# 회원·팀 등급 점수 조회 API (rating_router에 묶여 실제 주소 앞에 /rating 이 붙음)
#   GET /rating/tiers                              등급 구간표 (관리자 앱과 같은 기준)
#   GET /rating/summary/{c_id_seq}?recent=5        내 수준 통계 (현재 점수·등급·다음 등급까지 남은 점수·최고/최저/평균·최근 N경기 변동 합)
#   GET /rating/history/{c_id_seq}?limit=30        내 경기별 점수 변동 목록 (최신순, 점수 추이 그래프에도 사용)
#   GET /rating/team/{t_id}?limit=30               팀 경기별 점수 변동 목록 (최신순)
#
# [점수는 읽기만 함]
#   customer.c_rating / team.t_rating / 경기별 전·후 점수는 관리자 앱의 경기 결과 등록에서만 바뀜
#   이 파일은 SELECT만 실행하고 점수를 수정하지 않음
#
# [종목별 점수] 회원 ID가 종목마다 다름 (아이디_01 축구 / _02 농구 / _03 야구 / _04 배구)
#   → 종목을 바꾸면 그 종목의 c_id_seq로 조회 (점수가 종목별로 따로 쌓임)
#
# [경기별 점수 기록] (관리자 앱 match_result_insert.py에서 저장)
#   c_result_record.c_r_r_rating_before / c_r_r_rating_after : 회원의 그 경기 반영 전 / 후 점수 (변동 = 후 - 전)
#   t_result_record.t_r_r_rating_after                       : 팀의 그 경기 반영 후 점수
#   점수 변동(±)은 따로 저장하지 않고 조회할 때 "후 - 전"으로 계산
#
# [점수가 비어 있는 경기] 결석(점수 미반영) 또는 컬럼 추가 전에 등록된 경기
#   → 응답에 null을 보내지 않고 그 시점의 기존 점수를 그대로 보여 줌 (전 = 후, 변동 0)
#      기존 점수 = 그 회원(팀)의 직전 경기 후 점수, 직전 기록이 없으면 시작 점수 1500
#   결석 여부는 c_r_r_attendance(true 출석 / false 결석)로 앱에서 구분
import logging
import re

import pymysql
from fastapi import APIRouter, HTTPException, Query

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)

# 이 파일의 API들을 담는 라우터 (rating/__init__.py에서 rating_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# c_id_seq 끝 번호 → 종목 (match/reservation.py의 SPORT_BY_SEQUENCE와 같은 규칙)
# 조회 전용 API라서 예약·알림 모듈을 불러오지 않도록 이 파일에서 직접 확인
SPORT_BY_SEQUENCE = {1: "축구", 2: "농구", 3: "야구", 4: "배구"}
CUSTOMER_SEQUENCE_PATTERN = re.compile(r"^.+_0([1-4])$")


# c_id_seq 끝 번호(01~04)로 종목 이름 확인 (형식이 틀리면 DB 조회 전에 400)
def sport_from_customer_id(c_id_seq: str) -> str:
    matched = CUSTOMER_SEQUENCE_PATTERN.fullmatch(c_id_seq)
    if matched is None:
        raise HTTPException(status_code=400, detail="c_id_seq는 아이디_01부터 아이디_04 형식이어야 합니다.")
    return SPORT_BY_SEQUENCE[int(matched.group(1))]

# 점수 기준 값 (관리자 앱 match_result_insert.py와 같은 값)
RATING_START = 1500   # 가입·팀 개설 시작 점수 (비기너 1, DB 기본값)
RATING_FLOOR = 1000   # 최저 점수

# 등급 구간 (점수가 위에서부터 처음으로 기준 이상이 되는 등급)
# 관리자 앱 match_result_insert.py의 TIERS와 반드시 같게 유지 (관리자 서버 GET /match/rating/stat_keys의 tiers)
# 1000 ~ 1299 는 루키 1
TIERS = [
    (3000, "프로"),
    (2700, "세미프로 5"), (2600, "세미프로 4"), (2500, "세미프로 3"), (2400, "세미프로 2"), (2300, "세미프로 1"),
    (2200, "아마추어 5"), (2100, "아마추어 4"), (2000, "아마추어 3"), (1900, "아마추어 2"), (1800, "아마추어 1"),
    (1700, "비기너 3"), (1600, "비기너 2"), (1500, "비기너 1"),
    (1400, "루키 3"), (1300, "루키 2"),
]
TIER_LOWEST = "루키 1"

# 경기 기록의 종목코드(e_code) → 종목 이름
E_CODE_NAMES = {"SOCCER": "축구", "BASKETBALL": "농구", "BASEBALL": "야구", "VOLLEYBALL": "배구"}


# 경기 전·후 점수가 비어 있으면 기존 점수로 채움 (결석·이전 기록은 점수 미반영이라 전 = 후)
#   previous_after : 직전 경기의 경기 후 점수 (직전 기록이 없으면 None → 시작 점수 1500)
#   반환 : (경기 전 점수, 경기 후 점수)
def fill_rating(before, after, previous_after) -> tuple[int, int]:
    if before is not None and after is not None:
        return before, after
    current = previous_after if previous_after is not None else RATING_START
    return current, current


# 점수 → 등급 이름 (예: 1650 → "비기너 2", 점수가 없으면 None)
def rating_tier(rating) -> str | None:
    if rating is None:
        return None
    for min_rating, name in TIERS:
        if rating >= min_rating:
            return name
    return TIER_LOWEST


# 다음 등급 이름과 남은 점수 (예: 1650 → ("비기너 3", 50), 프로이거나 점수가 없으면 (None, None))
def next_tier(rating) -> tuple[str | None, int | None]:
    if rating is None:
        return None, None
    for min_rating, name in reversed(TIERS):   # 낮은 등급부터 확인
        if rating < min_rating:
            return name, min_rating - rating
    return None, None


# 회원이 존재하는지 확인하고 현재 점수 반환 (없으면 404)
def find_customer(cursor, c_id_seq: str) -> dict:
    cursor.execute("SELECT c_id_seq, c_name, c_rating FROM customer WHERE c_id_seq = %s", (c_id_seq,))
    customer = cursor.fetchone()
    if customer is None:
        raise HTTPException(status_code=404, detail="존재하지 않는 회원입니다.")
    return customer


# 등급 구간표 (앱의 등급 안내·다음 등급 표시용)
# 낮은 등급부터 순서대로 [{tier, min_rating, max_rating}] (프로는 max_rating = None)
@router.get("/tiers")
def select_rating_tiers():
    ordered = [(RATING_FLOOR, TIER_LOWEST)] + list(reversed(TIERS))
    tiers = []
    for index, (min_rating, name) in enumerate(ordered):
        upper = ordered[index + 1][0] - 1 if index + 1 < len(ordered) else None
        tiers.append({"tier": name, "min_rating": min_rating, "max_rating": upper})
    return {"rating_start": RATING_START, "rating_floor": RATING_FLOOR, "tiers": tiers}


# 내 수준 통계 (점수·등급 카드)
# 현재 점수는 customer.c_rating, 통계는 전·후 점수가 모두 있는 경기만 사용
# 예: /rating/summary/hong_01?recent=5
@router.get("/summary/{c_id_seq}")
def select_rating_summary(
    c_id_seq: str,
    recent: int = Query(5, ge=1, le=50, description="최근 몇 경기의 점수 변동을 합칠지"),
):
    sport_name = sport_from_customer_id(c_id_seq)  # 종목 확인 (형식이 틀리면 400)
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            customer = find_customer(cursor, c_id_seq)

            # 1) 경기 수 + 점수 통계 (최고·최저·평균은 점수가 기록된 경기의 경기 후 점수 기준)
            cursor.execute(
                """SELECT COUNT(*) AS total_matches,
                        SUM(c_r_r_rating_before IS NOT NULL AND c_r_r_rating_after IS NOT NULL) AS rated_matches,
                        MAX(CASE WHEN c_r_r_rating_before IS NOT NULL THEN c_r_r_rating_after END) AS best_rating,
                        MIN(CASE WHEN c_r_r_rating_before IS NOT NULL THEN c_r_r_rating_after END) AS lowest_rating,
                        AVG(CASE WHEN c_r_r_rating_before IS NOT NULL THEN c_r_r_rating_after END) AS average_rating
                    FROM c_result_record
                    WHERE c_id_seq = %s""",
                (c_id_seq,),
            )
            stats = cursor.fetchone()

            # 2) 최근 N경기 점수 변동 (점수가 기록된 경기만, 최신순)
            cursor.execute(
                """SELECT c_r_r_rating_after - c_r_r_rating_before AS rating_change
                    FROM c_result_record
                    WHERE c_id_seq = %s AND c_r_r_rating_before IS NOT NULL AND c_r_r_rating_after IS NOT NULL
                    ORDER BY c_r_r_date DESC, c_r_r_seq DESC
                    LIMIT %s""",
                (c_id_seq, recent),
            )
            recent_changes = [int(row["rating_change"]) for row in cursor.fetchall()]

        current = customer["c_rating"]  # 현재 점수 (관리자 앱 결과 등록에서만 바뀜)
        next_name, points_to_next = next_tier(current)
        average = stats["average_rating"]
        return {
            "c_id_seq": c_id_seq,                               # 조회한 종목별 회원 ID
            "c_name": customer["c_name"],                       # 회원 이름
            "sport": sport_name,                                # 종목 (ID 끝 번호 기준)
            "current_rating": current,                          # 현재 점수 (없으면 None)
            "tier": rating_tier(current),                       # 현재 등급 (예: "비기너 2")
            "next_tier": next_name,                             # 다음 등급 (프로면 None)
            "points_to_next_tier": points_to_next,              # 다음 등급까지 남은 점수 (프로면 None)
            "total_matches": int(stats["total_matches"] or 0),  # 전체 경기 기록 수 (점수 기록 없는 경기 포함)
            "rated_matches": int(stats["rated_matches"] or 0),  # 점수 변동이 기록된 경기 수
            "best_rating": stats["best_rating"],                # 최고 점수 (기록이 없으면 None)
            "lowest_rating": stats["lowest_rating"],            # 최저 점수
            "average_rating": round(float(average)) if average is not None else None,  # 평균 점수 (정수로 반올림)
            "recent_count": len(recent_changes),                # 최근 변동에 실제로 합친 경기 수
            "recent_change_sum": sum(recent_changes),           # 최근 N경기 변동 합 (예: +34)
        }
    except HTTPException:
        raise  # 위에서 만든 404는 500으로 바뀌지 않게 그대로 전달
    except pymysql.MySQLError:
        logger.exception("회원 점수 통계 DB 조회 실패")
        raise HTTPException(status_code=500, detail="점수 통계 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("회원 점수 통계 조회 실패")
        raise HTTPException(status_code=500, detail="점수 통계 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 내 경기별 점수 변동 목록 (최신순)
# 항목마다 경기 전 내 점수 → 경기 후 내 점수와 변동(±)을 보냄 (점수가 비어 있던 경기는 기존 점수, 변동 0)
# 점수 추이 그래프는 rating_after를 날짜 오름차순으로 이어서 그림
# 예: /rating/history/hong_01?limit=30
@router.get("/history/{c_id_seq}")
def select_rating_history(
    c_id_seq: str,
    limit: int = Query(30, ge=1, le=200, description="최근 몇 경기까지 조회할지"),
):
    sport_name = sport_from_customer_id(c_id_seq)
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            find_customer(cursor, c_id_seq)

            # c / g 는 테이블 별칭 (c_result_record / ground)
            # LEFT JOIN ground : 구장 정보가 없어도 기록은 빠지지 않게
            # 점수가 빈 경기에 기존 점수(직전 경기 후 점수)를 채우기 위해 오래된 순으로 전부 조회하고,
            # 응답은 최신순으로 limit 개만 보냄
            cursor.execute(
                """SELECT c.c_r_r_seq, c.c_r_r_date, c.e_code, c.c_r_r_team, c.c_r_r_score, c.c_r_r_code,
                        c.c_r_r_attendance, c.c_r_r_rating_before, c.c_r_r_rating_after, c.g_code, g.g_name
                    FROM c_result_record AS c
                    LEFT JOIN ground AS g ON g.g_code = c.g_code
                    WHERE c.c_id_seq = %s
                    ORDER BY c.c_r_r_date, c.c_r_r_seq""",
                (c_id_seq,),
            )
            rows = cursor.fetchall()

        results = []
        previous_after = None   # 직전 경기 후 점수 (첫 경기면 None → 시작 점수 1500)
        for row in rows:
            # 점수가 비어 있으면(결석·이전 기록) 기존 점수로 채워서 전 = 후, 변동 0
            before, after = fill_rating(row["c_r_r_rating_before"], row["c_r_r_rating_after"], previous_after)
            previous_after = after
            results.append({
                "c_r_r_seq": row["c_r_r_seq"],                         # 결과기록 번호
                "c_r_r_date": row["c_r_r_date"],                       # 경기(기록) 날짜
                "e_code": row["e_code"],                               # 종목코드
                "sport": E_CODE_NAMES.get(row["e_code"], sport_name),  # 종목 이름
                "c_r_r_team": row["c_r_r_team"],                       # 경기팀
                "c_r_r_score": row["c_r_r_score"],                     # 스코어
                "c_r_r_code": row["c_r_r_code"],                       # 경기코드
                "g_code": row["g_code"],                               # 구장코드
                "g_name": row["g_name"],                               # 구장명
                # 출석 여부 (true 출석 / false 결석 → 점수 미반영 / 기록 전이면 None)
                "c_r_r_attendance": None if row["c_r_r_attendance"] is None else bool(row["c_r_r_attendance"]),
                "rating_before": before,                               # 경기 전 내 점수
                "rating_after": after,                                 # 경기 후 내 점수 (그래프 값)
                "rating_change": after - before,                       # 변동 (예: +24 / -10, 미반영이면 0)
                "tier_after": rating_tier(after),                      # 경기 후 등급
            })
        results.reverse()  # 최신순
        return {"c_id_seq": c_id_seq, "sport": sport_name, "results": results[:limit]}
    except HTTPException:
        raise
    except pymysql.MySQLError:
        logger.exception("회원 점수 변동 DB 조회 실패")
        raise HTTPException(status_code=500, detail="점수 변동 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("회원 점수 변동 조회 실패")
        raise HTTPException(status_code=500, detail="점수 변동 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 팀 경기별 점수 변동 목록 (최신순)
# t_result_record에는 경기 후 점수만 있으므로 변동은 직전 기록과의 차이로 계산
#   - 팀의 첫 경기 기록 : 시작 점수(1500)와의 차이
#   - 점수가 비어 있는 경기(컬럼 추가 전 등록) : 직전 점수를 그대로 보여 주고 변동 0
# 예: /rating/team/3?limit=30
@router.get("/team/{t_id}")
def select_team_rating_history(
    t_id: int,
    limit: int = Query(30, ge=1, le=200, description="최근 몇 경기까지 조회할지"),
):
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            cursor.execute("SELECT t_id, t_name, t_rating FROM team WHERE t_id = %s", (t_id,))
            team = cursor.fetchone()
            if team is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀입니다.")

            # 변동 계산을 위해 오래된 순으로 전부 조회한 뒤, 응답은 최신순으로 limit 개만 보냄
            cursor.execute(
                """SELECT t.t_r_r_seq, t.t_r_r_date, t.e_code, t.t_r_r_score, t.t_r_r_m_code,
                        t.t_r_r_rating_after, t.g_code, g.g_name
                    FROM t_result_record AS t
                    LEFT JOIN ground AS g ON g.g_code = t.g_code
                    WHERE t.t_id = %s
                    ORDER BY t.t_r_r_date, t.t_r_r_seq""",
                (t_id,),
            )
            rows = cursor.fetchall()

        results = []
        previous_after = None   # 직전 경기 후 팀 점수 (첫 경기면 None → 시작 점수 1500)
        for row in rows:
            # 경기 전 점수 = 직전 경기 후 점수 (첫 경기는 1500), 점수가 비어 있으면 경기 후 = 경기 전
            before, _ = fill_rating(None, None, previous_after)
            after = row["t_r_r_rating_after"] if row["t_r_r_rating_after"] is not None else before
            previous_after = after
            results.append({
                "t_r_r_seq": row["t_r_r_seq"],                    # 팀 결과기록 번호
                "t_r_r_date": row["t_r_r_date"],                  # 경기(기록) 날짜
                "e_code": row["e_code"],                          # 종목코드
                "sport": E_CODE_NAMES.get(row["e_code"]),         # 종목 이름
                "t_r_r_score": row["t_r_r_score"],                # 팀 스코어
                "t_r_r_m_code": row["t_r_r_m_code"],              # 경기코드
                "g_code": row["g_code"],                          # 구장코드
                "g_name": row["g_name"],                          # 구장명
                "rating_before": before,                          # 경기 전 팀 점수 (직전 경기 후 점수)
                "rating_after": after,                            # 경기 후 팀 점수
                "rating_change": after - before,                  # 변동 (점수가 비어 있던 경기는 0)
                "tier_after": rating_tier(after),                 # 경기 후 등급
            })
        results.reverse()  # 최신순
        return {
            "t_id": team["t_id"],
            "t_name": team["t_name"],
            "current_rating": team["t_rating"],     # 현재 팀 점수
            "tier": rating_tier(team["t_rating"]),  # 현재 팀 등급
            "results": results[:limit],
        }
    except HTTPException:
        raise
    except pymysql.MySQLError:
        logger.exception("팀 점수 변동 DB 조회 실패")
        raise HTTPException(status_code=500, detail="팀 점수 변동 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀 점수 변동 조회 실패")
        raise HTTPException(status_code=500, detail="팀 점수 변동 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()

# 최종 수정 일 : 2026-10-29
