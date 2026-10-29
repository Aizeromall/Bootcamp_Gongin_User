# 작업자 : 최현준
# 최초 작업 일 : 2026-10-28
"""공급자·DB에 연결하지 않는 모바일 인증/회원 권한 회귀 검사."""
import unittest
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.auth import kakao, naver
from python.FastAPI.auth.token import current_account
from python.FastAPI.chat import chat_login_request as chat
from python.FastAPI.chat.chat_room import decode_chat_token
from python.FastAPI.notification import worker


def test_kakao_mobile_validates_app_and_subject_before_db():
    app = FastAPI()
    app.include_router(kakao.router)
    with TestClient(app) as api, patch.object(kakao, 'signing_key'), \
            patch.object(kakao, 'setting', return_value='123'), \
            patch.object(kakao, 'provider_request', return_value={'id': 77, 'app_id': 123, 'expires_in': 100}) as remote, \
            patch.object(kakao, 'finish_identity', return_value={'result': 'OK'}) as finish:
        result = api.post('/kakao/mobile', json={'access_token': 'mock-token'})
        assert result.status_code == 200 and result.headers['cache-control'] == 'no-store'
        finish.assert_called_once_with('kakao', '77')
        for invalid in ({'id': True, 'app_id': 123, 'expires_in': 100},
                        {'id': 77, 'app_id': 999, 'expires_in': 100},
                        {'id': 77, 'app_id': 123, 'expires_in': 0}):
            finish.reset_mock()
            remote.return_value = invalid
            assert api.post('/kakao/mobile', json={'access_token': 'mock-token'}).status_code == 401
            finish.assert_not_called()
        assert api.post('/kakao/mobile', json={}).status_code == 422


def test_naver_mobile_uses_provider_identity_not_client_input():
    app = FastAPI()
    app.include_router(naver.router)
    with TestClient(app) as api, patch.object(naver, 'signing_key'), \
            patch.object(naver, 'provider_request', return_value={'resultcode': '00', 'response': {'id': 'provider-id'}}) as remote, \
            patch.object(naver, 'finish_identity', return_value={'result': 'SIGNUP_REQUIRED'}) as finish:
        result = api.post('/naver/mobile', json={'access_token': 'mock-token', 'c_id': 'attacker'})
        assert result.status_code == 200
        finish.assert_called_once_with('naver', 'provider-id')
        remote.return_value = {'resultcode': '00', 'response': {'id': ''}}
        finish.reset_mock()
        assert api.post('/naver/mobile', json={'access_token': 'mock-token'}).status_code == 401
        finish.assert_not_called()


def test_chat_session_exchange_requires_owned_active_member():
    app = FastAPI()
    app.include_router(chat.router)
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    with TestClient(app) as api, patch.object(chat, 'chat_connection') as context:
        context.return_value.__enter__.return_value = connection
        assert api.post('/session-token', json={'c_id_seq': 'member_04'}).status_code == 401
        app.dependency_overrides[current_account] = lambda: {'member_ids': ['member_01', 'member_04']}
        assert api.post('/session-token', json={'c_id_seq': 'other_04'}).status_code == 403
        cursor.execute.assert_not_called()
        cursor.fetchone.return_value = None
        assert api.post('/session-token', json={'c_id_seq': 'member_04'}).status_code == 404
        cursor.fetchone.return_value = {'c_id_seq': 'member_04'}
        result = api.post('/session-token', json={'c_id_seq': 'member_04'})
        assert result.status_code == 200
        assert decode_chat_token(result.json()['access_token'])['sub'] == 'member_04'


def test_all_sports_delivery_checks_account_and_reassignment_at_send_time():
    # SQL의 동일 계정 조건이 사전 생성과 실제 발송 양쪽에 존재하는지 확인합니다.
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    delivery = {'f_seq': 1, 'd_seq': 2, 'd_attempts': 1}
    event = {'c_id_seq': 'g_hash_04'}
    send = MagicMock()
    with patch.object(worker, 'eligible', return_value=True):
        assert worker.deliver(connection, event, delivery, send) == 'skipped'
    send.assert_not_called()
    query, args = cursor.execute.call_args_list[0].args
    assert args == (1, 'g_hash_04')
    assert 'BINARY LEFT(owner.c_id_seq' in query and 'owner.c_login_type=recipient.c_login_type' in query
    assert 'owner.c_deletdate IS NULL' in query and "'_04'" in query and ' LIKE ' not in query
    cursor.reset_mock()
    cursor.fetchall.return_value = []
    cursor.fetchone.return_value = {'total': 0, 'waiting': 0, 'failed': 0}
    with patch.object(worker, 'eligible', return_value=True):
        worker.process_event(connection, {**event, 'n_seq': 3}, send)
    insertion = cursor.execute.call_args_list[0].args[0]
    assert 'BINARY LEFT(owner.c_id_seq' in insertion
    assert 'owner.c_login_type=recipient.c_login_type' in insertion


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(value) for name, value in globals().items()
                              if name.startswith('test_') and callable(value))
# 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
