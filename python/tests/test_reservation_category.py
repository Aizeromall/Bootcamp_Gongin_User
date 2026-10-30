# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""실제 VARCHAR 자료형을 사용한 예약 분류 회귀 검사. 실제 DB 쓰기는 없습니다."""

import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from fastapi import HTTPException

from python.FastAPI.match import reservation_status as status, payment, reservation
from python.FastAPI.ground import ground_reservation as rental
from python.FastAPI.cancel import customer_match_delete as cancel


def database():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.lastrowid = 7
    cursor.rowcount = 1
    return connection, cursor


def row(category):
    return {"r_seq": 7, "c_id_seq": "member_01", "g_code": 2, "r_date": date(2100, 1, 1),
            "r_check": 0, "r_category": "1", "r_c_category": "", "reservation_category": category,
            "g_price": 10000, "g_num": 10, "rs_time": "10:00", "re_time": "12:00"}


def test_constants_and_sql_conditions_are_strict_strings():
    assert status.RESERVATION_MATCH == "1" and status.RESERVATION_RENTAL == "2"
    assert status.reservation_type_condition("1", "r") == "r.reservation_category = '1'"
    assert status.reservation_type_condition("2") == "reservation_category = '2'"
    for invalid in [1, 2, True, None, "", "3", "1 OR 1=1"]:
        try:
            status.reservation_type_condition(invalid)
            raise AssertionError("must reject invalid category")
        except ValueError:
            pass


def test_payment_string_category_uses_rental_total_or_individual_share():
    for category, amount in [("1", "1000"), ("2", "10000")]:
        connection, cursor = database()
        cursor.fetchone.side_effect = [row(category), None] if category == '1' else [row(category), None, None]
        with patch.object(payment, "connect", return_value=connection):
            result = payment.create_payment(7, "member_01", "카카오페이")
        assert result["p_amount"] == amount
        connection.commit.assert_called_once()


def test_existing_string_category_blocks_rental_before_insert():
    for category in ["1", "2"]:
        connection, cursor = database()
        cursor.fetchone.side_effect = [{"g_code": 2, "g_price": 10000}, {"exists": 1}]
        cursor.fetchall.return_value = [{"reservation_category": category}]
        with patch.object(rental, "connect", return_value=connection):
            try:
                rental.create_ground_reservation("member_01", "2", date(2100, 1, 1), "10:00", "카카오페이")
                raise AssertionError("must reject occupied slot")
            except HTTPException as error:
                assert error.status_code == 409
        assert not any("INSERT INTO reservation" in call.args[0] for call in cursor.execute.call_args_list)
        connection.rollback.assert_called_once()
        connection.commit.assert_not_called()


def test_rental_cancel_accepts_string_two():
    connection, cursor = database()
    cursor.fetchone.side_effect = [{'g_code': 2}, {'g_code': 2}, row("2"), None, row("2"), None]
    cursor.fetchall.return_value = []
    with patch.object(rental, "connect", return_value=connection):
        result = rental.cancel_ground_reservation(7, "가상 취소 사유", "member_01")
    assert result["reservation_category"] == "2"
    connection.commit.assert_called_once()


def test_personal_cancel_rejects_rental_string_two():
    connection, cursor = database()
    cursor.fetchone.return_value = row("2")
    with patch.object(cancel, "connect", return_value=connection):
        try:
            cancel.delete_customer_reservation(7, "가상 사유", "member_01")
            raise AssertionError("must reject rental via personal cancellation")
        except HTTPException as error:
            assert error.status_code == 409
    assert not any("DELETE FROM pay" in call.args[0] for call in cursor.execute.call_args_list)
    connection.commit.assert_not_called()


def test_slot_flags_use_string_categories():
    connection, cursor = database()
    cursor.fetchone.return_value = {"g_code": 2, "g_name": "가상 구장", "g_price": 10000}
    cursor.fetchall.return_value = [{"rs_time": timedelta(hours=10), "reservation_category": "2"},
                                    {"rs_time": timedelta(hours=12), "reservation_category": "1"}]
    with patch.object(rental, "connect", return_value=connection), patch.object(rental, "find_assigned_manager", return_value=None):
        result = rental.select_ground_reservation_slots("2", date(2100, 1, 1))
    slots = {slot["rs_time"]: slot for slot in result["slots"]}
    assert slots["10:00"]["is_rented"] and not slots["10:00"]["is_available"]
    assert slots["12:00"]["has_match_reservation"] and not slots["12:00"]["is_available"]
    assert slots["08:00"]["is_available"]


def test_new_reservation_and_rental_insert_string_category():
    for module, category in [(reservation, "1"), (rental, "2")]:
        connection, cursor = database()
        if module is reservation:
            cursor.fetchone.side_effect = [{"g_code": 2, "g_num": 10, "g_price": 10000}, {"exists": 1}, None, None, None,
                                           {"reservation_count": 0}]
        else:
            cursor.fetchone.side_effect = [{"g_code": 2, "g_price": 10000}, {"exists": 1}, None]
            cursor.fetchall.return_value = []
        with patch.object(module, "connect", return_value=connection):
            create = module.create_reservation if module is reservation else module.create_ground_reservation
            create("member_01", "2", date(2100, 1, 1), "10:00", "카카오페이")
        inserted = [call for call in cursor.execute.call_args_list if "INSERT INTO reservation" in call.args[0]]
        assert len(inserted) == 1 and inserted[0].args[1][-3] == category


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith("test_") and callable(fn))

# 최종 수정 일 : 2026-10-28
# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
