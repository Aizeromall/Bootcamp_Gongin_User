# 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
"""팀 출전 선택·예약 보호 테스트. 모든 DB 호출은 모의 처리합니다."""
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from python.FastAPI.auth.token import current_account
from python.FastAPI.ground import ground_reservation
from python.FastAPI.match import payment
from python.FastAPI.team_match import lineup, team_match_connect as match


RENTAL = {'r_seq': 8, 'g_code': 2, 'g_num': 4, 'r_date': date(2100, 1, 1),
          'rs_time': timedelta(hours=16), 're_time': timedelta(hours=18),
          'r_check': 0, 'c_id_seq': 'captain_01', 'g_name': '경기장'}


def fake_cursor():
    cursor = MagicMock()
    cursor.fetchone.return_value = None
    cursor.lastrowid = 101
    return cursor


def test_exact_half_and_current_members():
    cursor = fake_cursor()
    with patch.object(lineup, 'team_members', return_value=[{'c_id_seq': 'a_01'}, {'c_id_seq': 'b_01'}]):
        lineup.validate(cursor, 1, ['a_01', 'b_01'], 4)
        for members, code in [(['a_01'], 422), (['a_01', 'a_01'], 422),
                              (['a_01', 'outsider_01'], 409)]:
            with unittest.TestCase().assertRaises(HTTPException) as caught:
                lineup.validate(cursor, 1, members, 4)
            assert caught.exception.status_code == code
    for capacity in (None, 0, -1, 3):
        with unittest.TestCase().assertRaises(HTTPException) as caught:
            lineup.required_count(capacity)
        assert caught.exception.status_code == 409


def test_store_creates_pending_rows_without_touching_anchor():
    cursor = fake_cursor()
    with patch.object(lineup, 'team_members', return_value=[{'c_id_seq': 'captain_01'}, {'c_id_seq': 'other_01'}]):
        result = lineup.store(cursor, RENTAL, 5, ['captain_01', 'other_01'])
    inserts = [call.args for call in cursor.execute.call_args_list if call.args[0].startswith('INSERT INTO reservation')]
    assert len(inserts) == 2
    assert {call[1][0] for call in inserts} == {'captain_01', 'other_01'}
    assert all("0,'2','1',''" in call[0] for call in inserts)
    assert all(call[1][1:] == (2, RENTAL['r_date'], RENTAL['rs_time'], RENTAL['re_time']) for call in inserts)
    assert result['team_id'] == 5 and result['reservations'] == [101, 101]
    assert not any('UPDATE reservation' in call.args[0] for call in cursor.execute.call_args_list)


def test_selected_rental_owner_reuses_original_reservation():
    cursor = fake_cursor()
    with patch.object(lineup, 'team_members', return_value=[{'c_id_seq': 'captain_01'}, {'c_id_seq': 'other_01'}]):
        result = lineup.store(cursor, RENTAL, 5, ['captain_01', 'other_01'], use_anchor=True)
    inserts = [call.args for call in cursor.execute.call_args_list if call.args[0].startswith('INSERT INTO reservation')]
    assert len(inserts) == 1 and inserts[0][1][0] == 'other_01'
    assert result['reservations'] == [8, 101]


def test_overlapping_reservation_aborts_before_insert():
    cursor = fake_cursor()
    cursor.fetchone.return_value = {'r_seq': 99}
    with patch.object(lineup, 'team_members', return_value=[{'c_id_seq': 'a'}, {'c_id_seq': 'b'}]):
        with unittest.TestCase().assertRaises(HTTPException) as caught:
            lineup.store(cursor, RENTAL, 1, ['a', 'b'])
    assert caught.exception.status_code == 409
    assert not any('INSERT INTO reservation' in call.args[0] for call in cursor.execute.call_args_list)


