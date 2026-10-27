# 작업자 : 최현준
# 최초 작업 일 : 2026-10-27

"""실제 SQL 필터를 메모리 DB에 실행해 대상별 비공개 및 분류 조회를 검증합니다."""

import sqlite3
import unittest
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.announce import announce


@contextmanager
def notice_client():
    # 운영 DB에 쓰지 않고 사용자·매니저·본사·미지정 대상 데이터를 준비합니다.
    db = sqlite3.connect(":memory:", check_same_thread=False)
    db.row_factory = sqlite3.Row
    db.execute("CREATE TABLE announcement (a_seq INTEGER, a_classify TEXT, a_title TEXT, a_detail TEXT, a_date TEXT, a_target TEXT)")
    for seq, category, target in [(1, "공지", "사용자"), (2, "이벤트", "사용자"),
                                  (3, "운영", "매니저"), (4, "본사전용", "본사"),
                                  (5, None, "사용자"), (6, "비공개", None),
                                  (7, "공백대상", "사용자 ")]:
        db.execute("INSERT INTO announcement VALUES (?, ?, ?, ?, ?, ?)",
                   (seq, category, f"제목 {seq}", None, "2026-10-27 10:00:00", target))
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value

    def execute(sql, params):
        # MySQL 바인딩 및 바이너리 비교만 SQLite 문법으로 치환합니다.
        result = db.execute(sql.replace("%s", "?").replace("AS BINARY", "AS BLOB"), params)
        cursor.fetchall.return_value = [dict(row) for row in result.fetchall()]

    cursor.execute.side_effect = execute
    app = FastAPI()
    app.include_router(announce.router, prefix="/announce")
    try:
        with patch.object(announce, "connect", return_value=connection), TestClient(app) as client:
            yield client, connection
    finally:
        db.close()


def test_user_only_and_categories():
    with notice_client() as (client, connection):
        rows = client.get("/announce").json()["results"]
        assert [row["a_seq"] for row in rows] == [5, 2, 1]
        assert all(row["a_target"] == "사용자" for row in rows)
        assert client.get("/announce/categories").json() == {"results": ["공지", "이벤트"]}
        assert connection.close.call_count == 2


def test_category_filter_and_pagination():
    with notice_client() as (client, _):
        assert [row["a_seq"] for row in client.get("/announce", params={"a_classify": "이벤트"}).json()["results"]] == [2]
        assert client.get("/announce", params={"a_classify": "본사전용"}).json()["results"] == []
        assert client.get("/announce", params={"a_classify": "' OR 1=1 --"}).json()["results"] == []
        assert [row["a_seq"] for row in client.get("/announce", params={"limit": 1, "offset": 1}).json()["results"]] == [2]


def test_detail_visibility():
    with notice_client() as (client, _):
        assert client.get("/announce/1").status_code == 200
        # 번호를 알아도 매니저·본사·NULL·공백 대상은 조회할 수 없습니다.
        for seq in (3, 4, 6, 7, 999):
            response = client.get(f"/announce/{seq}")
            assert response.status_code == 404, response.text
            assert response.json() == {"detail": "조회할 수 있는 공지가 없습니다."}


def test_invalid_input():
    with notice_client() as (client, _):
        assert client.get("/announce", params={"a_classify": "  "}).status_code == 400
        for params in ({"limit": 0}, {"limit": 101}, {"offset": -1}, {"a_classify": "x" * 51}):
            assert client.get("/announce", params=params).status_code == 422
        assert client.get("/announce/0").status_code == 422


def test_empty_data_and_db_error():
    with notice_client() as (client, connection):
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.execute.side_effect = None
        cursor.fetchall.return_value = []
        assert client.get("/announce").json()["results"] == []
        assert client.get("/announce/categories").json() == {"results": []}
        cursor.execute.side_effect = pymysql.OperationalError(2003, "private diagnostic")
        response = client.get("/announce")
        assert response.status_code == 500
        assert "private diagnostic" not in response.text


def load_tests(loader, tests, pattern):
    # 테스트 전용 클래스를 만들지 않고 함수를 표준 unittest에 등록합니다.
    return unittest.TestSuite(unittest.FunctionTestCase(test) for test in (
        test_user_only_and_categories, test_category_filter_and_pagination,
        test_detail_visibility, test_invalid_input, test_empty_data_and_db_error,
    ))


if __name__ == "__main__":
    unittest.main()

# 최종 수정 일 : 2026-10-27
