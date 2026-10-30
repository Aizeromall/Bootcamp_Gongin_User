# 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
"""예약과 결제 실패 시 같은 트랜잭션을 되돌리는 Mock 검증입니다."""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

import pymysql
from fastapi.testclient import TestClient

from python.FastAPI.main import app
from python.FastAPI.match import reservation
from python.FastAPI.ground import ground_reservation


class AtomicReservationTests(unittest.TestCase):
    def test_payment_failure_rolls_back_both_reservation_types(self):
        for module, path in [(reservation, '/match/reservation'),
                             (ground_reservation, '/ground/reservation')]:
            with self.subTest(path=path):
                connection = MagicMock()
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.lastrowid = 17
                cursor.fetchall.return_value = []
                if module is reservation:
                    cursor.fetchone.side_effect = [
                        {'g_code': '2', 'g_num': 10, 'g_price': 10000}, {'exists': 1},
                        None, None, None, {'reservation_count': 0}]
                else:
                    cursor.fetchone.side_effect = [
                        {'g_code': '2', 'g_price': 10000}, {'exists': 1}, None]
                with patch.object(module, 'connect', return_value=connection), \
                     patch.object(module, 'insert_payment', side_effect=pymysql.MySQLError('virtual')), \
                     patch.object(module.logger, 'error') as log_error, TestClient(app) as client:
                    response = client.post(path, json={'c_id_seq': 'member_01', 'g_code': '2',
                        'r_date': '2100-01-01', 'rs_time': '10:00', 'p_method': '카카오페이'})
                self.assertEqual(response.status_code, 500)
                self.assertTrue(any('INSERT INTO reservation' in c.args[0]
                                    for c in cursor.execute.call_args_list))
                connection.rollback.assert_called_once()
                connection.commit.assert_not_called()
                self.assertEqual(log_error.call_args.args[1:], ('결제 기록 저장', 'MySQLError'))

    def test_payment_method_is_required_before_database_connection(self):
        with TestClient(app) as client:
            for module, path in [(reservation, '/match/reservation'),
                                 (ground_reservation, '/ground/reservation')]:
                with patch.object(module, 'connect') as connect:
                    response = client.post(path, json={'c_id_seq': 'member_01', 'g_code': '2',
                        'r_date': '2100-01-01', 'rs_time': '10:00'})
                self.assertEqual(response.status_code, 422)
                connect.assert_not_called()


# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