def test_metadata_roundtrip_hidden_and_sql_parameter_interpolation():
    data = {'team_id': 4, 'members': ['hong_01', 'kim_01'], 'reservations': [12, 13]}
    text = lineup.pack('[예약번호:8]\n본문', data)
    assert lineup.unpack(text) == data
    assert lineup.visible(text) == '[예약번호:8]\n본문'
    sql = 'SELECT * FROM reservation r WHERE r.r_seq=%s AND ' + lineup.participant_condition()
    assert 'r.r_seq=12' in (sql % (12,))


def test_confirm_updates_only_anchor_and_both_lineups():
    cursor = fake_cursor()
    home = {'team_id': 1, 'members': ['a', 'b'], 'reservations': [11, 12]}
    away = {'team_id': 2, 'members': ['c', 'd'], 'reservations': [21, 22]}
    with patch.object(lineup, 'validate') as validate, patch.object(lineup, 'rows_for', return_value=[]) as rows:
        lineup.confirm(cursor, RENTAL, home, away)
    assert validate.call_count == 2 and rows.call_count == 2
    assert [c.args[1][0] for c in cursor.execute.call_args_list] == [8, 11, 12, 21, 22]


def test_rejection_deletes_only_pending_rows_and_never_anchor():
    cursor = fake_cursor()
    data = {'team_id': 2, 'members': ['a', 'b'], 'reservations': [21, 22]}
    with patch.object(lineup, 'rows_for', return_value=[{'r_seq': 21, 'r_check': 0}, {'r_seq': 22, 'r_check': 0}]):
        lineup.discard(cursor, RENTAL, data)
    assert [c.args[1][0] for c in cursor.execute.call_args_list] == [21, 22]
    cursor.reset_mock()
    with patch.object(lineup, 'rows_for', return_value=[{'r_seq': 8, 'r_check': 0}]):
        lineup.discard(cursor, RENTAL, data)
    with patch.object(lineup, 'rows_for', return_value=[{'r_seq': 21, 'r_check': 1}]):
        with unittest.TestCase().assertRaises(HTTPException):
            lineup.discard(cursor, RENTAL, data)
    cursor.execute.assert_not_called()


def test_payment_and_cancel_guard_participant():
    cursor = fake_cursor()
    cursor.fetchone.return_value = {'present': 1}
    with unittest.TestCase().assertRaises(HTTPException) as caught:
        lineup.guard_participant(cursor, 101)
    assert caught.exception.status_code == 409


def test_participant_payment_and_rental_cancel_never_change_data():
    for module, invoke in (
        (payment, lambda: payment.create_payment(101, 'captain_01', '카카오페이')),
        (ground_reservation, lambda: ground_reservation.cancel_ground_reservation(101, '취소', 'captain_01')),
    ):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        row = {**RENTAL, 'r_seq': 101, 'reservation_category': '2',
               'r_category': '1', 'r_c_category': ''}
        cursor.fetchone.side_effect = ([{'g_code': RENTAL['g_code']}, {'g_code': RENTAL['g_code']}, row, {'present': 1}]
                                       if module is ground_reservation else [row, {'present': 1}])
        with patch.object(module, 'connect', return_value=connection):
            with unittest.TestCase().assertRaises(HTTPException) as caught:
                invoke()
        assert caught.exception.status_code == 409
        connection.commit.assert_not_called()
        assert not any(call.args[0].startswith(('INSERT ', 'UPDATE ', 'DELETE '))
                       for call in cursor.execute.call_args_list)


def test_selection_requires_login_and_rejects_other_member():
    app = FastAPI()
    app.include_router(match.router, prefix='/team_match')
    with patch.object(match, 'connect') as connect, TestClient(app) as api:
        response = api.get('/team_match/lineup-options', params={'c_id_seq': 'other_01', 'r_seq': 8})
        assert response.status_code == 401
        connect.assert_not_called()
        app.dependency_overrides[current_account] = lambda: {'member_ids': ['captain_01']}
        response = api.get('/team_match/lineup-options', params={'c_id_seq': 'other_01', 'r_seq': 8})
        assert response.status_code == 403
        connect.assert_not_called()


