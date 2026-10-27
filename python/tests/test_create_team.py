# 2026-10-27
# 작업자 : 양태건

"""실제 팀을 생성하지 않고 팀 개설·팀장 등록의 원자성을 검증합니다."""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.team import create_team
from python.FastAPI.team.team import router


class CreateTeamTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/team')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.lastrowid = 7
        self.created = datetime(2026, 10, 27, 10, 30)
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, None, {'c_date': self.created}]
        patcher = patch.object(create_team, 'connect', return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)
        self.payload = {'c_id_seq': 'member_01', 't_name': '우리 팀', 't_logo': None}

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_creation_registers_owner_as_member_and_captain(self):
        self.payload['t_name'] = '  우리 팀  '
        response = self.client.post('/team/create', json=self.payload)
        self.assertEqual(response.status_code, 201, response.text)
        result = response.json()
        self.assertEqual(result['t_id'], 7)
        self.assertEqual(result['captain_id'], 'member_01')
        self.assertEqual(result['c_category'], '개설일')
        self.assertEqual(result['c_date'], self.created.isoformat())
        calls = self.cursor.execute.call_args_list
        self.assertIn('FOR UPDATE', calls[0].args[0])
        self.assertIn('INSERT INTO team (', calls[2].args[0])
        self.assertEqual(calls[2].args[1], ('우리 팀', None))
        self.assertIn("'개설일', NOW()", calls[3].args[0])
        self.assertEqual(calls[3].args[1], (7, 'member_01'))
        self.assertIn('INSERT INTO t_register', calls[4].args[0])
        self.assertEqual(calls[4].args[1], ('member_01', 7))
        self.assertIn('INSERT INTO team_captain_change', calls[5].args[0])
        self.assertEqual(calls[5].args[1], (7, 'member_01'))
        self.assertEqual(calls[6].args[1], ('우리 팀', 'member_01'))
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_called_once()

    def test_logo_is_optional(self):
        del self.payload['t_logo']
        response = self.client.post('/team/create', json=self.payload)
        self.assertEqual(response.status_code, 201)
        self.assertIsNone(response.json()['t_logo'])

    def test_unknown_member_rejected(self):
        self.cursor.fetchone.side_effect = [None]
        self.assertEqual(self.client.post('/team/create', json=self.payload).status_code, 404)
        self.assertEqual(self.cursor.execute.call_count, 1)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()

    def test_existing_membership_rejected_without_writes(self):
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, {'1': 1}]
        self.assertEqual(self.client.post('/team/create', json=self.payload).status_code, 409)
        self.assertEqual(self.cursor.execute.call_count, 2)
        self.connection.commit.assert_not_called()

    def test_validation_rejects_blank_oversized_and_server_owned_fields(self):
        for updates in [{'c_id_seq': ' '}, {'t_name': ' '}, {'t_name': '가' * 51},
                        {'t_logo': '가' * 256}, {'c_category': '폐지일'},
                        {'c_date': '2026-10-27'}, {'captain_id': 'other_01'}, {'t_rating': 9999}]:
            with self.subTest(updates=updates):
                response = self.client.post('/team/create', json=dict(self.payload, **updates))
                self.assertEqual(response.status_code, 422)
        self.connect.assert_not_called()

    def test_each_write_failure_rolls_back_every_table(self):
        for failure_at in range(2, 7):
            with self.subTest(failure_at=failure_at):
                self.connection.reset_mock()
                self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, None]
                self.cursor.execute.side_effect = [None] * failure_at + [RuntimeError('test failure')]
                with self.assertLogs(create_team.logger, level='ERROR'):
                    response = self.client.post('/team/create', json=self.payload)
                self.assertEqual(response.status_code, 500)
                self.connection.rollback.assert_called_once()
                self.connection.commit.assert_not_called()
                self.connection.close.assert_called_once()

    def test_integrity_failure_returns_conflict(self):
        self.cursor.execute.side_effect = [None, None, pymysql.IntegrityError(1452, 'test FK')]
        with self.assertLogs(create_team.logger, level='ERROR'):
            response = self.client.post('/team/create', json=self.payload)
        self.assertEqual(response.status_code, 409)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_invalid_team_id_rolls_back(self):
        self.cursor.lastrowid = 0
        with self.assertLogs(create_team.logger, level='ERROR'):
            response = self.client.post('/team/create', json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.connection.rollback.assert_called_once()

    def test_missing_saved_date_rolls_back(self):
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, None, None]
        with self.assertLogs(create_team.logger, level='ERROR'):
            response = self.client.post('/team/create', json=self.payload)
        self.assertEqual(response.status_code, 500)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_main_router_exposes_team_create(self):
        from python.FastAPI.main import app
        schema = app.openapi()
        self.assertIn('post', schema['paths']['/team/create'])
        self.assertIn('201', schema['paths']['/team/create']['post']['responses'])
        self.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
