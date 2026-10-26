# 작업자 : 신현진
# 최초 작업 일 : 2026-10-26

# 팀 경기 매칭 API (team_match_router에 묶여 실제 주소 앞에 /team_match 가 붙음)
#   GET  /team_match/rentals/{c_id_seq}                   매칭신청 글을 쓸 수 있는 팀장의 구장대여 내역
#   POST /team_match/post                                 구장대여 내역으로 [매칭신청] 게시글 작성
#   GET  /team_match/posts?c_id_seq=회원ID                 상대 팀 선택 리스트 (매칭신청 게시글 + 내 신청 상태)
#   POST /team_match/request                              상대 팀 게시글에 팀매칭 신청 ("요청됨")
#   GET  /team_match/requests/{bulletin_seq}?c_id_seq=    내 게시글에 들어온 신청 팀 목록 (대결 여부 판단용)
#   POST /team_match/accept                               신청 수락 → 팀 매칭 성사
#   POST /team_match/reject                               신청 거절
#
# [사용 테이블] 새 테이블·컬럼 없이 ERD 그대로 사용
#   board_a_write (게시글작성) : 게시글과 댓글을 한 테이블에 저장
#     - 게시글 행 : comment_seq = 0 (bulletin_seq는 AUTO_INCREMENT)
#     - 댓글 행   : 같은 bulletin_seq + comment_seq 1, 2, 3 ... (게시글마다 1부터 따로 증가)
#     - 대댓글    : reply_to_comment_seq = 부모 댓글의 comment_seq, depth = 1, 2
#   team (팀) : t_id, t_name, t_logo, t_rating(팀 Elo 점수 → 화면의 팀 레벨 표시용)
#   team_match (팀 매치 성사) : home_t_id, away_t_id, team_num, team_start, team_end
#   team_captain_change (변경하다) / team_create : 팀장 확인
#   t_register : 팀원 수
#
# [진행 과정]
#   1) 팀장이 구장대여(reservation_category = 2)를 한 뒤, 그 대여 내역으로 [매칭신청] 게시글 작성
#      → 게시글 내용 첫 줄에 [예약번호:r_seq] 를 넣어서 구장·일시를 대여 예약과 연결
#   2) 다른 팀 팀장이 리스트에서 게시글을 골라 신청
#      → 댓글(depth 0) "OO 팀이 팀매칭을 신청하였습니다." (신청 팀 팀장 이름으로)
#   3) 게시글 팀 팀장이 신청 팀 정보를 보고 판단
#      수락 → 대댓글(depth 1) "OO 팀의 팀매칭 요청이 수락되었습니다."
#             + 2번째 대댓글(depth 2) "OO 팀과 OO 팀 매칭이 성사되었습니다."
#             + team_match에 경기 1건 저장, 대여 예약 r_check = 1 (팀매칭 성사)
#      거절 → 대댓글(depth 1) "OO 팀의 팀매칭 요청이 거절되었습니다."
#   [매칭신청] 게시글은 회원이 댓글을 직접 쓰지 못하고 위 과정의 댓글만 달림
#   (게시판 댓글 API에서 is_team_match_post()로 확인해서 막아 주세요)
#
# [팀장 확인] team_captain_change의 가장 최근 팀장, 변경 기록이 없으면 team_create의 생성자
import logging
import re
from datetime import date, datetime, time, timedelta
from typing import Annotated, Optional

import pymysql
from fastapi import APIRouter, Body, HTTPException, Query, status

from ..database import connect  # 공용 DB 연결 함수 (python/FastAPI/database.py)
# 구장대여 예약과 같은 기준을 쓰기 위해 match 폴더의 공용 값·함수를 가져옴
#   sport_from_customer_id : c_id_seq 끝 번호(01~04)로 종목 확인 (축구·농구·야구·배구)
#   format_time : 시간 값 → "08:00" 형식으로 통일
#   RESERVATION_RENTAL / category_condition / reservation_type_condition : 구장대여·취소 여부 조건
from ..match.reservation import sport_from_customer_id
from ..match.reservation_search import format_time
from ..match.reservation_status import RESERVATION_RENTAL, category_condition, reservation_type_condition

# 이 파일의 API들을 담는 라우터 (team_match/__init__.py에서 team_match_router로 묶임)
router = APIRouter()
logger = logging.getLogger(__name__)

# 게시판 카테고리 이름 (board_a_write.board_category)
BOARD_CATEGORY_TEAM_MATCH = "매칭신청"

# board_a_write에서 게시글 행의 comment_seq 값 (댓글 행은 1부터)
POST_COMMENT_SEQ = 0

