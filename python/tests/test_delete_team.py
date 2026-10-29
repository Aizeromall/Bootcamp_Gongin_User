# 2026-10-27
# 작업자 : 양태건

"""실제 DB 변경 없이 팀 폐지 권한·상태·팀원 해제·롤백을 검증합니다."""
import unittest
from datetime import datetime
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.team_create import delete
from python.FastAPI.team_create.team import router


class DeleteTeamTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/team')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.rowcount = 3
        self.closed_date = datetime(2026, 10, 27, 15, 0)
        self.team = {'t_id': 7, 't_name': '우리 팀', 'c_id_seq': 'creator_01', 'c_category': '개설일'}
        self.cursor.fetchone.side_effect = [
            {'c_id_seq': 'captain_01'}, self.team,
            {'t_c_captain': 'captain_01'}, {'c_date': self.closed_date}]
        patcher = patch.object(delete, 'connect', return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    def request(self, member='captain_01'):
        return self.client.delete('/team/delete/7', params={'c_id_seq': member})

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_current_captain_closes_team_and_releases_members(self):
        response = self.request()
        self.assertEqual(response.status_code, 200, response.text)
        data = response.json()
        self.assertEqual(data['c_category'], '폐지일')
        self.assertEqual(data['c_date'], self.closed_date.isoformat())
        self.assertEqual(data['captain_id'], 'captain_01')
        self.assertEqual(data['members_released'], 3)
        calls = self.cursor.execute.call_args_list
        self.assertIn('FOR UPDATE', calls[1].args[0])
        self.assertIn('t_c_date DESC, t_c_seq DESC', calls[2].args[0])
        self.assertIn("c_category = '폐지일', c_date = NOW()", calls[3].args[0])
        self.assertEqual(calls[3].args[1], (7,))
        self.assertNotIn('c_id_seq =', calls[3].args[0])
        self.assertIn("c.c_team = '무소속'", calls[4].args[0])
        self.assertEqual(calls[4].args[1], (7, '우리 팀'))
        self.assertIn("UPDATE t_register SET c_category = '탈퇴', tr_state = '탈퇴', tr_date = NOW()", calls[5].args[0])
        self.assertEqual(calls[5].args[1], (7,))
        self.assertFalse(any('DELETE FROM t_register' in call.args[0] for call in calls))
        self.assertFalse(any('DELETE FROM team ' in call.args[0] or
                             'DELETE FROM team_captain_change' in call.args[0] for call in calls))
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_called_once()

    def test_creator_is_captain_when_no_change_record_exists(self):
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'creator_01'}, self.team, None, {'c_date': self.closed_date}]
        response = self.request('creator_01')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['captain_id'], 'creator_01')

    def test_former_captain_cannot_close_after_transfer(self):
        response = self.request('creator_01')
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.cursor.execute.call_count, 3)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()

    def test_duplicate_closure_rejected(self):
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'captain_01'},
            dict(self.team, c_category='폐지일'), {'t_c_captain': 'captain_01'}]
        self.assertEqual(self.request().status_code, 409)
        self.assertEqual(self.cursor.execute.call_count, 3)
        self.connection.commit.assert_not_called()

    def test_missing_member_and_team(self):
        for rows in [[None], [{'c_id_seq': 'captain_01'}, None]]:
            self.cursor.fetchone.side_effect = rows
            self.assertEqual(self.request().status_code, 404)
        self.connection.commit.assert_not_called()

    def test_invalid_ids_rejected_before_connection(self):
        for member in ['', '   ', '가' * 51]:
            self.assertEqual(self.request(member).status_code, 422)
        self.assertEqual(self.client.delete('/team/delete/0', params={'c_id_seq': 'captain_01'}).status_code, 422)
        self.assertEqual(self.client.delete('/team/delete/7').status_code, 422)
        self.connect.assert_not_called()

    def test_every_write_failure_rolls_back_all_changes(self):
        for failure_at in [3, 4, 5]:
            with self.subTest(failure_at=failure_at):
                self.connection.reset_mock()
                self.cursor.fetchone.side_effect = [
                    {'c_id_seq': 'captain_01'}, self.team, {'t_c_captain': 'captain_01'}]
                self.cursor.execute.side_effect = [None] * failure_at + [RuntimeError('test failure')]
                with self.assertLogs(delete.logger, level='ERROR'):
                    response = self.request()
                self.assertEqual(response.status_code, 500)
                self.connection.rollback.assert_called_once()
                self.connection.commit.assert_not_called()
                self.connection.close.assert_called_once()

    def test_integrity_error_rolls_back(self):
        self.cursor.execute.side_effect = [None, None, None, pymysql.IntegrityError(1452, 'test FK')]
        with self.assertLogs(delete.logger, level='ERROR'):
            response = self.request()
        self.assertEqual(response.status_code, 409)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_missing_saved_date_rolls_back(self):
        self.cursor.fetchone.side_effect = [
            {'c_id_seq': 'captain_01'}, self.team, {'t_c_captain': 'captain_01'}, None]
        with self.assertLogs(delete.logger, level='ERROR'):
            self.assertEqual(self.request().status_code, 500)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_closed_team_is_excluded_by_existing_captain_query(self):
        from python.FastAPI.team_match.team_match_connect import find_captain_team
        self.cursor.fetchone.side_effect = [None]
        self.assertIsNone(find_captain_team(self.cursor, 'captain_01'))
        sql, params = self.cursor.execute.call_args.args
        self.assertIn("COALESCE(tc.c_category, '') <> '폐지일'", sql)
        self.assertEqual(params, ('captain_01',))

    def test_main_registers_closure_api(self):
        from python.FastAPI.main import app
        self.assertIn('delete', app.openapi()['paths']['/team/delete/{t_id}'])
        self.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건

# 수정 일 : 2026-10-28 / 작업자 : 양태건
# 탈퇴 상태와 대기 신청 종료 SQL을 포함한 폐지 계약을 검증합니다.
# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
