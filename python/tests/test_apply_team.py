# 2026-10-27
# 작업자 : 양태건

"""모의 DB로 팀 가입·탈퇴·재가입과 기존 소속 연동을 검증합니다."""
import unittest
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient
from python.FastAPI.team import apply_team
from python.FastAPI.team.team import router


class ApplyTeamTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/team')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.team = {'t_id': 7, 't_name': '우리 팀', 'c_category': '개설일', 'c_id_seq': 'captain_01'}
        self.joined = {'tr_seq': 3, 'tr_date': '2026-10-27T15:00:00', 'c_category': '가입'}
        self.left = dict(self.joined, c_category='탈퇴')
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, self.team, None, None, self.joined]
        patcher = patch.object(apply_team, 'connect', return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    def join(self):
        return self.client.post('/team/apply/7', json={'c_id_seq': 'member_01'})

    def leave(self):
        return self.client.delete('/team/leave/7', params={'c_id_seq': 'member_01'})

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_join_stores_category_date_and_customer_team(self):
        response = self.join()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['c_category'], '가입')
        calls = self.cursor.execute.call_args_list
        self.assertIn('FOR UPDATE', calls[0].args[0])
        self.assertIn('FOR UPDATE', calls[1].args[0])
        self.assertIn("NOW(), '가입'", calls[4].args[0])
        self.assertEqual(calls[4].args[1], ('member_01', 7))
        self.assertEqual(calls[5].args[1], ('우리 팀', 'member_01'))
        self.connection.commit.assert_called_once()
        self.connection.rollback.assert_not_called()
        self.connection.close.assert_called_once()

    def test_rejoin_updates_existing_unique_membership(self):
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, self.team, None,
                                           {'tr_seq': 3, 'c_category': '탈퇴'}, self.joined]
        response = self.join()
        self.assertEqual(response.status_code, 201)
        calls = self.cursor.execute.call_args_list
        self.assertIn("UPDATE t_register SET c_category = '가입'", calls[4].args[0])
        self.assertEqual(calls[4].args[1], (3, 'member_01', 7))
        self.assertFalse(any('INSERT INTO t_register' in c.args[0] for c in calls))

    def test_duplicate_or_other_active_membership_rejected(self):
        for team_id in [7, 8]:
            self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, self.team, {'t_id': team_id}]
            self.assertEqual(self.join().status_code, 409)
        self.connection.commit.assert_not_called()

    def test_missing_member_team_and_closed_team_rejected(self):
        for rows, expected in [([None], 404), ([{}, None], 404),
                               ([{}, dict(self.team, c_category='폐지일')], 409)]:
            self.cursor.fetchone.side_effect = rows
            self.assertEqual(self.join().status_code, expected)
        self.connection.commit.assert_not_called()

    def test_unknown_existing_category_not_overwritten(self):
        self.cursor.fetchone.side_effect = [{}, self.team, None, {'tr_seq': 3, 'c_category': '확인필요'}]
        self.assertEqual(self.join().status_code, 409)
        self.connection.commit.assert_not_called()

    def test_leave_preserves_record_and_sets_date(self):
        self.cursor.fetchone.side_effect = [{}, self.team, {'tr_seq': 3, 'c_category': '가입'},
                                           {'t_c_captain': 'captain_01'}, self.left]
        response = self.leave()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['c_category'], '탈퇴')
        calls = self.cursor.execute.call_args_list
        self.assertIn("c_category = '탈퇴', tr_date = NOW()", calls[4].args[0])
        self.assertEqual(calls[4].args[1], (3, 'member_01', 7))
        self.assertEqual(calls[5].args[1], ('member_01', '우리 팀'))
        self.assertFalse(any('DELETE FROM t_register' in c.args[0] for c in calls))
        self.connection.commit.assert_called_once()

    def test_current_captain_cannot_leave_without_transfer(self):
        for captain in [None, {'t_c_captain': 'member_01'}]:
            team = dict(self.team, c_id_seq='member_01')
            self.cursor.fetchone.side_effect = [{}, team, {'tr_seq': 3, 'c_category': '가입'}, captain]
            self.assertEqual(self.leave().status_code, 409)
        self.connection.commit.assert_not_called()

    def test_former_captain_can_leave_after_transfer_and_legacy_blank_is_active(self):
        self.cursor.fetchone.side_effect = [{}, dict(self.team, c_id_seq='member_01'),
                                           {'tr_seq': 3, 'c_category': ''},
                                           {'t_c_captain': 'captain_01'}, self.left]
        self.assertEqual(self.leave().status_code, 200)

    def test_leave_missing_member_team_membership_and_already_left(self):
        for rows, code in [([None], 404), ([{}, None], 404), ([{}, self.team, None], 404),
                           ([{}, self.team, {'tr_seq': 3, 'c_category': '탈퇴'}], 409)]:
            self.cursor.fetchone.side_effect = rows
            self.assertEqual(self.leave().status_code, code)
        self.connection.commit.assert_not_called()

    def test_invalid_payload_rejected_before_db(self):
        for payload in [{'c_id_seq': '  '}, {'c_id_seq': '가' * 51},
                        {'c_id_seq': 'member_01', 'c_category': '가입'}]:
            self.assertEqual(self.client.post('/team/apply/7', json=payload).status_code, 422)
        self.assertEqual(self.client.post('/team/apply/0', json={'c_id_seq': 'member_01'}).status_code, 422)
        self.assertEqual(self.client.delete('/team/leave/7', params={'c_id_seq': '  '}).status_code, 422)
        self.connect.assert_not_called()

    def test_join_failure_rolls_back_membership_and_customer(self):
        for fail_at in [4, 5, 6]:
            self.connection.reset_mock()
            self.cursor.fetchone.side_effect = [{}, self.team, None, None]
            self.cursor.execute.side_effect = [None] * fail_at + [RuntimeError('test failure')]
            with self.assertLogs(apply_team.logger, level='ERROR'):
                self.assertEqual(self.join().status_code, 500)
            self.connection.rollback.assert_called_once()
            self.connection.commit.assert_not_called()
            self.connection.close.assert_called_once()

    def test_leave_failure_rolls_back_membership_and_customer(self):
        for fail_at in [4, 5, 6]:
            self.connection.reset_mock()
            self.cursor.fetchone.side_effect = [{}, self.team, {'tr_seq': 3, 'c_category': '가입'},
                                               {'t_c_captain': 'captain_01'}]
            self.cursor.execute.side_effect = [None] * fail_at + [RuntimeError('test failure')]
            with self.assertLogs(apply_team.logger, level='ERROR'):
                self.assertEqual(self.leave().status_code, 500)
            self.connection.rollback.assert_called_once()
            self.connection.commit.assert_not_called()

    def test_integrity_error_is_conflict(self):
        self.cursor.execute.side_effect = [None] * 4 + [pymysql.IntegrityError(1062, 'test duplicate')]
        with self.assertLogs(apply_team.logger, level='ERROR'):
            self.assertEqual(self.join().status_code, 409)
        self.connection.rollback.assert_called_once()

    def test_active_roster_counts_ignore_left_members(self):
        from python.FastAPI.team_match import team_match_connect as matching
        team = dict(t_id=7, t_name='우리 팀', t_logo=None, t_rating=1500)
        self.cursor.fetchone.side_effect = [{'c_id_seq': 'member_01'}, {'n': 2}, None]
        self.cursor.fetchall.return_value = [{
            'comment_seq': 1, 'c_id_seq': 'member_01', 'comment_content': '신청', 'c_name': '회원'}]
        with patch.object(matching, 'connect', return_value=self.connection), \
             patch.object(matching, 'find_captain_team', return_value=team), \
             patch.object(matching, 'post_to_dict', return_value={}):
            result = matching.select_team_match_requests(1, c_id_seq='member_01')
        self.assertEqual(result['results'][0]['member_count'], 2)
        count = [call for call in self.cursor.execute.call_args_list if 'COUNT(*)' in call.args[0]][0]
        self.assertIn("COALESCE(c_category, '') IN ('', '가입', '가입일')", count.args[0])
        self.assertEqual(count.args[1], (7,))

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_legacy_left_state_rejoins_using_new_join_value(self):
        self.cursor.fetchone.side_effect = [{}, self.team, None,
            {'tr_seq': 3, 'c_category': '탈퇴일'}, self.joined]
        response = self.join()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['c_category'], '가입')
        self.assertIn("SET c_category = '가입'", self.cursor.execute.call_args_list[4].args[0])

    def test_legacy_join_state_leaves_using_new_left_value(self):
        self.cursor.fetchone.side_effect = [{}, self.team, {'tr_seq': 3, 'c_category': '가입일'},
            {'t_c_captain': 'captain_01'}, self.left]
        response = self.leave()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['c_category'], '탈퇴')
        self.assertIn("SET c_category = '탈퇴'", self.cursor.execute.call_args_list[4].args[0])

    def test_main_exposes_join_and_leave(self):
        from python.FastAPI.main import app
        paths = app.openapi()['paths']
        self.assertIn('post', paths['/team/apply/{t_id}'])
        self.assertIn('delete', paths['/team/leave/{t_id}'])
        self.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
