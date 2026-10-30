// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter_test/flutter_test.dart';
import 'package:bootcamp_project_gongin_admin_app/view/history/cancellation_time.dart';

void main() {
  test('경기 시작 정확히 한 시간 전부터 비활성화하며 성사 여부는 무관', () {
    final row = {'r_date': '2100-01-01', 'rs_time': '08:00', 'r_check': true};
    expect(
      canCancelReservation(row, now: DateTime.utc(2099, 12, 31, 21, 59, 59)),
      isTrue,
    );
    expect(
      canCancelReservation(row, now: DateTime.utc(2099, 12, 31, 22)),
      isFalse,
    );
    expect(
      canCancelReservation({
        ...row,
        'is_canceled': true,
      }, now: DateTime.utc(2099, 12, 31, 20)),
      isFalse,
    );
  });
}

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
