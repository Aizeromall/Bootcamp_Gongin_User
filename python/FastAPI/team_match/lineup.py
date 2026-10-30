# 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
"""기존 예약·게시글에 출전 선택을 연결합니다. 테이블·컬럼 추가 없이 예약 PK를 보존합니다."""
import json
import re

from fastapi import HTTPException

from ..team_create.apply_team import active_registration

MARK = re.compile(r"\n\[출전예약:([0-9,]*)\]\n\[출전정보:(\{[^\n]*\})\]\Z")


def unpack(text):
    match = MARK.search(text or "")
    if not match:
        return None
    try:
        data = json.loads(match[2])
        data["reservations"] = [int(value) for value in match[1].split(",") if value]
        return data
    except (ValueError, TypeError, AttributeError):
        raise HTTPException(409, "출전 명단 연결 정보를 확인해 주세요.") from None


def visible(text):
    return MARK.sub("", text or "")


def pack(text, data):
    ids = ",".join(str(value) for value in data["reservations"])
    info = json.dumps({k: v for k, v in data.items() if k != "reservations"}, ensure_ascii=False)
    return visible(text) + f"\n[출전예약:{ids}]\n[출전정보:{info}]"


def participant_condition(alias="r"):
    # 예약번호 목록의 정확한 항목으로만 판별합니다. 시간대 전체를 DELETE하지 않습니다.
    return f"""EXISTS (SELECT 1 FROM board_a_write lineup_board
        JOIN board_a_write lineup_post ON lineup_post.bulletin_seq=lineup_board.bulletin_seq
            AND lineup_post.comment_seq=0 AND lineup_post.board_category='매칭신청'
        WHERE (LOCATE('[출전예약:',lineup_board.board_content)>0 OR LOCATE('[출전예약:',lineup_board.comment_content)>0)
        AND {alias}.r_seq <> CAST(SUBSTRING_INDEX(SUBSTRING_INDEX(lineup_post.board_content, ']', 1), ':', -1) AS UNSIGNED)
        AND FIND_IN_SET(CONVERT(CAST({alias}.r_seq AS CHAR) USING ascii), CONVERT(SUBSTRING_INDEX(SUBSTRING_INDEX(
            COALESCE(NULLIF(lineup_board.board_content,''),lineup_board.comment_content), '[출전예약:', -1), ']', 1) USING ascii)) > 0)"""


def guard_participant(cursor, r_seq):
    cursor.execute(f"SELECT 1 FROM reservation r WHERE r.r_seq=%s AND {participant_condition()} LIMIT 1", (r_seq,))
    if cursor.fetchone():
        raise HTTPException(409, "팀 출전자 예약은 별도로 결제·취소할 수 없습니다. 팀 매칭에서 처리해 주세요.")


def team_members(cursor, team_id):
    cursor.execute(f"""SELECT DISTINCT c.c_id_seq,c.c_name,c.c_position FROM t_register tr
        JOIN customer c ON c.c_id_seq=tr.c_id_seq
        WHERE tr.t_id=%s AND {active_registration('tr')} AND c.c_deletdate IS NULL
        ORDER BY c.c_id_seq""", (team_id,))
    return list(cursor.fetchall())


def required_count(capacity):
    if type(capacity) is not int or capacity <= 0 or capacity % 2:
        raise HTTPException(409, "구장 정원은 양 팀으로 나눌 수 있는 양의 짝수여야 합니다.")
    return capacity // 2


def validate(cursor, team_id, members, capacity):
    count = required_count(capacity)
    if (not isinstance(members, list) or len(members) != count
            or any(not isinstance(member, str) for member in members)
            or len(set(members)) != count):
        raise HTTPException(422, f"중복 없이 출전 팀원 {count}명을 정확히 선택해 주세요.")
    available = {row["c_id_seq"] for row in team_members(cursor, team_id)}
    if not set(members) <= available:
        raise HTTPException(409, "현재 승인된 소속 팀원만 출전할 수 있습니다. 명단을 다시 확인해 주세요.")


