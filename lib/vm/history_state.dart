// 2026-10-28
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_state.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 회원·예약/취소별 서버 상태를 분리하고 개인 예약과 전체 대여를 함께 조회합니다.
// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose·retry는 그대로)
typedef HistoryKey = ({String id, bool canceled});

class HistoryNotifier extends AsyncNotifier<Map<String, dynamic>> {
  HistoryNotifier(this.key);
  final HistoryKey key;

  @override
  Future<Map<String, dynamic>> build() async {
    final api = ref.watch(memberApiProvider);
    ref.watch(sessionProvider);
    final id = Uri.encodeComponent(key.id);
    final data = await Future.wait([
      api.request(
        '/match/reservation/customer/$id',
        query: {'r_category': key.canceled ? '2' : '1'},
      ),
      // 수정 일 : 2026-10-30 / 작업자 : 최현준
      // 전체 대여도 예약·취소 내역에 포함하며 결제는 예약 번호로 연결합니다.
      api.request(
        '/ground/reservation/customer/$id',
        query: {'r_category': key.canceled ? '2' : '1'},
      ),
      if (!key.canceled) api.request('/match/payment/customer/$id'),
    ]);
    final reservations = [
      ...data[0]['results'] as List,
      ...data[1]['results'] as List,
    ];
    if (key.canceled) return {'results': reservations};
    final payments = {
      for (final row in data[2]['results'] as List) '${row['r_seq']}': row,
    };
    return {
      'results': [
        for (final row in reservations)
          <String, dynamic>{...row, ...?payments['${row['r_seq']}']},
      ],
    };
  }
}

final historyProvider = AsyncNotifierProvider.autoDispose
    .family<HistoryNotifier, Map<String, dynamic>, HistoryKey>(
      HistoryNotifier.new,
      retry: (_, _) => null,
    );
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (조회 provider AsyncNotifier 변환)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (구장 대여 내역 연결)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (AsyncNotifier 충돌 해결)
