# 2026-10-30
# 작업자 : 김병재

"""내 소속팀 조회 API 검증. DB는 mock이며 SELECT만 실행되는지 확인합니다."""
import os
import unittest
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.auth import token
from python.FastAPI.my_team import list_my_team, team_members
from python.FastAPI.my_team.my_team import router

TEST_KEY = "test-only-not-a-production-secret-12345678"


def team_row(c_id_seq, t_id, tr_state="승인", captain_id="captain_02"):
    return {"c_id_seq": c_id_seq, "tr_state": tr_state, "tr_date": "2026-10-29T10:00:00",
            "t_id": t_id, "t_name": f"팀{t_id}", "t_logo": None, "t_rating": 1500,
            "creator_id": captain_id, "c_date": "2026-10-28T10:00:00",
            "captain_id": captain_id, "captain_name": "팀장", "member_count": 3}


class MyTeamTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        env = patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY)
        env.start()
        self.addCleanup(env.stop)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        patcher = patch.object(list_my_team, "connect", return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)
        signed = token.issue_token("member", ["member_02", "member_01", "member_04"])["access_token"]
        self.headers = {"Authorization": "Bearer " + signed}

    # 수정 일 : 2026-10-30 / 작업자 : 김병재
    def test_returns_every_signed_sport_with_team_or_null(self):
        self.cursor.fetchall.return_value = [
            team_row("member_02", 7, captain_id="member_02"),
            team_row("member_04", 9, tr_state="대기"),
            team_row("member_04", 8, tr_state=""),  # tr_state가 빈 기존 가입 데이터도 소속으로 봅니다.
        ]
        response = self.client.get("/my_team", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        results = response.json()["results"]
        self.assertEqual([r["c_id_seq"] for r in results], ["member_01", "member_02", "member_04"])
        self.assertEqual([r["sport"] for r in results], [1, 2, 4])
        self.assertEqual(results[1]["sport_name"], "농구")
        self.assertIsNone(results[0]["team"])
        self.assertEqual(results[1]["team"]["t_id"], 7)
        self.assertTrue(results[1]["team"]["is_captain"])
        # 수정 일 : 2026-10-30 / 작업자 : 김병재 — 팀 점수로 계산한 등급을 함께 반환합니다.
        self.assertIsInstance(results[1]["team"]["tier"], str)
        self.assertEqual(results[2]["team"]["t_id"], 8)
        self.assertFalse(results[2]["team"]["is_captain"])
        self.assertEqual([p["t_id"] for p in results[2]["pending"]], [9])
        # 서명된 JWT의 회원 ID만 조회 조건으로 사용하고 DB는 변경하지 않습니다.
        sql, params = self.cursor.execute.call_args.args
        self.assertTrue(sql.strip().startswith("SELECT"))
        self.assertIn("<> '폐지일'", sql)
        self.assertEqual(params, (("member_01", "member_02", "member_04"),))
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_requires_login_token(self):
        self.assertEqual(self.client.get("/my_team").status_code, 401)
        self.assertEqual(self.client.get("/my_team", headers={"Authorization": "Bearer forged"}).status_code, 401)
        self.connect.assert_not_called()

    def test_database_failure_is_hidden(self):
        self.cursor.execute.side_effect = pymysql.MySQLError("secret detail")
        response = self.client.get("/my_team", headers=self.headers)
        self.assertEqual(response.status_code, 500)
        self.assertNotIn("secret", response.text)
        self.connection.close.assert_called_once()


# 수정 일 : 2026-10-30 / 작업자 : 김병재
# 팀원 목록 API: 팀원만 조회 가능하고 팀장이 맨 앞에 오는지 확인합니다.
class TeamMembersTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        env = patch.dict(os.environ, AUTH_TOKEN_SECRET=TEST_KEY)
        env.start()
        self.addCleanup(env.stop)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        patcher = patch.object(team_members, "connect", return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)
        signed = token.issue_token("member", ["member_01"])["access_token"]
        self.headers = {"Authorization": "Bearer " + signed}
        self.cursor.fetchone.return_value = {"captain_id": "captain_01", "c_category": "개설일"}

    def member(self, c_id_seq, name):
        return {"c_id_seq": c_id_seq, "c_name": name, "c_position": "FW", "c_rating": 1500,
                "tr_date": "2026-10-29T10:00:00"}

    def test_member_sees_list_with_captain_first(self):
        self.cursor.fetchall.return_value = [self.member("member_01", "나"), self.member("captain_01", "팀장")]
        response = self.client.get("/my_team/members/7", headers=self.headers)
        self.assertEqual(response.status_code, 200, response.text)
        rows = response.json()["results"]
        self.assertEqual([r["c_id_seq"] for r in rows], ["captain_01", "member_01"])
        self.assertTrue(rows[0]["is_captain"])
        self.assertTrue(rows[1]["is_me"])
        self.assertEqual(response.json()["total"], 2)
        for call in self.cursor.execute.call_args_list:
            self.assertTrue(call.args[0].strip().startswith("SELECT"))
        self.connection.commit.assert_not_called()

    def test_non_member_and_closed_team_are_rejected(self):
        self.cursor.fetchall.return_value = [self.member("captain_01", "팀장")]
        self.assertEqual(self.client.get("/my_team/members/7", headers=self.headers).status_code, 403)
        self.cursor.fetchone.return_value = {"captain_id": "captain_01", "c_category": "폐지일"}
        self.assertEqual(self.client.get("/my_team/members/7", headers=self.headers).status_code, 404)
        self.assertEqual(self.client.get("/my_team/members/7").status_code, 401)

# 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
