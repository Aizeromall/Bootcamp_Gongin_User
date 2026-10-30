// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30

// 경기 시각은 한국 시각이며, 정확히 한 시간 전부터 취소를 제한합니다.
bool canCancelReservation(Map<String, dynamic> row, {DateTime? now}) {
  if (row['is_canceled'] == true) return false;
  final date = DateTime.tryParse('${row['r_date']}');
  final parts = '${row['rs_time']}'.split(':');
  if (date == null || parts.length < 2) return false;
  final hour = int.tryParse(parts[0]);
  final minute = int.tryParse(parts[1]);
  if (hour == null ||
      minute == null ||
      hour > 23 ||
      minute > 59 ||
      hour < 0 ||
      minute < 0) {
    return false;
  }
  final startKst = DateTime.utc(
    date.year,
    date.month,
    date.day,
    hour - 9,
    minute,
  );
  return (now ?? DateTime.now()).toUtc().isBefore(
    startKst.subtract(const Duration(hours: 1)),
  );
}

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
