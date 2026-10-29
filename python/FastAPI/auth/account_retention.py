# 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
"""30일 경과 종목 정리 도구. 기본 preview이며 운영 스케줄 등록·실행은 별도 승인 사항입니다.

실행: python3 -m python.FastAPI.auth.account_retention [--delete]
FK 이력이 하나라도 있으면 보존하고 blocked로 보고합니다. FK 비활성화/연쇄 이력 삭제는 하지 않습니다.
"""
import argparse
import json
from collections import defaultdict

from .account_lifecycle import GRACE, account_db, now_kst


def identifier(value: str) -> str:
    # information_schema의 식별자를 SQL 식별자로 인용합니다. 외부 입력 SQL은 받지 않습니다.
    return "`" + value.replace("`", "``") + "`"


def incoming_references(cursor) -> list:
    cursor.execute("""SELECT TABLE_SCHEMA,TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_COLUMN_NAME
                      FROM information_schema.KEY_COLUMN_USAGE
                      WHERE REFERENCED_TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME='customer'
                      ORDER BY TABLE_SCHEMA,TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION""")
    groups = defaultdict(list)
    for row in cursor.fetchall():
        groups[(row["TABLE_SCHEMA"], row["TABLE_NAME"], row["CONSTRAINT_NAME"])].append(row)
    return list(groups.items())


def blockers(cursor, member: str, references: list) -> list[str]:
    blocked = []
    for (schema, table, _), columns in references:
        condition = " AND ".join("child." + identifier(c["COLUMN_NAME"]) + "=parent."
                                 + identifier(c["REFERENCED_COLUMN_NAME"]) for c in columns)
        cursor.execute("SELECT 1 FROM " + identifier(schema) + "." + identifier(table)
                       + " child JOIN customer parent ON " + condition
                       + " WHERE parent.c_id_seq=%s LIMIT 1", (member,))
        if cursor.fetchone() is not None:
            blocked.append(table)
    return sorted(set(blocked))


def run_retention(delete: bool = False, limit: int = 100, after: str = "") -> dict:
    if not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    cutoff = now_kst() - GRACE
    report = {"mode": "delete" if delete else "preview", "eligible": [], "blocked": [], "deleted": [],
              "next_cursor": None}
    with account_db(write=delete) as connection, connection.cursor() as cursor:
        if not delete:
            cursor.execute("SET TRANSACTION READ ONLY")
            cursor.execute("START TRANSACTION READ ONLY")
        cursor.execute("SELECT c_id_seq FROM customer WHERE c_deletdate IS NOT NULL AND c_deletdate<=%s "
                       "AND c_id_seq>%s ORDER BY c_id_seq LIMIT %s" + (" FOR UPDATE" if delete else ""),
                       (cutoff, after, limit))
        candidates = list(cursor.fetchall())
        # blocked 행이 배치 앞부분을 계속 차지해 뒤의 정리 가능 행이 굶지 않도록 커서를 제공합니다.
        if len(candidates) == limit:
            report["next_cursor"] = candidates[-1]["c_id_seq"]
        references = incoming_references(cursor)
        for row in candidates:
            member = row["c_id_seq"]
            blocked = blockers(cursor, member, references)
            if blocked:
                report["blocked"].append({"c_id_seq": member, "tables": blocked})
                continue
            report["eligible"].append(member)
            if delete:
                # 조회·복구와 동일한 행 잠금으로 경계 경합을 막습니다. 동시 FK 추가는 DB 제약으로 차단합니다.
                cursor.execute("DELETE FROM customer WHERE c_id_seq=%s AND c_deletdate IS NOT NULL "
                               "AND c_deletdate<=%s", (member, cutoff))
                if cursor.rowcount == 1:
                    report["deleted"].append(member)
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delete", action="store_true", help="실제 DELETE (기본값은 읽기 전용 preview)")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--after", default="", help="직전 출력 next_cursor (없으면 첫 배치)")
    args = parser.parse_args()
    print(json.dumps(run_retention(args.delete, args.limit, args.after), ensure_ascii=False))

# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