def test_post_validation_failure_rolls_back_without_commit():
    app = FastAPI()
    app.include_router(match.router, prefix='/team_match')
    app.dependency_overrides[current_account] = lambda: {'member_ids': ['captain_01']}
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [RENTAL, None, None]
    with patch.object(match, 'connect', return_value=connection), \
         patch.object(match, 'find_captain_team', return_value={'t_id': 5}), \
         patch.object(match, 'is_rental_open', return_value=True), \
         patch.object(lineup, 'store', side_effect=HTTPException(422, '명단 오류')), TestClient(app) as api:
        response = api.post('/team_match/post', json={'c_id_seq': 'captain_01', 'r_seq': 8,
                                                     'member_ids': ['captain_01']})
    assert response.status_code == 422
    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()


def test_accept_keeps_only_winner_and_discards_other_pending_team():
    home = {'team_id': 1, 'members': ['a', 'b'], 'reservations': [11, 12]}
    away = {'team_id': 2, 'members': ['c', 'd'], 'reservations': [21, 22]}
    other = {'team_id': 3, 'members': ['e', 'f'], 'reservations': [31, 32]}
    post = {**RENTAL, 'bulletin_seq': 9, 'board_content': lineup.pack('[예약번호:8]', home)}
    request = {'comment_seq': 4, 'c_id_seq': 'away_01', 'comment_content': lineup.pack('신청', away)}
    loser = {'comment_seq': 5, 'c_id_seq': 'other_01', 'comment_content': lineup.pack('신청', other)}
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [post, request]
    cursor.fetchall.return_value = [loser]
    cursor.lastrowid = 77
    teams = [{'t_id': 1, 't_name': '홈'}, {'t_id': 2, 't_name': '원정'}]
    with patch.object(match, 'connect', return_value=connection), \
         patch.object(match, 'find_captain_team', side_effect=teams), \
         patch.object(match, 'request_status', return_value=match.STATUS_REQUESTED), \
         patch.object(match, 'is_rental_open', return_value=True), \
         patch.object(match, 'insert_comment', return_value=6), \
         patch.object(lineup, 'confirm') as confirm, patch.object(lineup, 'discard') as discard:
        result = match.answer_team_match_request('captain_01', 9, 4, True)
    confirm.assert_called_once_with(cursor, post, home, away)
    discard.assert_called_once_with(cursor, post, other)
    assert result['status'] == 'accepted' and result['team_code'] == 77
    connection.commit.assert_called_once()


def test_reject_discards_only_requested_team():
    away = {'team_id': 2, 'members': ['c', 'd'], 'reservations': [21, 22]}
    post = {**RENTAL, 'bulletin_seq': 9, 'board_content': '[예약번호:8]'}
    request = {'comment_seq': 4, 'c_id_seq': 'away_01', 'comment_content': lineup.pack('신청', away)}
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.side_effect = [post, request]
    teams = [{'t_id': 1, 't_name': '홈'}, {'t_id': 2, 't_name': '원정'}]
    with patch.object(match, 'connect', return_value=connection), \
         patch.object(match, 'find_captain_team', side_effect=teams), \
         patch.object(match, 'request_status', return_value=match.STATUS_REQUESTED), \
         patch.object(match, 'is_rental_open', return_value=True), \
         patch.object(match, 'insert_comment', return_value=6), \
         patch.object(lineup, 'confirm') as confirm, patch.object(lineup, 'discard') as discard:
        result = match.answer_team_match_request('captain_01', 9, 4, False)
    discard.assert_called_once_with(cursor, post, away)
    confirm.assert_not_called()
    assert result['status'] == 'rejected'
    connection.commit.assert_called_once()


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(unittest.FunctionTestCase(fn) for name, fn in globals().items()
                              if name.startswith('test_') and callable(fn))

# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
