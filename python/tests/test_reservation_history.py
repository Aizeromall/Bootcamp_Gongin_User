"""취소 사유 기반 조회·취소·결제 검증. 작업자 : 양태건 / 최종 수정일 : 2026-10-26."""
import unittest
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from python.FastAPI.match import reservation_search, payment
from python.FastAPI.match.reservation_status import CANCEL_REASONS, is_canceled
from python.FastAPI.cancel import customer_match_delete as cancel


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value.__enter__.return_value
        self.cursor.rowcount = 1
        self.row = dict(r_seq=7, c_id_seq='member_01', g_code=1,
                        g_name='구장', g_address='서울', m_id=None, m_name=None,
                        r_date=date.today() + timedelta(days=1),
                        rs_time=timedelta(hours=8), re_time=timedelta(hours=10),
                        r_check=False, r_category='', r_c_category='', p_seq=None)
        app = FastAPI()
        app.include_router(reservation_search.router, prefix='/match')
        app.include_router(payment.router, prefix='/match')
        app.include_router(cancel.router, prefix='/cancel')
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        for module in [reservation_search, payment, cancel]:
            patcher = patch.object(module, 'connect', return_value=self.connection)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_reason_codes_and_text_classify_without_category(self):
        for reason in ['', None, '0', '  ']:
            self.assertFalse(is_canceled(dict(r_category='', r_c_category=reason)))
        for code, label in CANCEL_REASONS.items():
            for reason in [code, label]:
                row = dict(self.row, r_c_category=reason)
                self.assertTrue(is_canceled(row))
                result = reservation_search.reservation_to_dict(row)
                self.assertEqual(result['cancel_reason'], label)
                self.assertEqual(result['r_category'], 2)
                self.assertEqual(result['rs_time'], '08:00')
                self.assertNotIn('r_cancel_date', result)

    def test_active_and_canceled_history_response(self):
        for kind in [1, 2]:
            with self.subTest(kind=kind):
                self.cursor.fetchall.return_value = [dict(self.row, r_c_category='1' if kind == 2 else '')]
                response = self.client.get('/match/reservation/customer/member_01', params={'r_category': kind})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['results'][0]['is_canceled'], kind == 2)

    def test_cancel_records_each_reason_without_deleting_reservation(self):
        for code, label in CANCEL_REASONS.items():
            with self.subTest(code=code):
                self.cursor.reset_mock()
                self.cursor.fetchone.side_effect = [dict(self.row), None]
                response = self.client.delete('/cancel/reservation/7', params={
                    'c_id_seq': 'member_01', 'r_c_category': code})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['cancel_reason'], label)
                calls = self.cursor.execute.call_args_list
                update = calls[-1]
                self.assertEqual(update.args[1], ('2', code, 7))
                self.assertNotIn('r_cancel_date', update.args[0])
                self.assertFalse(any('DELETE FROM reservation' in c.args[0] for c in calls))
        self.assertEqual(self.connection.commit.call_count, 3)

    def test_user_written_reason_is_trimmed_saved_and_displayed(self):
        for reason in ['개인 일정 때문에 참석할 수 없습니다.', '가' * 50]:
            with self.subTest(reason=reason):
                self.cursor.fetchone.side_effect = [dict(self.row), None]
                # 최대 길이는 원문 기준으로 검사되므로 50자에는 공백을 덧붙이지 않습니다.
                raw = '  ' + reason + '  ' if len(reason) < 46 else reason
                response = self.client.delete('/cancel/reservation/7', params={
                    'c_id_seq': 'member_01', 'r_c_category': raw})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()['cancel_reason'], reason)
                self.assertEqual(self.cursor.execute.call_args.args[1], ('2', reason, 7))
                result = reservation_search.reservation_to_dict(dict(self.row, r_c_category=reason))
                self.assertEqual(result['cancel_reason'], reason)

    def test_cancel_missing_invalid_reason_rejected_before_db(self):
        for reason in [None, '', '   ', '가' * 51]:
            params = {'c_id_seq': 'member_01'}
            if reason is not None:
                params['r_c_category'] = reason
            self.assertEqual(self.client.delete('/cancel/reservation/7', params=params).status_code, 422)
        self.connection.cursor.assert_not_called()

    def test_canceled_reason_blocks_repayment_and_duplicate_cancellation(self):
        self.cursor.fetchone.return_value = dict(self.row, r_c_category='2')
        response = self.client.post('/match/payment', json={
            'r_seq': 7, 'c_id_seq': 'member_01', 'p_method': '카드 결제'})
        self.assertEqual(response.status_code, 409)
        response = self.client.delete('/cancel/reservation/7', params={
            'c_id_seq': 'member_01', 'r_c_category': '1'})
        self.assertEqual(response.status_code, 409)
        self.connection.commit.assert_not_called()
        self.assertEqual(self.connection.rollback.call_count, 2)

    def test_cancel_preserves_ownership_and_date_guards(self):
        for updates, status in [({'c_id_seq': 'other_01'}, 403),
                                ({'r_date': date.today() - timedelta(days=1)}, 409),
                                ({'r_check': True}, 409)]:
            self.cursor.fetchone.return_value = dict(self.row, **updates)
            response = self.client.delete('/cancel/reservation/7', params={
                'c_id_seq': 'member_01', 'r_c_category': '1'})
            self.assertEqual(response.status_code, status)
        self.connection.commit.assert_not_called()


if __name__ == '__main__':
    unittest.main()
