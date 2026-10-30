// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/all_members_state.dart';
import '../../vm/member_features.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// FutureBuilder 대신 provider의 로딩·빈 결과·오류·재시도를 표시합니다.
class ApiContent extends ConsumerWidget {
  const ApiContent({
    super.key,
    required this.query,
    required this.builder,
    this.allMembers = false,
  });
  final ApiQuery query;
  final Widget Function(Map<String, dynamic>) builder;
  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // true면 query의 '{id}'를 내 모든 종목 회원 ID로 바꿔 조회한 결과를 합쳐 보여줍니다(종목 Dropdown 제거).
  final bool allMembers;
  @override
  Widget build(BuildContext context, WidgetRef ref) => ref
      .watch(
        allMembers
            ? allMembersDocumentProvider(query)
            : apiDocumentProvider(query),
      )
      .when(
        skipLoadingOnRefresh: false,
        data: builder,
        loading: () => const Padding(
          padding: EdgeInsets.all(32),
          child: Center(child: CircularProgressIndicator()),
        ),
        error: (error, _) => Column(
          children: [
            Text(error.toString().replaceFirst('Exception: ', '')),
            TextButton(
              onPressed: () => allMembers
                  // 합친 목록은 종목별 조회까지 모두 다시 요청합니다.
                  ? ref.invalidate(apiDocumentProvider)
                  : ref.invalidate(apiDocumentProvider(query)),
              child: const Text('다시 시도'),
            ),
          ],
        ),
      );
}

class FeedItems extends StatelessWidget {
  const FeedItems({super.key, required this.data, required this.item});
  final Map<String, dynamic> data;
  final Widget Function(Map<String, dynamic>) item;
  @override
  Widget build(BuildContext context) {
    final rows = apiRows(data);
    return rows.isEmpty
        ? const Padding(
            padding: EdgeInsets.all(24),
            child: Text('아직 표시할 내역이 없습니다.'),
          )
        : Column(children: rows.map(item).toList());
  }
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (전 종목 합친 목록 옵션)