# 게시글 내용 첫 줄에 넣는 대여 예약번호 표시 (예: [예약번호:15])
POST_RESERVATION_MARK = "[예약번호:{r_seq}]"
POST_RESERVATION_PATTERN = re.compile(r"^\[예약번호:(\d+)\]")
# SQL에서 게시글 내용의 [예약번호:15] → 15 를 꺼내는 식 (b = board_a_write 별칭)
POST_RESERVATION_SEQ_SQL = (
    "CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(b.board_content, ']', 1), ':', -1) AS UNSIGNED)"
)

# 매칭 진행 댓글 문구 (댓글 내용 끝부분으로 수락/거절을 구분하므로 문구를 바꾸면 아래 판단도 같이 바뀜)
REQUEST_TEXT = "{team} 팀이 팀매칭을 신청하였습니다."
ACCEPT_TEXT = "{team} 팀의 팀매칭 요청이 수락되었습니다."
REJECT_TEXT = "{team} 팀의 팀매칭 요청이 거절되었습니다."
SUCCESS_TEXT = "{request_team} 팀과 {post_team} 팀 매칭이 성사되었습니다."
ACCEPT_SUFFIX = "수락되었습니다."

# 신청 상태 (앱 버튼·라벨 표시용)
STATUS_NONE = "none"            # 신청 전
STATUS_REQUESTED = "requested"  # 요청됨 (상대 팀 판단 대기)
STATUS_ACCEPTED = "accepted"    # 수락 → 매칭 성사
STATUS_REJECTED = "rejected"    # 거절됨 (다시 신청 가능)

# 회원이 팀장인 팀 찾기 (t_rating : 팀 Elo 점수, 화면의 팀 레벨 표시용)
# 팀장 = team_captain_change의 가장 최근 팀장, 변경 기록이 없으면 team_create의 생성자
CAPTAIN_TEAM_SQL = """
    SELECT t.t_id, t.t_name, t.t_logo, t.t_rating
    FROM team AS t
    INNER JOIN team_create AS tc ON tc.t_id = t.t_id
    WHERE COALESCE(
        (SELECT cc.t_c_captain FROM team_captain_change AS cc
            WHERE cc.t_id = t.t_id
            ORDER BY cc.t_c_date DESC, cc.t_c_seq DESC
            LIMIT 1),
        tc.c_id_seq
    ) = %s
    ORDER BY t.t_id
    LIMIT 1
"""

# 매칭신청 게시글 + 연결된 구장대여 예약 + 구장 정보
# b / r / g 는 테이블 별칭 (board_a_write / reservation / ground)
# b.comment_seq = 0 : 게시글 행만 (댓글 행 제외)
# 게시글 내용 첫 줄의 [예약번호:r_seq]로 reservation과 연결
POST_SELECT = f"""
    SELECT b.bulletin_seq, b.c_id_seq, b.event_category, b.board_title, b.board_content, b.board_date,
        r.r_seq, r.g_code, g.g_name, g.g_address, g.g_num, r.r_date, r.rs_time, r.re_time, r.r_check,
        r.r_category, r.r_c_category
    FROM board_a_write AS b
    INNER JOIN reservation AS r ON r.r_seq = {POST_RESERVATION_SEQ_SQL}
    INNER JOIN ground AS g ON g.g_code = r.g_code
    WHERE b.comment_seq = {POST_COMMENT_SEQ} AND b.board_category = %s AND b.board_content LIKE %s
"""


# 회원이 팀장인 팀 조회 (팀장이 아니면 None)
def find_captain_team(cursor, c_id_seq: str) -> dict | None:
    cursor.execute(CAPTAIN_TEAM_SQL, (c_id_seq,))
    return cursor.fetchone()


# 게시글이 [매칭신청] 게시글인지 확인
# 게시판 댓글 API에서 회원이 직접 댓글을 쓰지 못하게 막을 때 사용 (True면 자유 댓글 금지)
def is_team_match_post(cursor, bulletin_seq: int) -> bool:
    cursor.execute(
        "SELECT board_category FROM board_a_write WHERE bulletin_seq = %s AND comment_seq = %s",
        (bulletin_seq, POST_COMMENT_SEQ),
    )
    row = cursor.fetchone()
    return row is not None and row["board_category"] == BOARD_CATEGORY_TEAM_MATCH


# 게시글에 댓글 행 저장 (comment_seq는 게시글마다 1부터 증가)
# 호출 전에 게시글 행을 FOR UPDATE로 잠가 두어 같은 번호가 두 번 나오지 않게 함
#   reply_to_comment_seq : 대댓글이면 부모 댓글의 comment_seq, 신청 댓글이면 None
def insert_comment(cursor, bulletin_seq: int, c_id_seq: str, reply_to_comment_seq: int | None,
                   depth: int, comment_content: str) -> int:
    cursor.execute(
        "SELECT COALESCE(MAX(comment_seq), 0) + 1 AS next_seq FROM board_a_write WHERE bulletin_seq = %s",
        (bulletin_seq,),
    )
    comment_seq = cursor.fetchone()["next_seq"]
    cursor.execute(
        """INSERT INTO board_a_write
            (bulletin_seq, comment_seq, c_id_seq, reply_to_comment_seq, depth, comment_content, comment_delete_state)
           VALUES (%s, %s, %s, %s, %s, %s, 0)""",
        (bulletin_seq, comment_seq, c_id_seq, reply_to_comment_seq, depth, comment_content),
    )
    return comment_seq


