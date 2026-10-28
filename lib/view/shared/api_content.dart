// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// FutureBuilder 대신 provider의 로딩·빈 결과·오류·재시도를 표시합니다.
class ApiContent extends ConsumerWidget {
  const ApiContent({super.key, required this.query, required this.builder});
  final ApiQuery query;
  final Widget Function(Map<String, dynamic>) builder;
  @override
  Widget build(BuildContext context, WidgetRef ref) => ref
      .watch(apiDocumentProvider(query))
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
              onPressed: () => ref.invalidate(apiDocumentProvider(query)),
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
