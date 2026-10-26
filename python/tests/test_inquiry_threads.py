"""문의 대화 이력 회귀 검증."""
# 수정 일 : 2026-10-26 / 작업자 : 양태건
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.inquiry import insert_inquiry as insert, list_inquiry as listing


def inquiry(seq, parent=None, level=0, **extra):
    return dict(i_seq=seq, i_comment_seq=parent, level=level,
                c_id_seq='member_01', i_option='2', post=f'문의 {seq}',
                i_date='2026-10-26T10:00:00', i_state='0',
                inquiry_detail=None, i_answer_date=None, h_id=None, h_name=None, **extra)


class InquiryThreadTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(insert.router, prefix='/inquiry/insert')
        app.include_router(listing.router, prefix='/inquiry/list')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.lastrowid = 10
        for module in [insert, listing]:
            patcher = patch.object(module, 'connect', return_value=self.connection)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_root_remains_level_zero(self):
        self.cursor.fetchone.return_value = {'1': 1}
        r = self.client.post('/inquiry/insert', json={
            'c_id_seq': 'member_01', 'post': '새 문의', 'i_option': 3})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()['level'], 0)
        self.assertIsNone(r.json()['i_comment_seq'])
        self.assertEqual(self.cursor.execute.call_args.args[1], ('member_01', '새 문의', 0, '3', None))

    def test_reply_increments_parent_depth_and_inherits_option(self):
        for depth in [0, 1, 2, 1500]:
            with self.subTest(depth=depth):
                self.cursor.fetchone.side_effect = [{'1': 1}, inquiry(7, level=depth)]
                r = self.client.post('/inquiry/insert', json={
                    'c_id_seq': 'member_01', 'post': '  추가 답변  ', 'i_comment_seq': 7, 'i_option': 4})
                self.assertEqual(r.status_code, 201, r.text)
                self.assertEqual(r.json()['level'], depth + 1)
                self.assertEqual(r.json()['i_comment_seq'], 7)
                self.assertEqual(self.cursor.execute.call_args.args[1],
                                 ('member_01', '추가 답변', depth + 1, '2', 7))
        self.assertEqual(self.connection.commit.call_count, 4)

    def test_missing_or_other_members_parent_rejected(self):
        for parent, expected in [(None, 404),
                                 (dict(inquiry(7), c_id_seq='other_01'), 403)]:
            self.cursor.fetchone.side_effect = [{'1': 1}, parent]
            r = self.client.post('/inquiry/insert', json={
                'c_id_seq': 'member_01', 'post': '추가 답변', 'i_comment_seq': 7})
            self.assertEqual(r.status_code, expected)
        self.connection.commit.assert_not_called()
        self.assertEqual(self.connection.rollback.call_count, 2)

    def test_missing_member_rejected(self):
        self.cursor.fetchone.return_value = None
        r = self.client.post('/inquiry/insert', json={'c_id_seq': 'member_01', 'post': '문의'})
        self.assertEqual(r.status_code, 404)
        self.connection.rollback.assert_called_once()

    def test_invalid_reply_inputs_rejected_before_db(self):
        for updates in [{'post': '   '}, {'post': '가' * 5001},
                        {'i_comment_seq': 0}, {'i_comment_seq': -1}, {'level': 99}, {'h_id': 'admin'}]:
            payload = dict(c_id_seq='member_01', post='문의', i_comment_seq=7)
            payload.update(updates)
            self.assertEqual(self.client.post('/inquiry/insert', json=payload).status_code, 422)
        self.connection.cursor.assert_not_called()

    def test_insert_failure_rolls_back(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, inquiry(7)]
        self.cursor.execute.side_effect = [None, None, RuntimeError('test failure')]
        with self.assertLogs(insert.logger, level='ERROR'):
            r = self.client.post('/inquiry/insert', json={
                'c_id_seq': 'member_01', 'post': '추가 답변', 'i_comment_seq': 7})
        self.assertEqual(r.status_code, 500)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_groups_multiple_branches_and_preserves_legacy_answer(self):
        root = inquiry(1)
        root.update(inquiry_detail='기존 관리자 답변', h_name='담당자')
        rows = [root, inquiry(2), inquiry(3, 1, 1), inquiry(4, 1, 1), inquiry(5, 3, 2)]
        threads = listing.group_threads(rows)
        self.assertEqual([r['i_seq'] for r in threads], [2, 1])
        self.assertEqual([r['i_seq'] for r in threads[1]['replies']], [3, 5, 4])
        self.assertEqual(threads[1]['inquiry_detail'], '기존 관리자 답변')
        self.assertEqual(threads[1]['reply_count'], 3)

    def test_deep_threads_do_not_use_recursive_calls(self):
        rows = [inquiry(1)] + [inquiry(i, i - 1, i - 1) for i in range(2, 1602)]
        threads = listing.group_threads(rows)
        self.assertEqual(threads[0]['reply_count'], 1600)
        self.assertEqual(threads[0]['replies'][-1]['level'], 1600)

    def test_orphan_is_not_attached_to_unrelated_root(self):
        threads = listing.group_threads([inquiry(1), inquiry(2, 99, 1)])
        self.assertEqual(threads[0]['replies'], [])

    def test_list_keeps_root_total_and_filters_owner_in_query(self):
        self.cursor.fetchone.return_value = {'1': 1}
        self.cursor.fetchall.return_value = [inquiry(1), inquiry(2, 1, 1)]
        r = self.client.get('/inquiry/list', params={'c_id_seq': 'member_01'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['total'], 1)
        self.assertEqual(r.json()['results'][0]['replies'][0]['level'], 1)
        self.assertIn('WHERE q.c_id_seq = %s', self.cursor.execute.call_args.args[0])
        self.assertEqual(self.cursor.execute.call_args.args[1], ('member_01',))


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
