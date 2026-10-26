"""구장·예약 배정 회귀 검증. 작업자 : 양태건 / 최종 수정일 : 2026-10-26."""
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.match import ground_search, reservation


class GroundAssignmentTests(unittest.TestCase):
    def test_ground_list_search_detail_preserve_unassigned_grounds(self):
        row = dict(g_code=1, g_name="구장", g_address="서울", g_num=10,
                   g_price=10000, g_information=None, g_time="08:00~24:00",
                   g_lat=0, g_lng=0, m_id=None, m_name=None)
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.fetchall.return_value = [row]
        cursor.fetchone.return_value = row
        app = FastAPI()
        app.include_router(ground_search.router, prefix="/match")
        with patch.object(ground_search, "connect", return_value=connection), TestClient(app) as client:
            for path, params in [("/match/ground", {}), ("/match/ground", {"keyword": "서울"}),
                                 ("/match/ground/1", {})]:
                with self.subTest(path=path, params=params):
                    response = client.get(path, params=params)
                    self.assertEqual(response.status_code, 200)
                    data = response.json()
                    self.assertIsNone((data['results'][0] if 'results' in data else data)['m_id'])
            cursor.fetchone.return_value = None
            self.assertEqual(client.get('/match/ground/999').status_code, 404)
        self.assertEqual(connection.close.call_count, 4)
        connection.commit.assert_not_called()

    def test_reservation_returns_matching_manager_without_missing_db_column(self):
        for manager in [None, {'m_id': 'manager', 'm_name': '매니저'}]:
            with self.subTest(manager=manager):
                connection = MagicMock()
                cursor = connection.cursor.return_value.__enter__.return_value
                cursor.fetchone.side_effect = [
                    {'g_code': 1, 'g_num': 10}, {'1': 1}, manager,
                    None, {'reservation_count': 0},
                ]
                cursor.lastrowid = 99
                with patch.object(reservation, 'connect', return_value=connection):
                    result = reservation.create_reservation('member_01', '1', date(2026, 10, 26), '08:00')
                expected = manager['m_id'] if manager else None
                self.assertEqual(result['m_id'], expected)
                insert = [call for call in cursor.execute.call_args_list if 'INSERT INTO reservation' in call.args[0]][0]
                self.assertNotIn('m_id', insert.args[0])
                self.assertEqual(insert.args[1][-2:], ('1', ''))
                # 배정 조회에 예약 시작·종료 시간을 모두 전달하는지 확인합니다.
                self.assertEqual(cursor.execute.call_args_list[2].args[1],
                                 ('1', date(2026, 10, 26), '08:00', '10:00'))
                connection.commit.assert_called_once()
                connection.close.assert_called_once()


if __name__ == '__main__':
    unittest.main()
