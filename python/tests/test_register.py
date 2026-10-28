"""회원가입 API 모의 DB 검증. 작업자 : 양태건 / 최종 수정일 : 2026-10-26."""
import unittest
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.auth import register


class RegisterTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(register.router, prefix="/auth")
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.fetchone.return_value = None
        connect = patch.object(register, "connect", return_value=self.connection)
        self.connect = connect.start()
        self.addCleanup(connect.stop)
        # 해싱 자체는 변경 대상이 아니므로 DB 저장 매핑에 집중합니다.
        password = patch.object(register, "hash_password", return_value="hashed")
        password.start()
        self.addCleanup(password.stop)
        self.payload = {
            "c_id": "member", "c_pw": "password123", "c_name": "회원",
            "c_address": "서울", "c_phone": "01012345678", "c_gender": "남성",
            "c_birthday": "2000-01-01", "c_team": "무소속",
            "preferred_stocks": [4, 2, 1, 3],
            "c_position": {"1": "FW", "2": "가드", "3": "투수", "4": "세터"},
        }

    def test_four_sports_create_four_rows_with_individual_positions(self):
        response = self.client.post("/auth/register", json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["created_customer_ids"],
                         ["member_01", "member_02", "member_03", "member_04"])
        rows = self.cursor.executemany.call_args.args[1]
        self.assertEqual([(r[0], r[1], r[8], r[9]) for r in rows], [
            ("member_01", 1, "무소속", "FW"), ("member_02", 2, "무소속", "가드"),
            ("member_03", 3, "무소속", "투수"), ("member_04", 4, "무소속", "세터"),
        ])
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_called_once()

    def test_baseball_only_keeps_fixed_sport_sequence(self):
        self.payload.update(preferred_stocks=[3], c_position={"3": "외야수"})
        response = self.client.post("/auth/register", json=self.payload)
        self.assertEqual(response.status_code, 201)
        rows = self.cursor.executemany.call_args.args[1]
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0][0], rows[0][1], rows[0][9]),
                         ("member_03", 3, "외야수"))

    def test_invalid_positions_rejected_before_db_connection(self):
        for positions in [{"1": "FW"}, {"1": "투수", "2": "가드", "3": "투수", "4": "세터"},
                          {"5": "FW"}, "축구: FW", {}, {"1": ""}]:
            with self.subTest(positions=positions):
                self.payload["c_position"] = positions
                self.assertEqual(self.client.post("/auth/register", json=self.payload).status_code, 422)
        self.connect.assert_not_called()

    def test_invalid_sports_rejected_before_db_connection(self):
        for sports in [[], [1, 1], [5]]:
            with self.subTest(sports=sports):
                self.payload["preferred_stocks"] = sports
                self.assertEqual(self.client.post("/auth/register", json=self.payload).status_code, 422)
        self.connect.assert_not_called()

    def test_duplicate_id_rolls_back_without_inserts(self):
        self.cursor.fetchone.return_value = {"1": 1}
        self.assertEqual(self.client.post("/auth/register", json=self.payload).status_code, 409)
        self.cursor.executemany.assert_not_called()
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_insert_failure_rolls_back_all_sports(self):
        self.cursor.executemany.side_effect = pymysql.err.IntegrityError(1062, "duplicate")
        self.assertEqual(self.client.post("/auth/register", json=self.payload).status_code, 409)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    # 수정 일 : 2026-10-28 / 작업자 : 최현준 (실제 DB VARCHAR 길이 경계 회귀 검증)
    def test_db_length_boundaries_are_accepted(self):
        self.payload.update(c_phone="1" * 20, c_gender="성" * 10, c_team="팀" * 50)
        response = self.client.post("/auth/register", json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        rows = self.cursor.executemany.call_args.args[1]
        self.assertTrue(all(len(row[5]) == 20 and len(row[6]) == 10 and len(row[8]) == 50 for row in rows))

    def test_db_length_overflow_rejected_before_connection(self):
        for field, maximum in [("c_phone", 20), ("c_gender", 10), ("c_team", 50)]:
            with self.subTest(field=field):
                payload = {**self.payload, field: "가" * (maximum + 1)}
                response = self.client.post("/auth/register", json=payload)
                self.assertEqual(response.status_code, 422)
                self.assertIn(["body", field], [error["loc"] for error in response.json()["detail"]])
        self.connect.assert_not_called()

    def test_main_exposes_report_and_preserves_existing_routes(self):
        from python.FastAPI.main import app
        with TestClient(app) as client:
            spec = client.get("/openapi.json").json()
            for path in ["/report/insert", "/report/list", "/auth/register", "/auth/login",
                         "/notifications/events", "/chat/rooms", "/ground"]:
                self.assertIn(path, spec["paths"])
            self.assertEqual(client.post("/report/insert", json={}).status_code, 422)
            self.assertEqual(client.get("/report/list").status_code, 422)


if __name__ == "__main__":
    unittest.main()

# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
