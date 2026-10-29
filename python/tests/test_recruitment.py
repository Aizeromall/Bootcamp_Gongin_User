# 2026-10-28
# 작업자 : 양태건
"""DB 연결은 모두 Mock으로 대체하며 실제 데이터를 쓰지 않습니다."""
import unittest
from unittest.mock import MagicMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from python.FastAPI.team_create import recruitment, apply_team
from python.FastAPI.team_create.team import router


class RecruitmentTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(router, prefix='/team')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.db = MagicMock()
        self.cur = self.db.cursor.return_value.__enter__.return_value
        self.team = {'t_id': 7, 't_name': '우리 팀', 'captain_id': 'captain_01', 'c_category': '개설일'}
        for module in [recruitment, apply_team]:
            p = patch.object(module, 'connect', return_value=self.db)
            p.start()
            self.addCleanup(p.stop)

    def decision(self, action='approve', **kwargs):
        return self.client.post('/team/' + action + '/7', json={'c_id_seq': 'captain_01', 'applicant_id': 'member_01', **kwargs})

    def test_approve_updates_membership_and_customer_atomically(self):
        self.cur.fetchone.side_effect = [{}, self.team, {'tr_seq': 9, 'tr_state': '대기'}, None]
        result = self.decision()
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['tr_state'], '승인')
        calls = self.cur.execute.call_args_list
        self.assertTrue(any('UPDATE customer' in c.args[0] for c in calls))
        self.assertEqual(calls[-1].args[1], ('승인', '가입', 9))
        self.assertTrue(any("t_id <> %s AND tr_state = '대기'" in c.args[0] for c in calls))
        self.db.commit.assert_called_once()

    def test_reject_does_not_change_customer(self):
        self.cur.fetchone.side_effect = [{}, self.team, {'tr_seq': 9, 'tr_state': '대기'}]
        self.assertEqual(self.decision('reject').status_code, 200)
        self.assertFalse(any('UPDATE customer' in c.args[0] for c in self.cur.execute.call_args_list))
        self.assertEqual(self.cur.execute.call_args_list[-1].args[1], ('거절', '', 9))

    def test_non_captain_closed_team_and_duplicate_decision_rejected(self):
        for team, application, code in [(dict(self.team, captain_id='other'), None, 403),
                                         (dict(self.team, c_category='폐지일'), None, 409),
                                         (self.team, {'tr_state': '승인'}, 409)]:
            self.cur.fetchone.side_effect = [{}, team, application]
            self.assertEqual(self.decision().status_code, code)
        self.db.commit.assert_not_called()
        self.assertEqual(self.db.rollback.call_count, 3)

    def test_other_membership_blocks_approval(self):
        self.cur.fetchone.side_effect = [{}, self.team, {'tr_seq': 9, 'tr_state': '대기'}, {'t_id': 8}]
        self.assertEqual(self.decision().status_code, 409)
        self.db.commit.assert_not_called()

    def test_member_list_hides_other_applicants(self):
        with patch.object(recruitment, 'recruitment_team', return_value=self.team):
            self.cur.fetchone.side_effect = [{'tr_state': '대기'}, None]
            result = self.client.get('/team/recruitment/10', params={'c_id_seq': 'member_01'})
        self.assertEqual(result.status_code, 200)
        self.assertFalse(result.json()['can_manage'])
        self.assertEqual(result.json()['results'], [])
        self.cur.fetchall.assert_not_called()

    def test_captain_lists_applicants(self):
        with patch.object(recruitment, 'recruitment_team', return_value=self.team):
            self.cur.fetchone.side_effect = [None, {'t_id': 7}]
            self.cur.fetchall.return_value = [{'tr_seq': 9, 'tr_state': '대기'}]
            result = self.client.get('/team/recruitment/10', params={'c_id_seq': 'captain_01'})
        self.assertTrue(result.json()['can_manage'])
        self.assertEqual(len(result.json()['results']), 1)

    def test_team_detail_list_is_captain_only(self):
        self.cur.fetchone.return_value = self.team
        self.cur.fetchall.return_value = []
        response = self.client.get('/team/applications/7', params={'c_id_seq': 'captain_01'})
        self.assertEqual(response.status_code, 200)
        response = self.client.get('/team/applications/7', params={'c_id_seq': 'member_01'})
        self.assertEqual(response.status_code, 403)

    def test_pending_duplicate_and_wrong_post_blocked(self):
        self.cur.fetchone.side_effect = [{}, self.team, None, {'tr_seq': 9, 'tr_state': '대기'}]
        self.assertEqual(self.client.post('/team/apply/7', json={'c_id_seq': 'member_01'}).status_code, 409)
        with patch.object(apply_team, 'recruitment_team', return_value=dict(self.team, t_id=8)):
            self.cur.fetchone.side_effect = [{}, self.team]
            self.assertEqual(self.client.post('/team/apply/7', json={'c_id_seq': 'member_01', 'bulletin_seq': 10}).status_code, 409)
        self.db.commit.assert_not_called()

    def test_failure_rolls_back_and_closes(self):
        self.cur.fetchone.side_effect = [{}, self.team, {'tr_seq': 9, 'tr_state': '대기'}, None]
        self.cur.execute.side_effect = [None, None, None, None, RuntimeError('mock failure')]
        with self.assertLogs(recruitment.logger, level='ERROR'):
            self.assertEqual(self.decision().status_code, 500)
        self.db.rollback.assert_called_once()
        self.db.commit.assert_not_called()
        self.db.close.assert_called_once()

# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
