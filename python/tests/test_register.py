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


if __name__ == "__main__":
    unittest.main()