# 날짜(DATE) + 시간(TIME) → datetime (team_match.team_start / team_end 저장용)
# DB TIME은 pymysql이 timedelta로 주므로 날짜 0시에 더해서 계산 (24:00 종료도 다음날 0시로 계산됨)
def to_datetime(day: date, value) -> datetime:
    if isinstance(value, timedelta):
        return datetime.combine(day, time.min) + value
    hour, minute = str(value)[:5].split(":")
    return datetime.combine(day, time.min) + timedelta(hours=int(hour), minutes=int(minute))


# 신청 댓글에 달린 대댓글(depth 1)로 신청 상태 판단
def request_status(cursor, bulletin_seq: int, comment_seq: int) -> str:
    cursor.execute(
        """SELECT comment_content FROM board_a_write
            WHERE bulletin_seq = %s AND reply_to_comment_seq = %s AND depth = 1 AND comment_delete_state = 0
            ORDER BY comment_seq
            LIMIT 1""",
        (bulletin_seq, comment_seq),
    )
    reply = cursor.fetchone()
    if reply is None:
        return STATUS_REQUESTED
    return STATUS_ACCEPTED if (reply["comment_content"] or "").endswith(ACCEPT_SUFFIX) else STATUS_REJECTED


# 회원이 게시글에 남긴 가장 최근 신청 댓글 (depth 0) 조회
def find_last_request(cursor, bulletin_seq: int, c_id_seq: str) -> dict | None:
    cursor.execute(
        """SELECT comment_seq FROM board_a_write
            WHERE bulletin_seq = %s AND c_id_seq = %s AND comment_seq > %s AND depth = 0
                AND comment_delete_state = 0
            ORDER BY comment_seq DESC
            LIMIT 1""",
        (bulletin_seq, c_id_seq, POST_COMMENT_SEQ),
    )
    return cursor.fetchone()


# 연결된 구장대여가 아직 매칭 가능한지 (취소 안 됨 · 성사 전 · 오늘 이후)
def is_rental_open(cursor, post: dict) -> bool:
    cursor.execute(
        f"SELECT 1 FROM reservation WHERE r_seq = %s AND {category_condition(False)}", (post["r_seq"],)
    )
    return cursor.fetchone() is not None and not bool(post["r_check"]) and post["r_date"] >= date.today()


# 팀 정보(dict) → 응답에 넣을 값 (팀장이 아니거나 팀이 없으면 None)
def team_to_dict(team: dict | None) -> dict:
    return {
        "t_id": team["t_id"] if team else None,           # 팀 ID
        "t_name": team["t_name"] if team else None,       # 팀명
        "t_logo": team["t_logo"] if team else None,       # 팀 로고
        "t_rating": team["t_rating"] if team else None,   # 팀 Elo 점수 (팀 레벨 표시용, 기본 1500)
    }


# 매칭신청 게시글 1줄(dict) → 앱으로 보낼 JSON(dict)으로 정리
def post_to_dict(row: dict, team: dict | None) -> dict:
    content = row["board_content"] or ""
    return {
        "bulletin_seq": row["bulletin_seq"],          # 게시글 번호
        "c_id_seq": row["c_id_seq"],                  # 작성자 (게시글 팀 팀장)
        **team_to_dict(team),                         # 게시글 팀 (리스트의 "성산 FC 레드" · 레벨)
        "event_category": row["event_category"],      # 종목
        "board_title": row["board_title"],            # 제목
        # 내용 (첫 줄의 [예약번호:..] 표시는 빼고 보냄)
        "board_content": POST_RESERVATION_PATTERN.sub("", content).lstrip("\n"),
        "board_date": row["board_date"],              # 작성일
        "r_seq": row["r_seq"],                        # 연결된 구장대여 예약번호
        "g_code": row["g_code"],                      # 구장코드
        "g_name": row["g_name"],                      # 구장명 (리스트의 "상암 보조구장")
        "g_address": row["g_address"],                # 구장 주소
        "g_num": row["g_num"],                        # 수용인원 (경기 형식 표시용)
        "r_date": row["r_date"],                      # 경기일
        "rs_time": format_time(row["rs_time"]),       # 시작 시간
        "re_time": format_time(row["re_time"]),       # 종료 시간
        "is_matched": bool(row["r_check"]),           # 이미 매칭 성사된 게시글인지
    }


