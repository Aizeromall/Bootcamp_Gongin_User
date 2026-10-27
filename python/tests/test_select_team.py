# 2026-10-27
# 작업자 : 양태건

"""팀 조회 API 검증. 실제 DB 쓰기는 실행하지 않습니다."""
import unittest
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.team import select
from python.FastAPI.team.team import router


class SelectTeamTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/team')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.row = dict(t_id=7, t_name='우리 팀', t_logo=None, t_rating=1500,
                        creator_id='creator_01', captain_id='captain_01', captain_name='팀장',
                        c_category='개설일', c_date='2026-10-27T10:00:00', member_count=3)
        self.cursor.fetchone.return_value = {'total': 1}
        self.cursor.fetchall.return_value = [self.row]
        patcher = patch.object(select, 'connect', return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_list_excludes_closed_by_default_and_uses_select_only(self):
        response = self.client.get('/team/select')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['total'], 1)
        self.assertEqual(response.json()['results'][0]['captain_id'], 'captain_01')
        self.assertFalse(response.json()['results'][0]['is_closed'])
        for call in self.cursor.execute.call_args_list:
            self.assertTrue(call.args[0].strip().startswith('SELECT'))
            self.assertIn("COALESCE(tc.c_category, '') <> '폐지일'", call.args[0])
        self.assertIn('t_c_date DESC, cc.t_c_seq DESC', self.cursor.execute.call_args.args[0])
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_include_closed_and_detail_preserve_closure_state(self):
        self.cursor.fetchall.return_value = [dict(self.row, c_category='폐지일', member_count=0)]
        response = self.client.get('/team/select', params={'include_closed': True})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['results'][0]['is_closed'])
        self.assertNotIn("<> '폐지일'", self.cursor.execute.call_args.args[0])
        self.cursor.fetchone.return_value = dict(self.row, c_category='폐지일', member_count=0)
        response = self.client.get('/team/select/7')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['is_closed'])
        self.assertEqual(response.json()['member_count'], 0)

    def test_search_literal_and_pagination(self):
        response = self.client.get('/team/select', params={'keyword': "%'_", 'limit': 5, 'offset': 10})
        self.assertEqual(response.status_code, 200)
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(params, ("%!%'!_%", 5, 10))
        self.assertNotIn("%'_", sql)
        self.assertEqual(response.json()['limit'], 5)
        self.assertEqual(response.json()['offset'], 10)

    def test_detail_and_legacy_team_without_creation_record(self):
        self.cursor.fetchone.return_value = dict(self.row, c_category=None, c_date=None, creator_id=None,
                                                captain_id=None, captain_name=None)
        response = self.client.get('/team/select/7')
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['captain_id'])
        self.assertFalse(response.json()['is_closed'])
        self.assertEqual(self.cursor.execute.call_args.args[1], (7,))
        self.connection.commit.assert_not_called()

    def test_missing_team(self):
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.get('/team/select/999').status_code, 404)
        self.connection.close.assert_called_once()

    def test_empty_list(self):
        self.cursor.fetchone.return_value = {'total': 0}
        self.cursor.fetchall.return_value = []
        self.assertEqual(self.client.get('/team/select').json()['results'], [])

    def test_invalid_input_does_not_connect(self):
        for path in ['/team/select/0', '/team/select/-1', '/team/select?limit=101',
                     '/team/select?offset=-1', '/team/select?include_closed=invalid']:
            self.assertEqual(self.client.get(path).status_code, 422)
        self.connect.assert_not_called()

    def test_db_error_closes_connection(self):
        self.cursor.execute.side_effect = pymysql.OperationalError(2006, 'test failure')
        with self.assertLogs(select.logger, level='ERROR'):
            self.assertEqual(self.client.get('/team/select').status_code, 500)
            self.assertEqual(self.client.get('/team/select/7').status_code, 500)
        self.assertEqual(self.connection.close.call_count, 2)
        self.connection.commit.assert_not_called()

    def test_main_registers_routes(self):
        from python.FastAPI.main import app
        schema = app.openapi()
        self.assertIn('get', schema['paths']['/team/select'])
        self.assertIn('get', schema['paths']['/team/select/{t_id}'])
        self.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
