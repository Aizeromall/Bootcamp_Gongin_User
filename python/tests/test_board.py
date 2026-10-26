# 2026-10-26
# 작업자 : 양태건

"""실제 게시글을 생성·삭제하지 않는 게시판 API 회귀 테스트."""
import unittest
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.board import board


class BoardTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(board.router, prefix='/board')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.lastrowid = 10
        self.cursor.rowcount = 1
        patcher = patch.object(board, 'connect', return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)
        self.post = dict(c_id_seq='member_01', board_title='제목', board_content='내용',
                         event_category='축구', board_category='자유게시판')

    def test_list_filters_pagination_and_literal_search(self):
        self.cursor.fetchone.return_value = {'total': 1}
        self.cursor.fetchall.return_value = [{'bulletin_seq': 1, 'board_title': '제목'}]
        r = self.client.get('/board/select', params={
            'event_category': '축구', 'board_category': '자유게시판',
            'keyword': "%'_", 'limit': 5, 'offset': 10})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['total'], 1)
        args = self.cursor.execute.call_args.args
        self.assertEqual(args[1], ('축구', '자유게시판', "%!%'!_%", "%!%'!_%", 5, 10))
        self.assertNotIn("%'_", args[0])
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_detail_increments_view_and_commits(self):
        self.cursor.fetchone.return_value = {'bulletin_seq': 1, 'board_views': 2}
        r = self.client.get('/board/select/1')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['board_views'], 2)
        self.assertIn('board_views = board_views + 1', self.cursor.execute.call_args_list[0].args[0])
        self.connection.commit.assert_called_once()

    def test_missing_detail_rolls_back(self):
        self.cursor.rowcount = 0
        self.assertEqual(self.client.get('/board/select/99').status_code, 404)
        self.connection.rollback.assert_called_once()

    def test_insert_board_trimmed_fields_and_server_defaults(self):
        self.cursor.fetchone.return_value = {'1': 1}
        self.post.update(board_title='  제목  ', board_content=' 내용 ')
        r = self.client.post('/board/insert', json=self.post)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()['bulletin_seq'], 10)
        self.assertEqual(self.cursor.execute.call_args.args[1],
                         ('member_01', '축구', '자유게시판', '제목', '내용'))
        self.connection.commit.assert_called_once()

    def test_invalid_bodies_rejected_before_db(self):
        for updates in [{'board_title': ' '}, {'board_content': ''},
                        {'board_title': '가' * 201}, {'board_views': 100}, {'board_category': '가' * 51}]:
            payload = dict(self.post, **updates)
            self.assertEqual(self.client.post('/board/insert', json=payload).status_code, 422)
        for updates in [{'comment_content': ' '}, {'depth': 99}, {'reply_to_comment_seq': 0}]:
            payload = dict(c_id_seq='member_01', comment_content='댓글')
            payload.update(updates)
            self.assertEqual(self.client.post('/board/comment/insert/1', json=payload).status_code, 422)
        self.connect.assert_not_called()

    def test_nonexistent_member_rejected(self):
        self.cursor.fetchone.return_value = None
        self.assertEqual(self.client.post('/board/insert', json=self.post).status_code, 404)
        self.connection.commit.assert_not_called()

    def test_board_delete_rejects_other_author(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'bulletin_seq': 1, 'c_id_seq': 'other_01'}]
        r = self.client.delete('/board/delete/1', params={'c_id_seq': 'member_01'})
        self.assertEqual(r.status_code, 403)
        self.assertFalse(any('DELETE FROM' in call.args[0] for call in self.cursor.execute.call_args_list))
        self.connection.rollback.assert_called_once()

    def test_board_delete_handles_self_reference_and_children_atomically(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'bulletin_seq': 1, 'c_id_seq': 'member_01'}]
        r = self.client.delete('/board/delete/1', params={'c_id_seq': 'member_01'})
        self.assertEqual(r.status_code, 200, r.text)
        queries = [call.args[0] for call in self.cursor.execute.call_args_list]
        self.assertIn('reply_to_comment_seq = NULL', queries[-3])
        self.assertIn('DELETE FROM board_comment', queries[-2])
        self.assertIn('DELETE FROM board WHERE', queries[-1])
        self.connection.commit.assert_called_once()

    def test_delete_fk_failure_rolls_back_and_closes(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'bulletin_seq': 1, 'c_id_seq': 'member_01'}]
        self.cursor.execute.side_effect = [None, None, None, pymysql.IntegrityError(1451, 'FK')]
        with self.assertLogs(board.logger, level='ERROR'):
            r = self.client.delete('/board/delete/1', params={'c_id_seq': 'member_01'})
        self.assertEqual(r.status_code, 409)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_comment_and_arbitrarily_deep_reply(self):
        for parent, depth in [(None, 0), (7, 1), (7, 1601)]:
            self.cursor.fetchone.side_effect = [
                {'bulletin_seq': 1, 'c_id_seq': 'other_01'}, {'1': 1},
                *([{'comment_seq': 7, 'bulletin_seq': 1, 'depth': depth - 1}] if parent else [])]
            r = self.client.post('/board/comment/insert/1', json={
                'c_id_seq': 'member_01', 'comment_content': ' 댓글 ', 'reply_to_comment_seq': parent})
            self.assertEqual(r.status_code, 201, r.text)
            self.assertEqual(r.json()['depth'], depth)
            self.assertEqual(self.cursor.execute.call_args.args[1], (1, 'member_01', parent, depth, '댓글'))
        self.assertEqual(self.connection.commit.call_count, 3)

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    def test_first_comment_omitted_or_null_parent_needs_no_existing_comments(self):
        for extra in [{}, {"reply_to_comment_seq": None}]:
            self.cursor.reset_mock()
            self.cursor.fetchone.side_effect = [{"bulletin_seq": 1}, {"1": 1}]
            response = self.client.post('/board/comment/insert/1', json={
                "c_id_seq": "member_01", "comment_content": "첫 댓글입니다.", **extra})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["depth"], 0)
            self.assertIsNone(response.json()["reply_to_comment_seq"])
            # 게시글·회원만 확인하고 기존 부모 댓글은 조회하지 않습니다.
            self.assertFalse(any('FROM board_comment' in call.args[0]
                                 for call in self.cursor.execute.call_args_list))
            self.assertEqual(self.cursor.execute.call_args.args[1],
                             (1, 'member_01', None, 0, '첫 댓글입니다.'))

    def test_swagger_default_example_is_parentless_comment(self):
        schema = self.client.get('/openapi.json').json()
        examples = schema['paths']['/board/comment/insert/{bulletin_seq}']['post'][
            'requestBody']['content']['application/json']['examples']
        self.assertNotIn('reply_to_comment_seq', examples['comment']['value'])
        self.assertIn('reply_to_comment_seq', examples['reply']['value'])

    def test_cross_board_and_missing_parent_rejected(self):
        for parent, expected in [(None, 404), ({'bulletin_seq': 2, 'depth': 0}, 409)]:
            self.cursor.fetchone.side_effect = [{'bulletin_seq': 1}, {'1': 1}, parent]
            r = self.client.post('/board/comment/insert/1', json={
                'c_id_seq': 'member_01', 'comment_content': '댓글', 'reply_to_comment_seq': 9})
            self.assertEqual(r.status_code, expected)
        self.connection.commit.assert_not_called()

    def test_comment_delete_preserves_descendants_and_masks_text(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'comment_seq': 7, 'c_id_seq': 'member_01', 'comment_delete_state': 0}]
        r = self.client.delete('/board/comment/delete/7', params={'c_id_seq': 'member_01'})
        self.assertEqual(r.status_code, 200)
        query = self.cursor.execute.call_args.args[0]
        self.assertIn('comment_delete_state = 1', query)
        self.assertNotIn('DELETE FROM', query)
        rows = [dict(comment_seq=1, reply_to_comment_seq=None, depth=0,
                     comment_content='숨겨야 하는 내용', comment_delete_state=1),
                dict(comment_seq=2, reply_to_comment_seq=1, depth=1,
                     comment_content='대댓글', comment_delete_state=0)]
        result = board.order_comments(rows)
        self.assertEqual(result[0]['comment_content'], '삭제된 댓글입니다.')
        self.assertEqual(result[1]['comment_content'], '대댓글')

    def test_comment_delete_author_and_duplicate_guards(self):
        for row, expected in [({'c_id_seq': 'other_01', 'comment_delete_state': 0}, 403),
                              ({'c_id_seq': 'member_01', 'comment_delete_state': 1}, 409), (None, 404)]:
            self.cursor.fetchone.side_effect = [{'1': 1}, row]
            self.assertEqual(self.client.delete('/board/comment/delete/7', params={'c_id_seq': 'member_01'}).status_code, expected)
        self.connection.commit.assert_not_called()

    def test_comment_list_keeps_parent_child_order_and_deep_threads(self):
        rows = [dict(comment_seq=i, reply_to_comment_seq=i - 1 if i > 1 else None,
                     depth=i - 1, comment_content='댓글', comment_delete_state=0) for i in range(1, 1602)]
        self.cursor.fetchone.return_value = {'bulletin_seq': 1}
        self.cursor.fetchall.return_value = rows
        r = self.client.get('/board/comment/select/1')
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['total'], 1601)
        self.assertEqual(r.json()['results'][-1]['depth'], 1600)

    def test_invalid_paths_and_pagination(self):
        for path in ['/board/select/0', '/board/comment/select/-1', '/board/select?limit=101', '/board/select?offset=-1']:
            self.assertEqual(self.client.get(path).status_code, 422)
        self.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