# 매칭신청 글을 쓸 수 있는 팀장의 구장대여 내역
# 조건 : 본인 구장대여(reservation_category = 2), 취소되지 않음, 아직 매칭 성사 전(r_check = 0), 오늘 이후
#        이미 매칭신청 글을 쓴 대여는 has_post = true 로 표시 (같은 대여로 글 중복 작성 방지)
# 예: /team_match/rentals/hong_01
@router.get("/rentals/{c_id_seq}")
def select_team_match_rentals(c_id_seq: str):
    connection = None
    try:
        connection = connect()  # DB 연결
        with connection.cursor() as cursor:  # SQL을 실행할 커서 (with가 끝나면 자동으로 닫힘)
            cursor.execute(
                f"""SELECT r.r_seq, r.g_code, g.g_name, g.g_num, r.r_date, r.rs_time, r.re_time
                    FROM reservation AS r
                    INNER JOIN ground AS g ON g.g_code = r.g_code
                    WHERE r.c_id_seq = %s AND {reservation_type_condition(RESERVATION_RENTAL, 'r')}
                        AND {category_condition(False, 'r')} AND r.r_check = 0 AND r.r_date >= CURDATE()
                    ORDER BY r.r_date, r.rs_time""",
                (c_id_seq,),
            )
            rentals = cursor.fetchall()

            # 이미 매칭신청 글을 쓴 예약번호 목록 (게시글 행만)
            cursor.execute(
                f"""SELECT {POST_RESERVATION_SEQ_SQL} AS r_seq FROM board_a_write AS b
                    WHERE b.comment_seq = {POST_COMMENT_SEQ} AND b.c_id_seq = %s
                        AND b.board_category = %s AND b.board_content LIKE %s""",
                (c_id_seq, BOARD_CATEGORY_TEAM_MATCH, "[예약번호:%"),
            )
            posted = {row["r_seq"] for row in cursor.fetchall()}
        return {
            "results": [
                {
                    "r_seq": row["r_seq"],                    # 구장대여 예약번호
                    "g_code": row["g_code"],                  # 구장코드
                    "g_name": row["g_name"],                  # 구장명
                    "g_num": row["g_num"],                    # 수용인원
                    "r_date": row["r_date"],                  # 경기일
                    "rs_time": format_time(row["rs_time"]),   # 시작 시간
                    "re_time": format_time(row["re_time"]),   # 종료 시간
                    "has_post": row["r_seq"] in posted,       # 이미 매칭신청 글을 썼는지
                }
                for row in rentals
            ]
        }
    except pymysql.MySQLError:
        logger.exception("팀매칭 구장대여 내역 DB 조회 실패")
        raise HTTPException(status_code=500, detail="구장대여 내역 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀매칭 구장대여 내역 조회 실패")
        raise HTTPException(status_code=500, detail="구장대여 내역 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()  # 성공/실패 상관없이 DB 연결 종료


# 구장대여 내역으로 [매칭신청] 게시글 작성 (선택 사항)
# 게시글 행(comment_seq = 0)으로 저장, 제목은 구장·일시로 자동 작성
# 내용 첫 줄에 [예약번호:r_seq]를 넣어 대여 예약과 연결
@router.post(
    "/post",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "팀장이 아니거나 본인 구장대여가 아님"},
        404: {"description": "구장대여 예약이 존재하지 않음"},
        409: {"description": "취소·성사·지난 대여이거나 이미 매칭신청 글을 쓴 대여"},
    },
)
def create_team_match_post(
    c_id_seq: Annotated[str, Body(min_length=4, max_length=50, description="글을 쓰는 회원 (팀장)")],
    r_seq: Annotated[int, Body(gt=0, description="연결할 구장대여 예약번호")],
    board_content: Annotated[Optional[str], Body(max_length=1000, description="추가로 적을 내용 (선택)")] = None,
):
    c_id_seq = c_id_seq.strip()  # 앞뒤 공백 제거
    sport_name = sport_from_customer_id(c_id_seq)  # c_id_seq 끝 번호로 종목 확인 (형식이 틀리면 400)
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 1) 팀장인지 확인
            team = find_captain_team(cursor, c_id_seq)
            if team is None:
                raise HTTPException(status_code=403, detail="팀장만 매칭신청 글을 쓸 수 있습니다.")

            # 2) 구장대여 예약 확인 (본인 · 구장대여 · 취소 안 됨 · 성사 전 · 오늘 이후)
            cursor.execute(
                f"""SELECT r.r_seq, r.c_id_seq, r.r_date, r.rs_time, r.re_time, r.r_check, g.g_name
                    FROM reservation AS r
                    INNER JOIN ground AS g ON g.g_code = r.g_code
                    WHERE r.r_seq = %s AND {reservation_type_condition(RESERVATION_RENTAL, 'r')}""",
                (r_seq,),
            )
            rental = cursor.fetchone()
            if rental is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 구장대여 예약입니다.")
            if rental["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 구장대여로만 매칭신청 글을 쓸 수 있습니다.")
            if not is_rental_open(cursor, rental):
                raise HTTPException(status_code=409, detail="취소·성사되었거나 지난 구장대여입니다.")

            # 3) 같은 대여로 이미 쓴 매칭신청 글이 있는지 확인 (게시글 행만)
            mark = POST_RESERVATION_MARK.format(r_seq=r_seq)
            cursor.execute(
                """SELECT 1 FROM board_a_write
                    WHERE comment_seq = %s AND board_category = %s AND board_content LIKE %s
                    LIMIT 1""",
                (POST_COMMENT_SEQ, BOARD_CATEGORY_TEAM_MATCH, mark + "%"),
            )
            if cursor.fetchone() is not None:
                raise HTTPException(status_code=409, detail="이미 매칭신청 글을 쓴 구장대여입니다.")

            # 4) 게시글 행 저장 (comment_seq = 0, bulletin_seq는 AUTO_INCREMENT)
            # 제목 예: [매칭신청] 상암 보조구장 10/26 20:00
            title = (f"[{BOARD_CATEGORY_TEAM_MATCH}] {rental['g_name']} "
                     f"{rental['r_date'].month}/{rental['r_date'].day} {format_time(rental['rs_time'])}")
            content = mark if not (board_content and board_content.strip()) else f"{mark}\n{board_content.strip()}"
            cursor.execute(
                """INSERT INTO board_a_write
                    (comment_seq, c_id_seq, event_category, board_category, board_title, board_content)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (POST_COMMENT_SEQ, c_id_seq, sport_name, BOARD_CATEGORY_TEAM_MATCH, title, content),
            )
            bulletin_seq = cursor.lastrowid  # 방금 저장된 게시글 번호 (AUTO_INCREMENT)
        connection.commit()
        return {
            "result": "OK",
            "bulletin_seq": bulletin_seq,   # 게시글 번호
            "t_name": team["t_name"],       # 게시글 팀명
            "board_title": title,           # 자동 작성된 제목
            "r_seq": r_seq,                 # 연결된 구장대여 예약번호
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()  # 위에서 만든 403/404/409는 되돌린 뒤 그대로 전달
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()
        logger.exception("매칭신청 게시글 DB 저장 실패")
        raise HTTPException(status_code=500, detail="매칭신청 글 저장 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("매칭신청 게시글 저장 실패")
        raise HTTPException(status_code=500, detail="매칭신청 글 저장에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 상대 팀 선택 리스트 (첫 화면의 "상대 팀 선택")
# 조건 : 같은 종목, 내 팀이 아닌 게시글, 연결된 구장대여가 취소·성사 전이고 오늘 이후
# 게시글마다 내 팀의 신청 상태(status)를 함께 보냄 → 앱에서 "요청됨" / "글 보기" 표시
# 예: /team_match/posts?c_id_seq=hong_01
@router.get("/posts")
def select_team_match_posts(
    c_id_seq: str = Query(min_length=4, max_length=50, description="리스트를 보는 회원 (팀장)"),
):
    c_id_seq = c_id_seq.strip()
    sport_name = sport_from_customer_id(c_id_seq)  # 같은 종목 게시글만 보여주기 위해 종목 확인
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            my_team = find_captain_team(cursor, c_id_seq)  # 내 팀 (팀장이 아니면 None → 신청 불가)

            sql = POST_SELECT + f"""
                AND b.event_category = %s AND b.c_id_seq <> %s
                AND {category_condition(False, 'r')} AND r.r_check = 0 AND r.r_date >= CURDATE()
                ORDER BY r.r_date, r.rs_time, b.bulletin_seq
            """
            cursor.execute(sql, (BOARD_CATEGORY_TEAM_MATCH, "[예약번호:%", sport_name, c_id_seq))
            rows = cursor.fetchall()

            results = []
            for row in rows:
                post_team = find_captain_team(cursor, row["c_id_seq"])
                # 같은 팀 게시글은 리스트에서 제외 (팀장이 바뀐 경우 대비)
                if my_team and post_team and post_team["t_id"] == my_team["t_id"]:
                    continue
                item = post_to_dict(row, post_team)
                # 내가 이 게시글에 남긴 가장 최근 신청 댓글로 상태 판단
                my_request = find_last_request(cursor, row["bulletin_seq"], c_id_seq)
                item["request_comment_seq"] = my_request["comment_seq"] if my_request else None
                item["status"] = (request_status(cursor, row["bulletin_seq"], my_request["comment_seq"])
                                  if my_request else STATUS_NONE)
                results.append(item)
        return {
            "my_team": team_to_dict(my_team) if my_team else None,  # 내 팀 (화면 상단 왼쪽 팀, 팀장이 아니면 None)
            "can_request": my_team is not None,                     # 팀장만 신청 가능
            "results": results,
        }
    except HTTPException:
        raise
    except pymysql.MySQLError:
        logger.exception("팀매칭 리스트 DB 조회 실패")
        raise HTTPException(status_code=500, detail="팀매칭 리스트 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀매칭 리스트 조회 실패")
        raise HTTPException(status_code=500, detail="팀매칭 리스트 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 팀매칭 신청 (리스트에서 상대 팀을 선택하고 "매칭 요청 보냄")
# 게시글에 신청 팀 팀장 이름으로 댓글(depth 0) "OO 팀이 팀매칭을 신청하였습니다." 저장
@router.post(
    "/request",
    status_code=status.HTTP_201_CREATED,
    responses={
        403: {"description": "팀장이 아님"},
        404: {"description": "매칭신청 게시글이 존재하지 않음"},
        409: {"description": "내 팀 게시글 / 다른 종목 / 이미 신청 / 이미 성사·마감된 게시글"},
    },
)
def create_team_match_request(
    c_id_seq: Annotated[str, Body(min_length=4, max_length=50, description="신청하는 회원 (신청 팀 팀장)")],
    bulletin_seq: Annotated[int, Body(gt=0, description="신청할 매칭신청 게시글 번호")],
):
    c_id_seq = c_id_seq.strip()
    sport_name = sport_from_customer_id(c_id_seq)
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 1) 신청하는 회원이 팀장인지 확인
            my_team = find_captain_team(cursor, c_id_seq)
            if my_team is None:
                raise HTTPException(status_code=403, detail="팀장만 팀매칭을 신청할 수 있습니다.")

            # 2) 게시글 + 연결된 구장대여 조회
            # FOR UPDATE : 신청하는 동안 수락 처리·다른 댓글 번호 계산이 끼어들지 못하게 게시글 행 잠금
            cursor.execute(POST_SELECT + " AND b.bulletin_seq = %s FOR UPDATE",
                           (BOARD_CATEGORY_TEAM_MATCH, "[예약번호:%", bulletin_seq))
            post = cursor.fetchone()
            if post is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 매칭신청 게시글입니다.")

            # 3) 신청 가능한 게시글인지 확인
            post_team = find_captain_team(cursor, post["c_id_seq"])
            if post["c_id_seq"] == c_id_seq or (post_team and post_team["t_id"] == my_team["t_id"]):
                raise HTTPException(status_code=409, detail="내 팀 게시글에는 신청할 수 없습니다.")
            if post["event_category"] != sport_name:
                raise HTTPException(status_code=409, detail="같은 종목 게시글에만 신청할 수 있습니다.")
            if not is_rental_open(cursor, post):
                raise HTTPException(status_code=409, detail="이미 성사되었거나 마감된 팀매칭입니다.")

            # 4) 이미 신청했는지 확인 (요청됨 / 수락이면 막고, 거절된 신청은 다시 신청 가능)
            last_request = find_last_request(cursor, bulletin_seq, c_id_seq)
            if last_request and request_status(cursor, bulletin_seq, last_request["comment_seq"]) != STATUS_REJECTED:
                raise HTTPException(status_code=409, detail="이미 팀매칭을 신청한 게시글입니다.")

            # 5) 신청 댓글 저장 (depth 0, 신청 팀 팀장 이름)
            comment_seq = insert_comment(cursor, bulletin_seq, c_id_seq, None, 0,
                                         REQUEST_TEXT.format(team=my_team["t_name"]))
        connection.commit()
        return {
            "result": "OK",
            "bulletin_seq": bulletin_seq,
            "comment_seq": comment_seq,                  # 신청 댓글 번호 (수락/거절할 때 bulletin_seq와 함께 사용)
            "status": STATUS_REQUESTED,                  # 요청됨
            "request_team": my_team["t_name"],           # 신청한 팀
            "post_team": post_team["t_name"] if post_team else None,  # 신청받은 팀
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀매칭 신청 DB 처리 실패")
        raise HTTPException(status_code=500, detail="팀매칭 신청 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀매칭 신청 처리 실패")
        raise HTTPException(status_code=500, detail="팀매칭 신청에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 내 게시글에 들어온 신청 팀 목록 (신청받은 팀이 상대 팀 정보를 보고 대결 여부 판단)
# 게시글 작성자(게시글 팀 팀장)만 조회 가능
# 예: /team_match/requests/3?c_id_seq=hong_01
@router.get("/requests/{bulletin_seq}")
def select_team_match_requests(
    bulletin_seq: int,
    c_id_seq: str = Query(min_length=4, max_length=50, description="게시글 작성자 (본인 확인용)"),
):
    c_id_seq = c_id_seq.strip()
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 1) 게시글 + 연결된 구장대여 조회
            cursor.execute(POST_SELECT + " AND b.bulletin_seq = %s",
                           (BOARD_CATEGORY_TEAM_MATCH, "[예약번호:%", bulletin_seq))
            post = cursor.fetchone()
            if post is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 매칭신청 게시글입니다.")
            if post["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 게시글의 신청만 확인할 수 있습니다.")

            # 2) 신청 댓글(depth 0) 목록 + 신청 팀 정보
            # comment_seq > 0 : 댓글 행만 (게시글 행 제외)
            # 팀원 수 : t_register(팀 가입) 인원
            cursor.execute(
                """SELECT w.comment_seq, w.c_id_seq, w.comment_content, cu.c_name
                    FROM board_a_write AS w
                    LEFT JOIN customer AS cu ON cu.c_id_seq = w.c_id_seq
                    WHERE w.bulletin_seq = %s AND w.comment_seq > %s AND w.depth = 0
                        AND w.comment_delete_state = 0
                    ORDER BY w.comment_seq""",
                (bulletin_seq, POST_COMMENT_SEQ),
            )
            comments = cursor.fetchall()

            requests = []
            for comment in comments:
                team = find_captain_team(cursor, comment["c_id_seq"])
                member_count = 0
                if team:
                    cursor.execute("SELECT COUNT(*) AS n FROM t_register WHERE t_id = %s", (team["t_id"],))
                    member_count = cursor.fetchone()["n"]
                requests.append({
                    "comment_seq": comment["comment_seq"],          # 신청 댓글 번호 (수락/거절할 때 사용)
                    "comment_content": comment["comment_content"],  # 신청 댓글 내용
                    "c_id_seq": comment["c_id_seq"],                # 신청한 팀장
                    "c_name": comment["c_name"],                    # 신청한 팀장 이름
                    **team_to_dict(team),                           # 신청 팀 (팀명 · 로고 · 팀 점수)
                    "member_count": member_count,                   # 신청 팀 팀원 수
                    "status": request_status(cursor, bulletin_seq, comment["comment_seq"]),  # 신청 상태
                })
            post_team = find_captain_team(cursor, post["c_id_seq"])  # 내 팀 (화면 상단 게시글 팀)
        return {"post": post_to_dict(post, post_team), "results": requests}
    except HTTPException:
        raise
    except pymysql.MySQLError:
        logger.exception("팀매칭 신청 목록 DB 조회 실패")
        raise HTTPException(status_code=500, detail="신청 목록 조회 중 DB 오류가 발생했습니다.")
    except Exception:
        logger.exception("팀매칭 신청 목록 조회 실패")
        raise HTTPException(status_code=500, detail="신청 목록 조회에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 신청 수락 / 거절 공통 처리
# 신청 댓글은 (bulletin_seq, comment_seq)로 찾음 (comment_seq는 게시글마다 1부터라 게시글 번호도 필요)
# 수락 : 대댓글(depth 1) 수락 + 2번째 대댓글(depth 2) 매칭 성사
#        + team_match에 경기 저장 (홈 = 게시글 팀, 원정 = 신청 팀, 인원 = 구장 수용인원, 시간 = 대여 시간)
#        + 연결된 구장대여 예약 r_check = 1 (팀매칭 성사 → 리스트에서 빠짐)
# 거절 : 대댓글(depth 1) 거절 (신청 팀은 다시 신청 가능)
def answer_team_match_request(c_id_seq: str, bulletin_seq: int, comment_seq: int, is_accepted: bool) -> dict:
    c_id_seq = c_id_seq.strip()
    connection = None
    try:
        connection = connect()
        with connection.cursor() as cursor:
            # 1) 게시글 + 연결된 구장대여 조회
            # FOR UPDATE : 동시에 두 팀을 수락하거나 댓글 번호가 겹치지 않게 게시글 행 잠금
            cursor.execute(POST_SELECT + " AND b.bulletin_seq = %s FOR UPDATE",
                           (BOARD_CATEGORY_TEAM_MATCH, "[예약번호:%", bulletin_seq))
            post = cursor.fetchone()
            if post is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 매칭신청 게시글입니다.")

            # 2) 신청 댓글 조회 (depth 0)
            cursor.execute(
                """SELECT comment_seq, c_id_seq FROM board_a_write
                    WHERE bulletin_seq = %s AND comment_seq = %s AND comment_seq > %s
                        AND depth = 0 AND comment_delete_state = 0""",
                (bulletin_seq, comment_seq, POST_COMMENT_SEQ),
            )
            request = cursor.fetchone()
            if request is None:
                raise HTTPException(status_code=404, detail="존재하지 않는 팀매칭 신청입니다.")

            # 3) 게시글 작성자(게시글 팀 팀장)만 판단 가능
            if post["c_id_seq"] != c_id_seq:
                raise HTTPException(status_code=403, detail="본인 게시글의 신청만 수락·거절할 수 있습니다.")

            # 4) 이미 수락/거절한 신청인지, 게시글이 이미 성사·마감됐는지 확인
            if request_status(cursor, bulletin_seq, comment_seq) != STATUS_REQUESTED:
                raise HTTPException(status_code=409, detail="이미 수락 또는 거절한 신청입니다.")
            if not is_rental_open(cursor, post):
                raise HTTPException(status_code=409, detail="이미 성사되었거나 마감된 팀매칭입니다.")

            post_team = find_captain_team(cursor, post["c_id_seq"])
            request_team = find_captain_team(cursor, request["c_id_seq"])
            if post_team is None or request_team is None:
                raise HTTPException(status_code=409, detail="팀 정보를 확인할 수 없는 신청입니다.")

            # 5) 대댓글(depth 1) 저장 : 수락 / 거절 (reply_to = 신청 댓글)
            text = ACCEPT_TEXT if is_accepted else REJECT_TEXT
            reply_seq = insert_comment(cursor, bulletin_seq, c_id_seq, comment_seq, 1,
                                       text.format(team=request_team["t_name"]))
            team_code = None

            if is_accepted:
                # 6) 2번째 대댓글(depth 2) 저장 : 매칭 성사 (reply_to = 수락 대댓글)
                insert_comment(cursor, bulletin_seq, c_id_seq, reply_seq, 2,
                               SUCCESS_TEXT.format(request_team=request_team["t_name"],
                                                   post_team=post_team["t_name"]))

                # 7) team_match에 경기 저장 (홈 = 게시글 팀, 원정 = 신청 팀)
                cursor.execute(
                    """INSERT INTO team_match (home_t_id, away_t_id, team_num, team_start, team_end)
                       VALUES (%s, %s, %s, %s, %s)""",
                    (post_team["t_id"], request_team["t_id"], post["g_num"],
                     to_datetime(post["r_date"], post["rs_time"]), to_datetime(post["r_date"], post["re_time"])),
                )
                team_code = cursor.lastrowid  # 팀 매치 코드

                # 8) 구장대여 예약 r_check = 1 (팀매칭 성사)
                cursor.execute("UPDATE reservation SET r_check = 1 WHERE r_seq = %s", (post["r_seq"],))
        connection.commit()  # 댓글 + 팀 매치 + 예약 상태를 한 번에 확정
        return {
            "result": "OK",
            "bulletin_seq": bulletin_seq,
            "comment_seq": comment_seq,                                   # 처리한 신청 댓글 번호
            "status": STATUS_ACCEPTED if is_accepted else STATUS_REJECTED,
            "team_code": team_code,                                       # 성사된 팀 매치 코드 (거절이면 None)
            "home_team": post_team["t_name"],                             # 게시글 팀
            "away_team": request_team["t_name"],                          # 신청 팀
        }
    except HTTPException:
        if connection is not None:
            connection.rollback()
        raise
    except pymysql.MySQLError:
        if connection is not None:
            connection.rollback()
        logger.exception("팀매칭 수락·거절 DB 처리 실패")
        raise HTTPException(status_code=500, detail="팀매칭 처리 중 DB 오류가 발생했습니다.")
    except Exception:
        if connection is not None:
            connection.rollback()
        logger.exception("팀매칭 수락·거절 처리 실패")
        raise HTTPException(status_code=500, detail="팀매칭 처리에 실패했습니다.")
    finally:
        if connection is not None:
            connection.close()


# 신청 수락 → 팀 매칭 성사
@router.post(
    "/accept",
    responses={
        403: {"description": "게시글 작성자가 아님"},
        404: {"description": "신청 또는 게시글이 존재하지 않음"},
        409: {"description": "이미 수락·거절한 신청 또는 이미 성사·마감된 게시글"},
    },
)
def accept_team_match_request(
    c_id_seq: Annotated[str, Body(min_length=4, max_length=50, description="게시글 작성자 (게시글 팀 팀장)")],
    bulletin_seq: Annotated[int, Body(gt=0, description="매칭신청 게시글 번호")],
    comment_seq: Annotated[int, Body(gt=0, description="수락할 신청 댓글 번호")],
):
    return answer_team_match_request(c_id_seq, bulletin_seq, comment_seq, True)


# 신청 거절
@router.post(
    "/reject",
    responses={
        403: {"description": "게시글 작성자가 아님"},
        404: {"description": "신청 또는 게시글이 존재하지 않음"},
        409: {"description": "이미 수락·거절한 신청 또는 이미 성사·마감된 게시글"},
    },
)
def reject_team_match_request(
    c_id_seq: Annotated[str, Body(min_length=4, max_length=50, description="게시글 작성자 (게시글 팀 팀장)")],
    bulletin_seq: Annotated[int, Body(gt=0, description="매칭신청 게시글 번호")],
    comment_seq: Annotated[int, Body(gt=0, description="거절할 신청 댓글 번호")],
):
    return answer_team_match_request(c_id_seq, bulletin_seq, comment_seq, False)

# 최종 수정 일 : 2026-10-26
