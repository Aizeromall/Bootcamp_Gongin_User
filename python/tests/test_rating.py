# 작업자 : 신현진
# 최초 작업 일 : 2026-10-29

"""회원·팀 등급 점수 조회 API 검증. 실제 DB는 사용하지 않고 SELECT 호출만 확인합니다."""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.rating import rating_router, rating_search


class RatingTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(rating_router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        patcher = patch.object(rating_search, "connect", return_value=self.connection)
        patcher.start()
        self.addCleanup(patcher.stop)

    # 실행한 SQL이 모두 SELECT인지 확인 (점수는 조회만 함)
    def assert_select_only(self):
        for call in self.cursor.execute.call_args_list:
            self.assertTrue(call.args[0].lstrip().upper().startswith("SELECT"), call.args[0])
        self.connection.commit.assert_not_called()

    # 등급 구간 : 관리자 앱과 같은 경계값
    def test_tier_boundaries_match_admin(self):
        cases = [(1000, "루키 1"), (1299, "루키 1"), (1300, "루키 2"), (1400, "루키 3"),
                 (1500, "비기너 1"), (1699, "비기너 2"), (1700, "비기너 3"), (1800, "아마추어 1"),
                 (2200, "아마추어 5"), (2300, "세미프로 1"), (2799, "세미프로 5"), (2999, "세미프로 5"),
                 (3000, "프로"), (None, None)]
        for rating, tier in cases:
            with self.subTest(rating=rating):
                self.assertEqual(rating_search.rating_tier(rating), tier)
        self.assertEqual(rating_search.next_tier(1650), ("비기너 3", 50))
        self.assertEqual(rating_search.next_tier(1000), ("루키 2", 300))
        self.assertEqual(rating_search.next_tier(3100), (None, None))

    def test_tiers_list_is_continuous(self):
        tiers = self.client.get("/rating/tiers").json()["tiers"]
        self.assertEqual(tiers[0], {"tier": "루키 1", "min_rating": 1000, "max_rating": 1299})
        self.assertEqual(tiers[-1], {"tier": "프로", "min_rating": 3000, "max_rating": None})
        for lower, upper in zip(tiers, tiers[1:]):
            self.assertEqual(lower["max_rating"] + 1, upper["min_rating"])

    # 내 수준 통계 : 현재 점수·등급·다음 등급, 통계는 점수가 기록된 경기만
    def test_summary(self):
        self.cursor.fetchone.side_effect = [
            {"c_id_seq": "hong_01", "c_name": "홍길동", "c_rating": 1650},
            {"total_matches": 5, "rated_matches": 3, "best_rating": 1680,
             "lowest_rating": 1490, "average_rating": 1606.6667},
        ]
        self.cursor.fetchall.return_value = [{"rating_change": 24}, {"rating_change": -10}]
        response = self.client.get("/rating/summary/hong_01", params={"recent": 2})
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual((data["sport"], data["current_rating"], data["tier"]), ("축구", 1650, "비기너 2"))
        self.assertEqual((data["next_tier"], data["points_to_next_tier"]), ("비기너 3", 50))
        self.assertEqual((data["total_matches"], data["rated_matches"]), (5, 3))
        self.assertEqual((data["best_rating"], data["lowest_rating"], data["average_rating"]), (1680, 1490, 1607))
        self.assertEqual((data["recent_count"], data["recent_change_sum"]), (2, 14))
        # 최근 변동 쿼리에 회원 ID와 경기 수가 전달되고, NULL 점수는 제외되는지 확인
        recent_sql, recent_params = self.cursor.execute.call_args_list[-1].args
        self.assertIn("IS NOT NULL", recent_sql)
        self.assertEqual(recent_params, ("hong_01", 2))
        self.assert_select_only()

    def test_summary_without_records(self):
        self.cursor.fetchone.side_effect = [
            {"c_id_seq": "hong_04", "c_name": "홍길동", "c_rating": 1500},
            {"total_matches": 0, "rated_matches": None, "best_rating": None,
             "lowest_rating": None, "average_rating": None},
        ]
        self.cursor.fetchall.return_value = []
        data = self.client.get("/rating/summary/hong_04").json()
        self.assertEqual((data["sport"], data["tier"], data["rated_matches"]), ("배구", "비기너 1", 0))
        self.assertIsNone(data["best_rating"])
        self.assertIsNone(data["average_rating"])
        self.assertEqual(data["recent_change_sum"], 0)

    # 경기별 변동 : 경기 전 → 경기 후 점수와 변동(±)
    # 점수가 비어 있는 경기(이전 기록·결석)는 null 없이 기존 점수(직전 경기 후 점수, 없으면 1500)로 채우고 변동 0
    def test_history_fills_empty_ratings_with_existing_score(self):
        self.cursor.fetchone.return_value = {"c_id_seq": "hong_01", "c_name": "홍길동", "c_rating": 1514}
        base = dict(c_r_r_date=datetime(2026, 10, 29, 20), e_code="SOCCER", c_r_r_team="A팀",
                    c_r_r_score="3:2", c_r_r_code="1_20261029_200000", g_code=1, g_name="구장")
        self.cursor.fetchall.return_value = [   # 오래된 순으로 조회됨
            dict(base, c_r_r_seq=1, c_r_r_attendance=None, c_r_r_rating_before=None, c_r_r_rating_after=None),
            dict(base, c_r_r_seq=2, c_r_r_attendance=1, c_r_r_rating_before=1500, c_r_r_rating_after=1490),
            dict(base, c_r_r_seq=3, c_r_r_attendance=0, c_r_r_rating_before=None, c_r_r_rating_after=None),
            dict(base, c_r_r_seq=4, c_r_r_attendance=1, c_r_r_rating_before=1490, c_r_r_rating_after=1514),
        ]
        response = self.client.get("/rating/history/hong_01")
        self.assertEqual(response.status_code, 200, response.text)
        latest, absent, lost, old = response.json()["results"]   # 최신순
        self.assertEqual((latest["rating_before"], latest["rating_after"], latest["rating_change"]), (1490, 1514, 24))
        self.assertEqual(latest["tier_after"], "비기너 1")
        self.assertEqual((absent["rating_before"], absent["rating_after"], absent["rating_change"]), (1490, 1490, 0))
        self.assertFalse(absent["c_r_r_attendance"])
        self.assertEqual(lost["rating_change"], -10)
        self.assertEqual((old["rating_before"], old["rating_after"], old["rating_change"]), (1500, 1500, 0))
        for item in response.json()["results"]:
            self.assertNotIn("rating_note", item)
            self.assertIsNotNone(item["rating_change"])
        self.assertEqual(latest["sport"], "축구")
        self.assert_select_only()

    def test_history_limit_returns_latest_records(self):
        self.cursor.fetchone.return_value = {"c_id_seq": "hong_01", "c_name": "홍길동", "c_rating": 1520}
        base = dict(c_r_r_date=datetime(2026, 10, 29, 20), e_code="SOCCER", c_r_r_team="A팀", c_r_r_score="1:0",
                    c_r_r_code="1_20261029_200000", g_code=1, g_name="구장", c_r_r_attendance=1)
        self.cursor.fetchall.return_value = [
            dict(base, c_r_r_seq=1, c_r_r_rating_before=1500, c_r_r_rating_after=1510),
            dict(base, c_r_r_seq=2, c_r_r_rating_before=1510, c_r_r_rating_after=1520),
        ]
        results = self.client.get("/rating/history/hong_01", params={"limit": 1}).json()["results"]
        self.assertEqual([(r["c_r_r_seq"], r["rating_change"]) for r in results], [(2, 10)])

    # 팀 변동 : 직전 경기 후 점수와의 차이, 점수가 비어 있는 경기는 직전 점수 그대로(변동 0)
    def test_team_history_change_from_previous_record(self):
        self.cursor.fetchone.return_value = {"t_id": 3, "t_name": "FC 망원", "t_rating": 1540}
        base = dict(e_code="SOCCER", t_r_r_score="3", t_r_r_m_code="15", g_code=1, g_name="구장")
        self.cursor.fetchall.return_value = [   # 오래된 순으로 조회됨
            dict(base, t_r_r_seq=1, t_r_r_date=datetime(2026, 10, 1), t_r_r_rating_after=None),
            dict(base, t_r_r_seq=2, t_r_r_date=datetime(2026, 10, 10), t_r_r_rating_after=1520),
            dict(base, t_r_r_seq=3, t_r_r_date=datetime(2026, 10, 20), t_r_r_rating_after=1540),
        ]
        data = self.client.get("/rating/team/3").json()
        self.assertEqual((data["current_rating"], data["tier"]), (1540, "비기너 1"))
        latest, middle, first = data["results"]   # 최신순
        self.assertEqual((latest["rating_before"], latest["rating_after"], latest["rating_change"]), (1520, 1540, 20))
        self.assertEqual((middle["rating_before"], middle["rating_change"]), (1500, 20))
        self.assertEqual((first["rating_before"], first["rating_after"], first["rating_change"]), (1500, 1500, 0))
        self.assertNotIn("rating_note", first)
        self.assert_select_only()

    def test_team_first_match_uses_start_rating_and_limit(self):
        self.cursor.fetchone.return_value = {"t_id": 3, "t_name": "FC 망원", "t_rating": 1480}
        base = dict(e_code="SOCCER", t_r_r_score="1", t_r_r_m_code="M", g_code=1, g_name="구장")
        self.cursor.fetchall.return_value = [
            dict(base, t_r_r_seq=1, t_r_r_date=datetime(2026, 10, 1), t_r_r_rating_after=1480),
            dict(base, t_r_r_seq=2, t_r_r_date=datetime(2026, 10, 2), t_r_r_rating_after=1500),
        ]
        results = self.client.get("/rating/team/3", params={"limit": 1}).json()["results"]
        self.assertEqual(len(results), 1)
        self.assertEqual((results[0]["t_r_r_seq"], results[0]["rating_change"]), (2, 20))
        all_results = self.client.get("/rating/team/3").json()["results"]
        self.assertEqual(all_results[-1]["rating_change"], -20)   # 첫 경기 : 1480 - 1500

    # 오류 : 잘못된 회원 ID 형식 400 (DB 연결 전), 없는 회원·팀 404, 범위 밖 limit 422
    def test_errors(self):
        self.assertEqual(self.client.get("/rating/summary/hong").status_code, 400)
        self.assertEqual(self.client.get("/rating/history/hong_05").status_code, 400)
        self.connection.cursor.assert_not_called()
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.get("/rating/summary/none_01").status_code, 404)
        self.assertEqual(self.client.get("/rating/history/none_01").status_code, 404)
        self.assertEqual(self.client.get("/rating/team/999").status_code, 404)
        self.assertEqual(self.client.get("/rating/history/hong_01", params={"limit": 0}).status_code, 422)
        self.assertEqual(self.client.get("/rating/summary/hong_01", params={"recent": 51}).status_code, 422)


if __name__ == "__main__":
    unittest.main()

# 최종 수정 일 : 2026-10-29
