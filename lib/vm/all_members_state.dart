// 2026-10-30
// 작업자 : 김병재
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'history_state.dart';
import 'member_features.dart';
import 'member_state.dart';

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 종목 Dropdown 제거: 한 로그인의 모든 종목 회원 ID로 같은 목록 API를 조회해 한 목록으로 합칩니다.
// 경로·쿼리 값의 '{id}'를 각 종목 회원 ID로 바꿔 기존 apiDocumentProvider로 조회하므로,
// 기존 화면의 ref.invalidate(apiDocumentProvider) 갱신도 그대로 반영됩니다.
// 각 행에는 그 내역의 내 종목 ID(member_id)를 붙여 종목 표시·상세 이동·답글 작성에 사용합니다.
// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose·retry는 그대로)
class AllMembersDocumentNotifier extends AsyncNotifier<Map<String, dynamic>> {
  AllMembersDocumentNotifier(this.template);
  final ApiQuery template;

  @override
  Future<Map<String, dynamic>> build() async {
    final ids = ref.watch(memberIdsProvider);
    final query = Uri.splitQueryString(template.query);
    final docs = await Future.wait([
      for (final id in ids)
        ref.watch(
          apiDocumentProvider(
            apiQuery(
              template.path.replaceAll('{id}', Uri.encodeComponent(id)),
              {
                for (final entry in query.entries)
                  entry.key: entry.value.replaceAll('{id}', id),
              },
            ),
          ).future,
        ),
    ]);
    return {
      'results': [
        for (final (index, doc) in docs.indexed)
          for (final row in apiRows(doc)) {...row, 'member_id': ids[index]},
      ],
    };
  }
}

final allMembersDocumentProvider = AsyncNotifierProvider.autoDispose
    .family<AllMembersDocumentNotifier, Map<String, dynamic>, ApiQuery>(
      AllMembersDocumentNotifier.new,
      retry: (_, _) => null,
    );

// 수정 일 : 2026-10-30 / 작업자 : 김병재
// 예약내역 전 종목 합치기: 종목별 예약·결제(또는 취소) 내역을 합쳐 경기 날짜·시작 시각 최신순으로 보여줍니다.
// 수정 일 : 2026-10-30 / 작업자 : 신현진
// 상태관리 방식 변경: FutureProvider → AsyncNotifier (조회 로직·키·autoDispose·retry는 그대로)
class AllHistoryNotifier extends AsyncNotifier<Map<String, dynamic>> {
  AllHistoryNotifier(this.canceled);
  final bool canceled;

  @override
  Future<Map<String, dynamic>> build() async {
    final ids = ref.watch(memberIdsProvider);
    final docs = await Future.wait([
      for (final id in ids)
        ref.watch(historyProvider((id: id, canceled: canceled)).future),
    ]);
    final rows = [
      for (final (index, doc) in docs.indexed)
        for (final row in apiRows(doc)) {...row, 'member_id': ids[index]},
    ];
    String key(Map<String, dynamic> row) =>
        '${row['r_date'] ?? ''} ${row['rs_time'] ?? ''}';
    rows.sort((a, b) => key(b).compareTo(key(a)));
    return {'results': rows};
  }
}

final allHistoryProvider = AsyncNotifierProvider.autoDispose
    .family<AllHistoryNotifier, Map<String, dynamic>, bool>(
      AllHistoryNotifier.new,
      retry: (_, _) => null,
    );
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (조회 provider AsyncNotifier 변환)
