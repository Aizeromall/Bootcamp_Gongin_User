# 2026-10-27
# 작업자 : 양태건

"""채팅 인증·방 관리·메시지·WebSocket을 실제 DB 쓰기 없이 검증합니다."""
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import jwt
import pymysql
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from python.FastAPI.chat import chat_router
from python.FastAPI.chat import socket_message as messages, chat_room as rooms
from python.FastAPI.chat import chat_login_request as login_api


def token(member='owner_01', expired=False):
    now = datetime.now(timezone.utc)
    return jwt.encode({'sub': member, 'iat': now - timedelta(hours=2) if expired else now,
                       'exp': now - timedelta(seconds=1) if expired else now + timedelta(minutes=10),
                       'aud': rooms.TOKEN_AUDIENCE, 'iss': rooms.TOKEN_ISSUER},
                      rooms.TOKEN_SECRET, algorithm='HS256')


class ChatTests(unittest.TestCase):
    def setUp(self):
        app = FastAPI()
        app.include_router(chat_router)
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.lastrowid = 7
        self.cursor.rowcount = 1
        self.room = {'me_id': 7, 'me_name': '우리 팀', 'me_state': '활성', 'owner_id': 'owner_01'}
        patcher = patch.object(rooms, 'connect', return_value=self.connection)
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)
        self.headers = {'Authorization': 'Bearer ' + token()}
        patcher = patch.object(messages, 'manager', messages.ConnectionManager())
        patcher.start()
        self.addCleanup(patcher.stop)

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_chat_login_issues_verified_member_token(self):
        self.cursor.fetchone.return_value = {'c_pw': 'hashed'}
        with patch.object(login_api, 'verify_password', return_value=True) as verify:
            r = self.client.post('/chat/token', json={'c_id_seq': 'owner_01', 'c_pw': 'password123'})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(rooms.decode_chat_token(r.json()['access_token'])['sub'], 'owner_01')
        verify.assert_called_once_with('password123', 'hashed')
        self.connection.commit.assert_not_called()

    def test_bad_login_and_deleted_member_do_not_issue_token(self):
        for row in [None, {'c_pw': 'hashed'}]:
            self.cursor.fetchone.return_value = row
            with patch.object(login_api, 'verify_password', return_value=False):
                self.assertEqual(self.client.post('/chat/token', json={
                    'c_id_seq': 'owner_01', 'c_pw': 'password123'}).status_code, 401)

    def test_missing_expired_forged_tokens_rejected_before_db(self):
        for headers in [{}, {'Authorization': 'Bearer invalid'},
                        {'Authorization': 'Bearer ' + token(expired=True)}]:
            self.assertEqual(self.client.get('/chat/rooms', headers=headers).status_code, 401)
        self.connect.assert_not_called()

    def test_create_room_uses_team_name_and_registers_owner_first(self):
        self.cursor.fetchone.return_value = {'c_name': '회원', 'c_team': '우리 팀'}
        r = self.client.post('/chat/rooms', json={}, headers=self.headers)
        self.assertEqual(r.status_code, 201, r.text)
        self.assertEqual(r.json()['me_name'], '우리 팀')
        self.assertEqual(r.json()['owner_id'], 'owner_01')
        calls = self.cursor.execute.call_args_list
        self.assertIn('INSERT INTO messenger', calls[1].args[0])
        self.assertIn('INSERT INTO participate', calls[2].args[0])
        self.assertEqual(calls[2].args[1], ('owner_01', 7))
        self.connection.commit.assert_called_once()

    def test_room_name_override_and_no_team_fallback(self):
        self.cursor.fetchone.return_value = {'c_name': '회원', 'c_team': '무소속'}
        self.assertEqual(self.client.post('/chat/rooms', json={}, headers=self.headers).json()['me_name'], '회원님의 채팅방')
        self.assertEqual(self.client.post('/chat/rooms', json={'me_name': '친구들'}, headers=self.headers).json()['me_name'], '친구들')

    def test_create_partial_failure_rolls_back_room_and_owner(self):
        self.cursor.fetchone.return_value = {'c_name': '회원', 'c_team': '우리 팀'}
        self.cursor.execute.side_effect = [None, None, RuntimeError('test failure')]
        with self.assertLogs(rooms.logger, level='ERROR'):
            self.assertEqual(self.client.post('/chat/rooms', json={}, headers=self.headers).status_code, 500)
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_room_detail_requires_participation_and_active_state(self):
        for room, membership, expected in [(None, None, 404), (self.room, None, 403),
                                           (dict(self.room, me_state='종료'), {'participate_seq': 1}, 409)]:
            self.cursor.fetchone.side_effect = [room, membership] if room else [None]
            self.assertEqual(self.client.get('/chat/rooms/7', headers=self.headers).status_code, expected)

    def test_owner_can_invite_and_duplicate_invites_are_idempotent(self):
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}, {'1': 1}, None,
                                           {'1': 1}, {'1': 1}]
        r = self.client.post('/chat/rooms/7/invite', json={
            'member_ids': ['other_01', 'other_01', 'owner_01']}, headers=self.headers)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()['invited'], ['other_01'])
        self.assertEqual(r.json()['already_joined'], ['owner_01'])
        inserts = [call for call in self.cursor.execute.call_args_list if 'INSERT INTO participate' in call.args[0]]
        self.assertEqual(len(inserts), 1)
        self.connection.commit.assert_called_once()

    def test_non_owner_cannot_invite_or_close(self):
        headers = {'Authorization': 'Bearer ' + token('other_01')}
        for path, method in [('/chat/rooms/7/invite', 'post'), ('/chat/rooms/7', 'delete')]:
            self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 2}]
            r = self.client.post(path, json={'member_ids': ['new_01']}, headers=headers) if method == 'post' else self.client.delete(path, headers=headers)
            self.assertEqual(r.status_code, 403)
        self.connection.commit.assert_not_called()

    def test_invalid_invitation_rolls_back_preceding_invites(self):
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}, {'1': 1}, None, None]
        r = self.client.post('/chat/rooms/7/invite', json={'member_ids': ['valid_01', 'missing_01']}, headers=self.headers)
        self.assertEqual(r.status_code, 404)
        self.connection.commit.assert_not_called()
        self.connection.rollback.assert_called_once()

    def test_owner_cannot_leave_and_non_owner_can_leave(self):
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}]
        self.assertEqual(self.client.delete('/chat/rooms/7/leave', headers=self.headers).status_code, 409)
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 2}]
        headers = {'Authorization': 'Bearer ' + token('other_01')}
        self.assertEqual(self.client.delete('/chat/rooms/7/leave', headers=headers).status_code, 200)
        self.assertEqual(self.cursor.execute.call_args.args[1], (7, 'other_01'))

    def test_close_changes_state_without_removing_messages_or_owner(self):
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}]
        r = self.client.delete('/chat/rooms/7', headers=self.headers)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['me_state'], '종료')
        self.assertIn("SET me_state = '종료'", self.cursor.execute.call_args.args[0])
        self.assertFalse(any('DELETE FROM' in c.args[0] for c in self.cursor.execute.call_args_list))

    def test_only_my_rooms_are_selected(self):
        self.cursor.fetchall.return_value = [self.room]
        self.assertEqual(self.client.get('/chat/rooms', headers=self.headers).status_code, 200)
        self.assertEqual(self.cursor.execute.call_args.args[1], ('owner_01', 20, 0))
        self.assertIn('ORDER BY owner.participate_seq LIMIT 1', self.cursor.execute.call_args.args[0])

    def test_invalid_bodies_cannot_spoof_owner_or_sender(self):
        for payload in [{'me_name': ' '}, {'owner_id': 'other_01'}, {'me_name': '가' * 101}]:
            self.assertEqual(self.client.post('/chat/rooms', json=payload, headers=self.headers).status_code, 422)
        self.assertEqual(self.client.post('/chat/rooms/7/invite', json={'member_ids': [' ']}, headers=self.headers).status_code, 422)
        self.connect.assert_not_called()

    def test_recent_and_after_message_history_order(self):
        for query, source, expected in [('', [{'s_me_id': 3}, {'s_me_id': 2}], [2, 3]),
                                        ('?after_id=1', [{'s_me_id': 2}, {'s_me_id': 3}], [2, 3])]:
            self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}]
            self.cursor.fetchall.return_value = source
            r = self.client.get('/chat/rooms/7/messages' + query, headers=self.headers)
            self.assertEqual(r.status_code, 200)
            self.assertEqual([m['s_me_id'] for m in r.json()['results']], expected)
        self.connection.commit.assert_not_called()

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_empty_mysql_tuple_history_returns_empty_list(self):
        for query in ['', '?after_id=0', '?before_id=10']:
            self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}]
            self.cursor.fetchall.return_value = ()
            response = self.client.get('/chat/rooms/7/messages' + query, headers=self.headers)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()['results'], [])
        self.connection.commit.assert_not_called()

    def test_mysql_tuple_history_reverses_without_error(self):
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}]
        self.cursor.fetchall.return_value = ({'s_me_id': 3}, {'s_me_id': 2})
        response = self.client.get('/chat/rooms/7/messages', headers=self.headers)
        self.assertEqual(response.status_code, 200)
        self.assertEqual([row['s_me_id'] for row in response.json()['results']], [2, 3])

    def test_history_nonparticipant_and_conflicting_cursors_rejected(self):
        self.cursor.fetchone.side_effect = [self.room, None]
        self.assertEqual(self.client.get('/chat/rooms/7/messages', headers=self.headers).status_code, 403)
        self.assertEqual(self.client.get('/chat/rooms/7/messages?after_id=1&before_id=5', headers=self.headers).status_code, 422)

    def test_store_uses_authenticated_sender_and_commits_before_return(self):
        message = {'s_me_id': 7, 'c_id_seq': 'owner_01', 's_me_content': '안녕'}
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}, message]
        self.cursor.fetchall.return_value = [{'c_id_seq': 'owner_01'}]
        result, participants = messages.store_message(7, 'owner_01', '안녕')
        self.assertEqual(result, message)
        self.assertEqual(participants, {'owner_01'})
        self.assertEqual(self.cursor.execute.call_args_list[2].args[1], ('owner_01', 7, '안녕'))
        self.connection.commit.assert_called_once()

    def test_message_store_failure_rolls_back(self):
        self.cursor.fetchone.side_effect = [self.room, {'participate_seq': 1}]
        self.cursor.execute.side_effect = [None, None, pymysql.OperationalError(2006, 'test')]
        with self.assertLogs(rooms.logger, level='ERROR'):
            with self.assertRaises(HTTPException):
                messages.store_message(7, 'owner_01', '안녕')
        self.connection.rollback.assert_called_once()
        self.connection.commit.assert_not_called()

    def test_websocket_two_members_receive_saved_message(self):
        stored = {'s_me_id': 10, 'me_id': 7, 'c_id_seq': 'owner_01', 's_me_content': '안녕'}
        with patch.object(messages, 'check_socket_access'), \
             patch.object(messages, 'store_message', return_value=(stored, {'owner_01', 'other_01'})) as store, \
             patch.object(messages, 'active_participants', return_value={'owner_01', 'other_01'}), self.client:
            with self.client.websocket_connect('/chat/ws/7') as owner:
                owner.send_json({'type': 'auth', 'access_token': token()})
                self.assertEqual(owner.receive_json()['type'], 'ready')
                with self.client.websocket_connect('/chat/ws/7') as other:
                    other.send_json({'type': 'auth', 'access_token': token('other_01')})
                    self.assertEqual(other.receive_json()['type'], 'ready')
                    owner.send_json({'type': 'message', 'content': ' 안녕 '})
                    self.assertEqual(owner.receive_json()['message'], stored)
                    self.assertEqual(other.receive_json()['message'], stored)
                    store.assert_called_once_with(7, 'owner_01', '안녕')
        self.assertEqual(messages.manager.rooms, {})

    def test_websocket_does_not_broadcast_across_rooms(self):
        def store(room, member, content):
            return {'s_me_id': room, 'me_id': room, 's_me_content': content}, {member}
        with patch.object(messages, 'check_socket_access'), patch.object(messages, 'store_message', side_effect=store), \
             patch.object(messages, 'active_participants', side_effect=lambda room: {'owner_01'} if room == 7 else {'other_01'}), self.client:
            with self.client.websocket_connect('/chat/ws/7') as first, self.client.websocket_connect('/chat/ws/8') as second:
                first.send_json({'type': 'auth', 'access_token': token()})
                second.send_json({'type': 'auth', 'access_token': token('other_01')})
                first.receive_json(); second.receive_json()
                first.send_json({'type': 'message', 'content': '7번 방'})
                self.assertEqual(first.receive_json()['message']['me_id'], 7)
                second.send_json({'type': 'message', 'content': '8번 방'})
                self.assertEqual(second.receive_json()['message']['me_id'], 8)

    def test_websocket_bad_token_and_nonmember_rejected(self):
        with self.client:
            with self.client.websocket_connect('/chat/ws/7') as ws:
                ws.send_json({'type': 'auth', 'access_token': 'invalid'})
                with self.assertRaises(WebSocketDisconnect):
                    ws.receive_json()
            with patch.object(messages, 'check_socket_access', side_effect=HTTPException(403, '미참여')):
                with self.client.websocket_connect('/chat/ws/7') as ws:
                    ws.send_json({'type': 'auth', 'access_token': token()})
                    with self.assertRaises(WebSocketDisconnect):
                        ws.receive_json()

    def test_websocket_invalid_content_and_sender_spoof_never_saved(self):
        with patch.object(messages, 'check_socket_access'), patch.object(messages, 'store_message') as store, self.client:
            with self.client.websocket_connect('/chat/ws/7') as ws:
                ws.send_json({'type': 'auth', 'access_token': token()})
                ws.receive_json()
                for data in [{'type': 'message', 'content': ' '}, {'type': 'message', 'content': '가' * 10001},
                             {'type': 'message', 'content': '안녕', 'c_id_seq': 'other_01'}]:
                    ws.send_json(data)
                    self.assertEqual(ws.receive_json()['type'], 'error')
                store.assert_not_called()

    def test_websocket_failed_save_does_not_publish(self):
        with patch.object(messages, 'check_socket_access'), \
             patch.object(messages, 'store_message', side_effect=HTTPException(500, '저장 실패')), self.client:
            with self.client.websocket_connect('/chat/ws/7') as ws:
                ws.send_json({'type': 'auth', 'access_token': token()})
                ws.receive_json()
                ws.send_json({'type': 'message', 'content': '안녕'})
                with self.assertRaises(WebSocketDisconnect) as error:
                    ws.receive_json()
                self.assertEqual(error.exception.code, 1011)

    def test_departed_socket_does_not_receive_new_messages(self):
        stored = {'s_me_id': 1, 'me_id': 7, 's_me_content': '안녕'}
        with patch.object(messages, 'check_socket_access'), \
             patch.object(messages, 'store_message', return_value=(stored, {'owner_01', 'other_01'})), \
             patch.object(messages, 'active_participants', return_value={'owner_01'}), self.client:
            with self.client.websocket_connect('/chat/ws/7') as owner, self.client.websocket_connect('/chat/ws/7') as other:
                owner.send_json({'type': 'auth', 'access_token': token()}); owner.receive_json()
                other.send_json({'type': 'auth', 'access_token': token('other_01')}); other.receive_json()
                owner.send_json({'type': 'message', 'content': '안녕'})
                owner.receive_json()
                with self.assertRaises(WebSocketDisconnect):
                    other.receive_json()

    def test_socket_closure_or_departure_prevents_further_save(self):
        for room, membership, expected in [(dict(self.room, me_state='종료'), {'participate_seq': 1}, 409),
                                            (self.room, None, 403)]:
            self.cursor.reset_mock()
            self.cursor.fetchone.side_effect = [room, membership]
            with self.assertRaises(HTTPException) as error:
                messages.store_message(7, 'owner_01', '메시지')
            self.assertEqual(error.exception.status_code, expected)
            self.assertFalse(any('INSERT INTO send_message' in c.args[0] for c in self.cursor.execute.call_args_list))
        self.connection.commit.assert_not_called()

    def test_forged_algorithm_audience_and_expired_socket_token(self):
        now = datetime.now(timezone.utc)
        claims = {'sub': 'owner_01', 'iat': now, 'exp': now + timedelta(minutes=1),
                  'aud': 'other-service', 'iss': rooms.TOKEN_ISSUER}
        for encoded in [jwt.encode(claims, rooms.TOKEN_SECRET, algorithm='HS256'),
                        jwt.encode(dict(claims, aud=rooms.TOKEN_AUDIENCE), rooms.TOKEN_SECRET, algorithm='HS384')]:
            with self.assertRaises(HTTPException):
                rooms.decode_chat_token(encoded)
        with self.client:
            with self.client.websocket_connect('/chat/ws/7') as ws:
                ws.send_json({'type': 'auth', 'access_token': token(expired=True)})
                with self.assertRaises(WebSocketDisconnect) as error:
                    ws.receive_json()
                self.assertEqual(error.exception.code, 1008)
        self.connect.assert_not_called()

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_chat_classes_have_one_definition_per_file(self):
        import ast
        from pathlib import Path
        folder = Path(messages.__file__).parent
        expected = {
            'ChatRequest': 'chat_request.py', 'ChatLoginRequest': 'chat_login_request.py',
            'CreateRoomRequest': 'create_room_request.py', 'InviteRequest': 'invite_request.py',
            'SocketAuth': 'socket_auth.py', 'SocketMessage': 'socket_message.py',
            'ConnectionManager': 'connection_manager.py',
        }
        found = {}
        for path in folder.glob('*.py'):
            classes = [node for node in ast.walk(ast.parse(path.read_text())) if isinstance(node, ast.ClassDef)]
            self.assertLessEqual(len(classes), 1, path.name)
            for definition in classes:
                found[definition.name] = path.name
        self.assertEqual(found, expected)

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def test_request_classes_and_their_routers_are_in_same_module(self):
        from importlib import import_module
        import inspect
        expected = {
            'chat_login_request': ('ChatLoginRequest', '/token'),
            'create_room_request': ('CreateRoomRequest', '/rooms'),
            'invite_request': ('InviteRequest', '/rooms/{me_id}/invite'),
        }
        for name, (class_name, path) in expected.items():
            module = import_module('python.FastAPI.chat.' + name)
            route = next(route for route in module.router.routes if route.path == path)
            self.assertEqual(route.endpoint.__module__, module.__name__)
            self.assertIs(inspect.signature(route.endpoint).parameters['payload'].annotation,
                          getattr(module, class_name))
        route = next(route for route in messages.router.routes if route.path == '/ws/{me_id}')
        self.assertEqual(route.endpoint.__module__, messages.SocketMessage.__module__)

    def test_main_exposes_chat_http_and_websocket_routes(self):
        from python.FastAPI.main import app
        paths = app.openapi()['paths']
        self.assertIn('post', paths['/chat/token'])
        self.assertIn('post', paths['/chat/rooms'])
        self.assertIn('get', paths['/chat/rooms/{me_id}/messages'])


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
