// 2026-10-28
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_state.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 회원·예약/취소별 서버 상태를 분리하고 결제는 예약 번호로 연결합니다.
final historyProvider = FutureProvider.autoDispose
    .family<Map<String, dynamic>, ({String id, bool canceled})>((
      ref,
      key,
    ) async {
      final api = ref.watch(memberApiProvider);
      ref.watch(sessionProvider);
      final id = Uri.encodeComponent(key.id);
      final data = await Future.wait([
        api.request(
          '/match/reservation/customer/$id',
          query: {'r_category': key.canceled ? '2' : '1'},
        ),
        if (!key.canceled) api.request('/match/payment/customer/$id'),
      ]);
      if (key.canceled) return data.first;
      final payments = {
        for (final row in data[1]['results'] as List) '${row['r_seq']}': row,
      };
      return {
        'results': [
          for (final row in data.first['results'] as List)
            <String, dynamic>{...row, ...?payments['${row['r_seq']}']},
        ],
      };
    }, retry: (_, _) => null);
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
