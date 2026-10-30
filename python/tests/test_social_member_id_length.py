# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""소셜 PK의 예약·결제·대여 길이 경계 검증. 실제 DB는 사용하지 않습니다."""

import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from python.FastAPI.main import app
from python.FastAPI.auth.social_account import social_base
from python.FastAPI.match import reservation, payment
from python.FastAPI.ground import ground_reservation


def database():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.lastrowid = 7
    cursor.rowcount = 1
    cursor.fetchall.return_value = []
    return connection, cursor


def requests(member):
    reservation_body = {"c_id_seq": member, "g_code": "2", "r_date": "2100-01-01", "rs_time": "10:00", "p_method": "카카오페이"}
    return [("/match/reservation", reservation, reservation_body),
            ("/ground/reservation", ground_reservation, reservation_body),
            ("/match/payment", payment, {"c_id_seq": member, "r_seq": 7, "p_method": "카카오페이"})]


def test_48_and_50_character_members_complete_mock_business_flow():
    for member in [social_base("google", "virtual-subject") + "_01", "a" * 47 + "_01"]:
        assert len(member) in (48, 50)
        with TestClient(app) as client:
            for path, module, body in requests(member):
                connection, cursor = database()
                if module is reservation:
                    cursor.fetchone.side_effect = [{"g_code": 2, "g_num": 10, "g_price": 10000}, {"exists": 1}, None,
                                                   None, None, {"reservation_count": 0}]
                elif module is ground_reservation:
                    cursor.fetchone.side_effect = [{"g_code": 2, "g_price": 10000}, {"exists": 1}, None]
                else:
                    cursor.fetchone.side_effect = [{"c_id_seq": member, "g_code": 2, "r_date": date(2100, 1, 1),
                                                    "reservation_category": "1", "r_category": "1", "r_c_category": "",
                                                    "g_price": 10000, "g_num": 10}, None]
                with patch.object(module, "connect", return_value=connection):
                    response = client.post(path, json=body)
                assert response.status_code == 201, (path, response.status_code)
                assert response.json()["c_id_seq"] == member
                connection.commit.assert_called_once()
                connection.close.assert_called_once()


def test_51_character_members_rejected_before_db_access():
    with TestClient(app) as client:
        for path, module, body in requests("a" * 48 + "_01"):
            with patch.object(module, "connect") as connect:
                response = client.post(path, json=body)
                assert response.status_code == 422
                assert ["body", "c_id_seq"] in [item["loc"] for item in response.json()["detail"]]
                connect.assert_not_called()


def test_swagger_member_id_limit_is_50_for_all_three_routes():
    schema = app.openapi()
    for path, _, _ in requests("member_01"):
        ref = schema["paths"][path]["post"]["requestBody"]["content"]["application/json"]["schema"]["$ref"]
        request_schema = schema["components"]["schemas"][ref.rsplit("/", 1)[-1]]
        assert request_schema["properties"]["c_id_seq"]["maxLength"] == 50


def test_long_member_id_does_not_bypass_payment_owner_check():
    member = social_base("google", "virtual-subject") + "_01"
    connection, cursor = database()
    cursor.fetchone.return_value = {"c_id_seq": "other_01"}
    with TestClient(app) as client, patch.object(payment, "connect", return_value=connection):
        response = client.post("/match/payment", json={"c_id_seq": member, "r_seq": 7, "p_method": "카카오페이"})
    assert response.status_code == 403
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-28
