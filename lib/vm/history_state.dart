// 2026-10-28
// 작업자 : 양태건
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'member_state.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 회원·예약/취소별 서버 상태를 분리하고 개인 예약과 전체 대여를 함께 조회합니다.
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
    }, retry: (_, _) => null);
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (구장 대여 내역 연결)
