# 2026-10-26
# 작업자 : 양태건

"""실제 게시글을 생성·삭제하지 않는 게시판 API 회귀 테스트."""
import unittest
from unittest.mock import MagicMock, patch

import pymysql
from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.board import board, comment, delete, insert, select, update


# 수정 일 : 2026-10-26 / 작업자 : 양태건
# router 통합 경로를 호출하고 각 기능 파일의 MySQL 연결을 모두 모의 처리합니다.
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
        self.connect = MagicMock(return_value=self.connection)
        for module in [select, insert, update, delete, comment]:
            patcher = patch.object(module, 'connect', self.connect)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.post = dict(c_id_seq='member_01', board_title='제목', board_content='내용',
                         event_category='축구', board_category='자유')

    # 수정 일 : 2026-10-28 / 작업자 : 양태건
    # 실제 DB 없이 드라이버의 빈 튜플 반환을 재현합니다.
    def test_empty_comment_tuple_returns_empty_list(self):
        self.cursor.fetchone.return_value = {'bulletin_seq': 1, 'c_id_seq': 'member_01'}
        self.cursor.fetchall.return_value = ()
        response = self.client.get('/board/comment/select/1')
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {'total': 0, 'results': []})
        self.connection.commit.assert_not_called()
        self.assertTrue(all(call.args[0].lstrip().startswith('SELECT')
                            for call in self.cursor.execute.call_args_list))
        self.connection.close.assert_called_once()

    def test_tuple_comments_keep_parent_child_order(self):
        child = dict(comment_seq=2, reply_to_comment_seq=1, comment_delete_state=0, comment_content='답글')
        parent = dict(comment_seq=1, reply_to_comment_seq=None, comment_delete_state=0, comment_content='댓글')
        result = comment.order_comments((child, parent))
        self.assertEqual([row['comment_seq'] for row in result], [1, 2])

    def test_list_filters_pagination_and_literal_search(self):
        self.cursor.fetchone.return_value = {'total': 1}
        self.cursor.fetchall.return_value = [{'bulletin_seq': 1, 'board_title': '제목'}]
        r = self.client.get('/board/select', params={
            'event_category': '축구', 'board_category': '자유',
            'keyword': "%'_", 'limit': 5, 'offset': 10})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['total'], 1)
        args = self.cursor.execute.call_args.args
        self.assertEqual(args[1], ('축구', '자유', "%!%'!_%", "%!%'!_%", 5, 10))
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
                         ('member_01', '축구', '자유', '제목', '내용'))
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
        self.assertIn('DELETE FROM board_a_write', queries[-2])
        self.assertIn('comment_seq > 0', queries[-2])
        self.assertIn('DELETE FROM board_a_write', queries[-1])
        self.assertIn('comment_seq = 0', queries[-1])
        self.connection.commit.assert_called_once()

    def test_delete_fk_failure_rolls_back_and_closes(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'bulletin_seq': 1, 'c_id_seq': 'member_01'}]
        self.cursor.execute.side_effect = [None, None, None, pymysql.IntegrityError(1451, 'FK')]
        with self.assertLogs(delete.logger, level='ERROR'):
            r = self.client.delete('/board/delete/1', params={'c_id_seq': 'member_01'})
        self.assertEqual(r.status_code, 409)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_comment_and_arbitrarily_deep_reply(self):
        for parent, depth in [(None, 0), (7, 1), (7, 1601)]:
            self.cursor.fetchone.side_effect = [
                {'bulletin_seq': 1, 'c_id_seq': 'other_01'}, {'1': 1},
                *([{'comment_seq': 7, 'bulletin_seq': 1, 'depth': depth - 1}] if parent else []),
                {'next_seq': 1}]
            r = self.client.post('/board/comment/insert/1', json={
                'c_id_seq': 'member_01', 'comment_content': ' 댓글 ', 'reply_to_comment_seq': parent})
            self.assertEqual(r.status_code, 201, r.text)
            self.assertEqual(r.json()['depth'], depth)
            self.assertEqual(self.cursor.execute.call_args.args[1], (1, 1, 'member_01', parent, depth, '댓글'))
        self.assertEqual(self.connection.commit.call_count, 3)

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    def test_first_comment_omitted_or_null_parent_needs_no_existing_comments(self):
        for extra in [{}, {"reply_to_comment_seq": None}]:
            self.cursor.reset_mock()
            self.cursor.fetchone.side_effect = [{"bulletin_seq": 1}, {"1": 1}, {"next_seq": 1}]
            response = self.client.post('/board/comment/insert/1', json={
                "c_id_seq": "member_01", "comment_content": "첫 댓글입니다.", **extra})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()["depth"], 0)
            self.assertIsNone(response.json()["reply_to_comment_seq"])
            # 게시글·회원만 확인하고 기존 부모 댓글은 조회하지 않습니다.
            self.assertFalse(any('AND comment_seq = %s' in call.args[0]
                                 for call in self.cursor.execute.call_args_list))
            self.assertEqual(self.cursor.execute.call_args.args[1],
                             (1, 1, 'member_01', None, 0, '첫 댓글입니다.'))

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
        r = self.client.delete('/board/comment/delete/7', params={'c_id_seq': 'member_01', 'bulletin_seq': 1})
        self.assertEqual(r.status_code, 200)
        query = self.cursor.execute.call_args.args[0]
        self.assertIn('comment_delete_state = 1', query)
        self.assertNotIn('DELETE FROM', query)
        rows = [dict(comment_seq=1, reply_to_comment_seq=None, depth=0,
                     comment_content='숨겨야 하는 내용', comment_delete_state=1),
                dict(comment_seq=2, reply_to_comment_seq=1, depth=1,
                     comment_content='대댓글', comment_delete_state=0)]
        result = comment.order_comments(rows)
        self.assertEqual(result[0]['comment_content'], '삭제된 댓글입니다.')
        self.assertEqual(result[1]['comment_content'], '대댓글')

    def test_comment_delete_author_and_duplicate_guards(self):
        for row, expected in [({'c_id_seq': 'other_01', 'comment_delete_state': 0}, 403),
                              ({'c_id_seq': 'member_01', 'comment_delete_state': 1}, 409), (None, 404)]:
            self.cursor.fetchone.side_effect = [{'1': 1}, row]
            self.assertEqual(self.client.delete('/board/comment/delete/7', params={'c_id_seq': 'member_01', 'bulletin_seq': 1}).status_code, expected)
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

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    def test_update_board_changes_content_and_preserves_metadata(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'bulletin_seq': 1, 'c_id_seq': 'member_01'}]
        self.cursor.rowcount = 0  # 동일 내용 재전송도 404로 오인하지 않습니다.
        r = self.client.put('/board/update/1', json=dict(self.post, board_title=' 수정 제목 '))
        self.assertEqual(r.status_code, 200, r.text)
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(params, ('축구', '자유', '수정 제목', '내용', 1))
        self.assertNotIn('board_views', sql)
        self.assertNotIn('board_date', sql)
        self.assertNotIn('board_comment', sql)
        self.connection.commit.assert_called_once()

    def test_update_board_checks_missing_board_and_author(self):
        for row, expected in [(None, 404), ({'c_id_seq': 'other_01'}, 403)]:
            self.cursor.fetchone.side_effect = [{'1': 1}, row]
            r = self.client.put('/board/update/1', json=self.post)
            self.assertEqual(r.status_code, expected)
        self.connection.commit.assert_not_called()
        self.assertEqual(self.connection.rollback.call_count, 2)

    def test_update_comment_preserves_parent_and_depth(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {
            'comment_seq': 7, 'c_id_seq': 'member_01', 'comment_delete_state': 0}]
        self.cursor.rowcount = 0
        r = self.client.put('/board/comment/update/7?bulletin_seq=1', json={
            'c_id_seq': 'member_01', 'comment_content': ' 수정 댓글 '})
        self.assertEqual(r.status_code, 200, r.text)
        sql, params = self.cursor.execute.call_args.args
        self.assertEqual(params, ('수정 댓글', 1, 7))
        self.assertNotIn('reply_to_comment_seq', sql)
        self.assertNotIn('depth', sql)
        self.connection.commit.assert_called_once()

    def test_update_comment_rejects_missing_other_author_and_deleted(self):
        for row, expected in [(None, 404),
                              ({'c_id_seq': 'other_01', 'comment_delete_state': 0}, 403),
                              ({'c_id_seq': 'member_01', 'comment_delete_state': 1}, 409)]:
            self.cursor.fetchone.side_effect = [{'1': 1}, row]
            r = self.client.put('/board/comment/update/7?bulletin_seq=1', json={
                'c_id_seq': 'member_01', 'comment_content': '수정 댓글'})
            self.assertEqual(r.status_code, expected)
        self.connection.commit.assert_not_called()

    def test_update_validation_rejects_invalid_and_relationship_changes(self):
        for updates in [{'board_title': ' '}, {'board_views': 100}, {'board_content': '가' * 10001}]:
            self.assertEqual(self.client.put('/board/update/1', json=dict(self.post, **updates)).status_code, 422)
        for updates in [{'comment_content': ' '}, {'depth': 9}, {'reply_to_comment_seq': 7}, {'comment_delete_state': 0}]:
            payload = dict(c_id_seq='member_01', comment_content='수정 댓글')
            payload.update(updates)
            self.assertEqual(self.client.put('/board/comment/update/7?bulletin_seq=1', json=payload).status_code, 422)
        self.connect.assert_not_called()

    def test_update_failure_rolls_back(self):
        self.cursor.fetchone.side_effect = [{'1': 1}, {'c_id_seq': 'member_01'}]
        self.cursor.execute.side_effect = [None, None, RuntimeError('test failure')]
        with self.assertLogs(update.logger, level='ERROR'):
            r = self.client.put('/board/update/1', json=self.post)
        self.assertEqual(r.status_code, 500)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_routes_belong_to_named_modules(self):
        expected = {
            ('GET', '/board/select'): 'select',
            ('GET', '/board/select/{bulletin_seq}'): 'select',
            ('POST', '/board/insert'): 'insert',
            ('PUT', '/board/update/{bulletin_seq}'): 'update',
            ('DELETE', '/board/delete/{bulletin_seq}'): 'delete',
            ('GET', '/board/comment/select/{bulletin_seq}'): 'comment',
            ('POST', '/board/comment/insert/{bulletin_seq}'): 'comment',
            ('PUT', '/board/comment/update/{comment_seq}'): 'comment',
            ('DELETE', '/board/comment/delete/{comment_seq}'): 'comment',
        }
        from importlib import import_module
        schema = self.client.get('/openapi.json').json()['paths']
        for name in ['select', 'insert', 'update', 'delete', 'comment']:
            module = import_module(f'python.FastAPI.board.{name}')
            for route in module.router.routes:
                for method in route.methods:
                    key = (method, '/board' + route.path)
                    self.assertIn(key, expected)
                    self.assertIn(method.lower(), schema[key[1]])
                    self.assertEqual(route.endpoint.__module__.split('.')[-1], expected.pop(key))
        self.assertEqual(expected, {})

    def test_web_cors_allows_update_method(self):
        from python.FastAPI.main import app
        with TestClient(app) as client:
            response = client.options('/board/update/1', headers={
                'Origin': 'http://localhost:3000', 'Access-Control-Request-Method': 'PUT'})
        self.assertEqual(response.status_code, 200)
        self.assertIn('PUT', response.headers['access-control-allow-methods'])
        self.connect.assert_not_called()

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    def test_single_table_queries_separate_posts_from_comments(self):
        self.cursor.fetchone.return_value = {'total': 1}
        self.cursor.fetchall.return_value = []
        self.assertEqual(self.client.get('/board/select').status_code, 200)
        for call in self.cursor.execute.call_args_list:
            self.assertIn('board_a_write', call.args[0])
            self.assertIn('b.comment_seq = 0', call.args[0])
        self.cursor.reset_mock()
        self.cursor.fetchone.return_value = {'bulletin_seq': 1}
        self.assertEqual(self.client.get('/board/comment/select/1').status_code, 200)
        self.assertIn('q.comment_seq > 0', self.cursor.execute.call_args.args[0])

    def test_comment_update_and_delete_require_composite_key(self):
        payload = {'c_id_seq': 'member_01', 'comment_content': '수정 댓글'}
        self.assertEqual(self.client.put('/board/comment/update/1', json=payload).status_code, 422)
        self.assertEqual(self.client.delete('/board/comment/delete/1', params={'c_id_seq': 'member_01'}).status_code, 422)
        self.connect.assert_not_called()

    def test_same_comment_number_is_updated_only_in_requested_board(self):
        for board_id in [1, 2]:
            self.cursor.fetchone.side_effect = [{'1': 1}, {
                'comment_seq': 7, 'c_id_seq': 'member_01', 'comment_delete_state': 0}]
            response = self.client.put(f'/board/comment/update/7?bulletin_seq={board_id}', json={
                'c_id_seq': 'member_01', 'comment_content': '수정 댓글'})
            self.assertEqual(response.status_code, 200)
            sql, params = self.cursor.execute.call_args.args
            self.assertIn('WHERE bulletin_seq = %s AND comment_seq = %s', sql)
            self.assertEqual(params, ('수정 댓글', board_id, 7))

    def test_comment_number_comes_from_locked_board_not_auto_increment(self):
        self.cursor.fetchone.side_effect = [{'bulletin_seq': 2}, {'1': 1}, {'next_seq': 12}]
        self.cursor.lastrowid = 999
        response = self.client.post('/board/comment/insert/2', json={
            'c_id_seq': 'member_01', 'comment_content': '새 댓글'})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()['comment_seq'], 12)
        calls = self.cursor.execute.call_args_list
        self.assertIn('comment_seq = 0 FOR UPDATE', calls[0].args[0])
        self.assertIn('MAX(comment_seq)', calls[-2].args[0])
        self.assertEqual(calls[-1].args[1], (2, 12, 'member_01', None, 0, '새 댓글'))

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    def test_allowed_categories_for_post_and_update(self):
        from python.FastAPI.board.insert import InsertBoardRequest
        from python.FastAPI.board.update import UpdateBoardRequest
        for event in ['축구', '배구', '야구', '농구']:
            for category in ['팀원모집', '매칭신청', '후기', '자유']:
                for model in [InsertBoardRequest, UpdateBoardRequest]:
                    value = model(**dict(self.post, event_category=event, board_category=category))
                    self.assertEqual(value.event_category, event)
                    self.assertEqual(value.board_category, category)

    def test_invalid_or_missing_categories_rejected_before_db(self):
        for updates in [{'event_category': '테니스'}, {'board_category': '자유게시판'},
                        {'event_category': None}, {'board_category': None}]:
            payload = dict(self.post, **updates)
            self.assertEqual(self.client.post('/board/insert', json=payload).status_code, 422)
            self.assertEqual(self.client.put('/board/update/1', json=payload).status_code, 422)
        for missing in ['event_category', 'board_category']:
            payload = dict(self.post)
            del payload[missing]
            self.assertEqual(self.client.post('/board/insert', json=payload).status_code, 422)
        for params in [{'event_category': '테니스'}, {'board_category': '모집완료'}]:
            self.assertEqual(self.client.get('/board/select', params=params).status_code, 422)
        self.connect.assert_not_called()

    # 수정 일 : 2026-10-26 / 작업자 : 양태건
    def test_matched_post_rejects_comments_and_replies(self):
        for parent in [None, 7]:
            self.cursor.reset_mock()
            self.cursor.fetchone.side_effect = [
                {'bulletin_seq': 1, 'board_category': '매칭신청', 'board_content': '[예약번호:15]\n매칭 모집'},
                {'1': 1}, {'r_check': 1},
            ]
            response = self.client.post('/board/comment/insert/1', json={
                'c_id_seq': 'member_01', 'comment_content': '댓글', 'reply_to_comment_seq': parent})
            self.assertEqual(response.status_code, 409, response.text)
            self.assertIn('매칭이 성사된', response.json()['detail'])
            self.assertFalse(any('INSERT INTO' in call.args[0] for call in self.cursor.execute.call_args_list))
            self.assertIn('FOR UPDATE', self.cursor.execute.call_args_list[0].args[0])
            self.assertEqual(self.cursor.execute.call_args.args[1], (15,))
        self.connection.commit.assert_not_called()
        self.assertEqual(self.connection.rollback.call_count, 2)

    def test_unmatched_post_accepts_comments_and_replies(self):
        for parent in [None, 7]:
            self.cursor.fetchone.side_effect = [
                {'bulletin_seq': 1, 'board_category': '매칭신청', 'board_content': '[예약번호:15]'},
                {'1': 1}, {'r_check': 0},
                *([{'bulletin_seq': 1, 'depth': 0}] if parent else []),
                {'next_seq': 8},
            ]
            response = self.client.post('/board/comment/insert/1', json={
                'c_id_seq': 'member_01', 'comment_content': '댓글', 'reply_to_comment_seq': parent})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertEqual(response.json()['depth'], 1 if parent else 0)
        self.assertEqual(self.connection.commit.call_count, 2)

    def test_other_categories_and_unlinked_posts_remain_commentable(self):
        for category in ['팀원모집', '후기', '자유', '매칭신청']:
            self.cursor.reset_mock()
            self.cursor.fetchone.side_effect = [
                {'bulletin_seq': 1, 'board_category': category, 'board_content': '일반 게시글'},
                {'1': 1}, {'next_seq': 1},
            ]
            response = self.client.post('/board/comment/insert/1', json={
                'c_id_seq': 'member_01', 'comment_content': '댓글'})
            self.assertEqual(response.status_code, 201, response.text)
            self.assertFalse(any('FROM reservation' in call.args[0] for call in self.cursor.execute.call_args_list))

    def test_missing_linked_reservation_does_not_allow_unverified_comment(self):
        self.cursor.fetchone.side_effect = [
            {'bulletin_seq': 1, 'board_category': '매칭신청', 'board_content': '[예약번호:15]'},
            {'1': 1}, None,
        ]
        response = self.client.post('/board/comment/insert/1', json={
            'c_id_seq': 'member_01', 'comment_content': '댓글'})
        self.assertEqual(response.status_code, 409)
        self.connection.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-26 / 작업자 : 양태건

# 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