def store(cursor, rental, team_id, members, *, use_anchor=False):
    count = required_count(rental['g_num'])
    if (not isinstance(members, list) or len(members) != count
            or any(not isinstance(m, str) for m in members) or len(set(members)) != count):
        raise HTTPException(422, f'중복 없이 출전 팀원 {count}명을 정확히 선택해 주세요.')
    # 서로 다른 공고의 동시 신청도 동일 회원 잠금으로 직렬화합니다.
    cursor.execute('SELECT c_id_seq FROM customer WHERE c_id_seq IN ('
                   + ','.join(['%s'] * len(members)) + ') ORDER BY c_id_seq FOR UPDATE', tuple(sorted(members)))
    validate(cursor, team_id, members, rental["g_num"])
    ids = []
    for member in sorted(members):
        # 같은 회원의 겹치는 예약은 분류와 관계없이 차단하고 현재 대표 예약만 제외합니다.
        cursor.execute("""SELECT r_seq FROM reservation WHERE c_id_seq=%s AND r_date=%s
            AND rs_time<%s AND re_time>%s AND r_category<>'2' AND COALESCE(r_c_category,'') IN ('','0')
            AND r_seq<>%s FOR UPDATE""",
            (member, rental["r_date"], rental["re_time"], rental["rs_time"], rental["r_seq"]))
        if cursor.fetchone():
            raise HTTPException(409, "선택한 팀원에게 겹치는 예약 또는 대기 중인 신청이 있습니다.")
        if use_anchor and member == rental['c_id_seq']:
            # 대표 대여자도 출전하면 기존 예약을 재사용하고 결제 권한을 보존합니다.
            ids.append(rental['r_seq'])
            continue
        cursor.execute("""INSERT INTO reservation
            (c_id_seq,g_code,r_date,rs_time,re_time,r_check,reservation_category,r_category,r_c_category)
            VALUES (%s,%s,%s,%s,%s,0,'2','1','')""",
            (member, rental["g_code"], rental["r_date"], rental["rs_time"], rental["re_time"]))
        if not isinstance(cursor.lastrowid, int) or cursor.lastrowid <= 0:
            raise RuntimeError('출전자 예약번호를 확인할 수 없습니다.')
        ids.append(cursor.lastrowid)
    return {"team_id": team_id, "members": members, "reservations": ids}


def rows_for(cursor, rental, data):
    if not data or not data.get("reservations") or len(data["reservations"]) != len(data.get("members", [])):
        raise HTTPException(409, "출전 명단을 등록하지 않은 기존 공고·신청입니다. 명단을 먼저 등록해 주세요.")
    ids = data["reservations"]
    cursor.execute("SELECT r_seq,c_id_seq,r_check FROM reservation WHERE r_seq IN ("
                   + ",".join(["%s"] * len(ids)) + ") AND g_code=%s AND r_date=%s AND rs_time=%s AND re_time=%s "
                   "AND reservation_category='2' AND r_category='1' AND r_c_category IN ('','0') FOR UPDATE",
                   (*ids, rental["g_code"], rental["r_date"], rental["rs_time"], rental["re_time"]))
    rows = cursor.fetchall()
    if len(rows) != len(ids) or {r["c_id_seq"] for r in rows} != set(data["members"]):
        raise HTTPException(409, "출전 예약이 변경되었습니다. 명단을 다시 확인해 주세요.")
    return rows


def discard(cursor, rental, data):
    if not data:
        return
    for row in rows_for(cursor, rental, data):
        # 대표 대여 행·성사 행·결제/참조 이력은 임의 삭제하지 않습니다. FK 충돌 시 전체 롤백됩니다.
        if row["r_seq"] == rental["r_seq"]:
            continue
        if row["r_check"]:
            raise HTTPException(409, "이미 성사된 출전 예약은 삭제할 수 없습니다.")
        cursor.execute("DELETE FROM reservation WHERE r_seq=%s AND r_check=0", (row["r_seq"],))


def confirm(cursor, rental, home, away):
    for index, data in enumerate((home, away)):
        validate(cursor, data["team_id"], data["members"], rental["g_num"])
        if any(row['r_check'] or (index == 1 and row['r_seq'] == rental['r_seq'])
               for row in rows_for(cursor, rental, data)):
            raise HTTPException(409, '대기 중인 출전 예약만 확정할 수 있습니다.')
    if home["team_id"] == away["team_id"] or set(home["members"]) & set(away["members"]):
        raise HTTPException(409, "같은 팀 또는 중복 출전자는 매칭할 수 없습니다.")
    for seq in dict.fromkeys([rental["r_seq"], *home["reservations"], *away["reservations"]]):
        cursor.execute("UPDATE reservation SET r_check=1 WHERE r_seq=%s", (seq,))


def cancel_pending(cursor, rental):
    # 대표 대여 취소 시 아직 응답하지 않은 신청과 공고 팀의 출전 예약만 함께 제거합니다.
    cursor.execute("""SELECT b.bulletin_seq,b.comment_seq,b.board_content,b.comment_content FROM board_a_write b
        WHERE b.bulletin_seq IN (SELECT p.bulletin_seq FROM board_a_write p
          WHERE p.comment_seq=0 AND p.board_content LIKE %s)
        AND (b.comment_seq=0 OR (b.depth=0 AND NOT EXISTS
          (SELECT 1 FROM board_a_write a WHERE a.bulletin_seq=b.bulletin_seq
           AND a.reply_to_comment_seq=b.comment_seq AND a.depth=1 AND a.comment_delete_state=0)))""",
        (f"[예약번호:{rental['r_seq']}]%",))
    for row in list(cursor.fetchall()):
        data = unpack(row.get('board_content') or row.get('comment_content'))
        if data:
            discard(cursor, rental, data)
            column = 'board_content' if row['comment_seq'] == 0 else 'comment_content'
            cursor.execute(f'UPDATE board_a_write SET {column}=%s WHERE bulletin_seq=%s AND comment_seq=%s',
                           (visible(row[column]), row['bulletin_seq'], row['comment_seq']))

# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
