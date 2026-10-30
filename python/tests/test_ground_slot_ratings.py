# 작업자 : 최현준
# 최초 작업 일 : 2026-10-30
from datetime import timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.match import reservation_search


def test_slot_rating_uses_active_sport_reservations_and_preserves_empty():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = {"g_code": "G1"}
    cursor.fetchall.return_value = [
        {"rs_time": timedelta(hours=8), "applicant_count": 2, "rated_count": 2,
         "average_rating": Decimal("1599.5")},
        {"rs_time": timedelta(hours=10), "applicant_count": 1, "rated_count": 0,
         "average_rating": None},
    ]
    app = FastAPI()
    app.include_router(reservation_search.router, prefix="/match")
    with patch.object(reservation_search, "connect", return_value=connection), TestClient(app) as client:
        result = client.get("/match/reservation/ground/G1/ratings", params={"r_date": "2026-10-30", "sport": 1})
        assert result.status_code == 200
        slots = result.json()["slots"]
        assert slots[0]["average_tier"] == "비기너 1"
        assert slots[0]["average_rating"] == 1599.5
        assert slots[1]["average_tier"] is None and slots[1]["applicant_count"] == 1
        assert slots[2]["average_tier"] is None and slots[2]["applicant_count"] == 0
        sql, params = cursor.execute.call_args.args
        assert "SELECT DISTINCT" in sql and "reservation_category = '1'" in sql
        assert "r_c_category" in sql and params[2] == "_01"
        assert client.get("/match/reservation/ground/G1/ratings", params={"r_date": "2026-10-30", "sport": 5}).status_code == 422
    connection.close.assert_called()


def test_slot_rating_unknown_ground_is_404():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value.fetchone.return_value = None
    app = FastAPI()
    app.include_router(reservation_search.router, prefix="/match")
    with patch.object(reservation_search, "connect", return_value=connection), TestClient(app) as client:
        assert client.get("/match/reservation/ground/missing/ratings", params={"r_date": "2026-10-30", "sport": 1}).status_code == 404
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
