# 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
"""한국 시간 기준 1시간 경계와 성사된 예약 취소를 Mock으로 검증합니다."""
import unittest
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

from python.FastAPI.match.reservation_status import cancellation_allowed
from python.FastAPI.cancel import customer_match_delete
from python.FastAPI.ground import ground_reservation
from python.FastAPI.team_match import lineup


class CancellationCutoffTests(unittest.TestCase):
    def test_cutoff_is_inclusive_and_uses_start_time(self):
        day = date(2100, 1, 1)
        self.assertTrue(cancellation_allowed(day, timedelta(hours=8), datetime(2100, 1, 1, 6, 59, 59)))
        self.assertFalse(cancellation_allowed(day, '08:00', datetime(2100, 1, 1, 7, 0)))
        self.assertFalse(cancellation_allowed(day, '08:00:00', datetime(2100, 1, 1, 8, 0)))
        self.assertTrue(cancellation_allowed(day, '00:30', datetime(2099, 12, 31, 23, 29)))

    def test_confirmed_personal_reopens_same_slot(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        row = {'r_seq': 7, 'g_code': 2, 'c_id_seq': 'member_01', 'r_date': date(2100, 1, 1),
               'rs_time': '08:00', 'r_check': 1, 'r_category': '1', 'r_c_category': '',
               'reservation_category': '1'}
        cursor.fetchone.side_effect = [{'g_code': 2}, {'g_code': 2}, row, None]
        with patch.object(customer_match_delete, 'connect', return_value=connection):
            customer_match_delete.delete_customer_reservation(7, '일정 변경', 'member_01')
        self.assertTrue(any('SET r_check=0' in c.args[0] for c in cursor.execute.call_args_list))
        connection.commit.assert_called_once()

    def test_confirmed_team_uses_whole_match_cleanup(self):
        connection = MagicMock()
        cursor = connection.cursor.return_value.__enter__.return_value
        cursor.rowcount = 1
        row = {'r_seq': 7, 'g_code': 2, 'c_id_seq': 'member_01', 'r_date': date(2100, 1, 1),
               'rs_time': '08:00', 'r_check': 1, 'r_category': '1', 'r_c_category': '',
               'reservation_category': '2'}
        cursor.fetchone.side_effect = [{'g_code': 2}, {'g_code': 2}, row, row, None]
        with patch.object(ground_reservation, 'connect', return_value=connection), \
             patch.object(ground_reservation, 'guard_participant'), \
             patch.object(ground_reservation, 'cancel_confirmed') as cleanup:
            ground_reservation.cancel_ground_reservation(7, '일정 변경', 'member_01')
        cleanup.assert_called_once_with(cursor, row)
        connection.commit.assert_called_once()

    def test_confirmed_lineups_and_matching_record_are_removed(self):
        cursor = MagicMock()
        home = {'team_id': 1, 'members': ['member_01'], 'reservations': [7]}
        away = {'team_id': 2, 'members': ['other_01'], 'reservations': [8]}
        post = {'bulletin_seq': 9, 'board_content': lineup.pack('[예약번호:7] 게시글', home)}
        application = {'comment_seq': 1, 'reply_seq': 2, 'comment_content': lineup.pack('신청', away)}
        cursor.fetchall.side_effect = [[post], [application], [{'team_code': 3}],
                                      [{'r_seq': 7, 'c_id_seq': 'member_01', 'r_check': 1}],
                                      [{'r_seq': 8, 'c_id_seq': 'other_01', 'r_check': 1}]]
        rental = {'r_seq': 7, 'g_code': 2, 'r_date': date(2100, 1, 1),
                  'rs_time': '08:00', 're_time': '10:00'}
        lineup.cancel_confirmed(cursor, rental)
        calls = cursor.execute.call_args_list
        self.assertTrue(any('DELETE FROM team_match' in c.args[0] and c.args[1] == (3,) for c in calls))
        self.assertTrue(any('DELETE FROM reservation' in c.args[0] and c.args[1] == (8,) for c in calls))
        self.assertFalse(any('DELETE FROM reservation' in c.args[0] and c.args[1] == (7,) for c in calls))

    def test_ambiguous_team_match_does_not_delete(self):
        cursor = MagicMock()
        home = {'team_id': 1, 'members': ['member_01'], 'reservations': [7]}
        away = {'team_id': 2, 'members': ['other_01'], 'reservations': [8]}
        cursor.fetchall.side_effect = [[{'bulletin_seq': 9, 'board_content': lineup.pack('[예약번호:7]', home)}],
            [{'comment_seq': 1, 'reply_seq': 2, 'comment_content': lineup.pack('신청', away)}],
            [{'team_code': 3}, {'team_code': 4}]]
        rental = {'r_seq': 7, 'g_code': 2, 'r_date': date(2100, 1, 1), 'rs_time': '08:00', 're_time': '10:00'}
        with self.assertRaises(Exception) as error:
            lineup.cancel_confirmed(cursor, rental)
        self.assertEqual(error.exception.status_code, 409)
        self.assertFalse(any('DELETE' in c.args[0] for c in cursor.execute.call_args_list))


# 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
