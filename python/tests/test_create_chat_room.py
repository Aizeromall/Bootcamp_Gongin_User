# 2026-10-27
# 작업자 : 양태건

"""채팅방 생성 전용 API 테스트.

실행: python3 -m unittest discover -s python/tests -p test_create_chat_room.py -v
실제 비밀번호 해시·토큰 검증·FastAPI 요청을 사용하고 MySQL 연결만 모의 처리합니다.
실제 서버에 접속하거나 실제 DB에 채팅방을 생성하지 않습니다.
"""
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from python.FastAPI.main import app
from python.FastAPI.auth.register import hash_password
from python.FastAPI.chat import chat_room


class CreateChatRoomTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 실제 회원과 무관한 테스트 전용 비밀번호입니다.
        cls.password = 'test-password-123'
        cls.password_hash = hash_password(cls.password)

    def setUp(self):
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.login_connection = MagicMock()
        self.login_cursor = self.login_connection.cursor.return_value.__enter__.return_value
        self.login_cursor.fetchone.return_value = {'c_pw': self.password_hash}
        self.create_connection = MagicMock()
        self.create_cursor = self.create_connection.cursor.return_value.__enter__.return_value
        self.create_cursor.fetchone.return_value = {'c_name': '테스트 회원', 'c_team': '공IN FC'}
        self.create_cursor.lastrowid = 101
        patcher = patch.object(chat_room, 'connect', side_effect=[self.login_connection, self.create_connection])
        self.connect = patcher.start()
        self.addCleanup(patcher.stop)

    # 수정 일 : 2026-10-27 / 작업자 : 양태건
    def login(self):
        response = self.client.post('/chat/token', json={
            'c_id_seq': 'test_member_01', 'c_pw': self.password})
        self.assertEqual(response.status_code, 200, response.text)
        return {'Authorization': 'Bearer ' + response.json()['access_token']}

    def test_01_login_then_create_team_named_room_and_owner(self):
        headers = self.login()
        response = self.client.post('/chat/rooms', headers=headers, json={})
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json(), {
            'result': 'OK', 'me_id': 101, 'me_name': '공IN FC',
            'me_state': '활성', 'owner_id': 'test_member_01'})
        writes = self.create_cursor.execute.call_args_list
        self.assertEqual(writes[1].args[1], ('공IN FC',))
        self.assertEqual(writes[2].args[1], ('test_member_01', 101))
        self.create_connection.commit.assert_called_once()
        self.create_connection.rollback.assert_not_called()
        self.login_connection.commit.assert_not_called()
        self.assertEqual(self.connect.call_count, 2)

    def test_02_login_then_create_custom_named_room(self):
        response = self.client.post('/chat/rooms', headers=self.login(), json={'me_name': '친구들과 축구'})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()['me_name'], '친구들과 축구')
        self.assertEqual(response.json()['owner_id'], 'test_member_01')

    def test_03_no_login_rejected_without_any_database_access(self):
        response = self.client.post('/chat/rooms', json={})
        self.assertEqual(response.status_code, 401)
        self.connect.assert_not_called()

    def test_04_wrong_password_does_not_reach_room_creation(self):
        response = self.client.post('/chat/token', json={
            'c_id_seq': 'test_member_01', 'c_pw': 'wrong-password-123'})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(self.connect.call_count, 1)
        self.create_cursor.execute.assert_not_called()

    def test_05_first_participant_failure_rolls_back_room_creation(self):
        self.create_cursor.execute.side_effect = [None, None, RuntimeError('test participant insert failure')]
        with self.assertLogs(chat_room.logger, level='ERROR'):
            response = self.client.post('/chat/rooms', headers=self.login(), json={})
        self.assertEqual(response.status_code, 500)
        self.create_connection.rollback.assert_called_once()
        self.create_connection.commit.assert_not_called()
        self.create_connection.close.assert_called_once()

    def test_06_swagger_offers_executable_request_examples(self):
        operation = self.client.get('/openapi.json').json()['paths']['/chat/rooms']['post']
        examples = operation['requestBody']['content']['application/json']['examples']
        self.assertEqual(examples['team_name']['value'], {})
        self.assertEqual(examples['custom_name']['value'], {'me_name': '우리 팀 채팅방'})
        self.assertEqual(operation['security'], [{'HTTPBearer': []}])
        self.connect.assert_not_called()


if __name__ == '__main__':
    unittest.main()

# 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
