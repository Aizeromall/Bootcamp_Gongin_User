// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';

void showMessage(BuildContext context, Object message) =>
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message.toString().replaceFirst('Exception: ', '')),
      ),
    );
String day(DateTime value) => value.toIso8601String().split('T').first;
Widget pageContent(List<Widget> children) => Center(
  child: ConstrainedBox(
    constraints: const BoxConstraints(maxWidth: 900),
    child: ListView(padding: const EdgeInsets.all(24), children: children),
  ),
);
Widget heading(String title, String subtitle) => Padding(
  padding: const EdgeInsets.only(bottom: 24),
  child: Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        title,
        style: const TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w800,
          color: Color(0xFF193B2B),
        ),
      ),
      const SizedBox(height: 8),
      Text(subtitle, style: const TextStyle(color: Color(0xFF647568))),
    ],
  ),
);

/// 비동기 조회 공통 상태: 로딩·빈 목록·오류·재시도를 일관되게 표시합니다.
class ResultList extends StatelessWidget {
  const ResultList({
    super.key,
    required this.future,
    required this.item,
    required this.retry,
  });
  final Future<Map<String, dynamic>> future;
  final Widget Function(Map<String, dynamic>) item;
  final VoidCallback retry;
  @override
  Widget build(BuildContext context) => FutureBuilder<Map<String, dynamic>>(
    future: future,
    builder: (context, snapshot) {
      if (snapshot.connectionState != ConnectionState.done) {
        return const Padding(
          padding: EdgeInsets.all(32),
          child: Center(child: CircularProgressIndicator()),
        );
      }
      if (snapshot.hasError) {
        return Column(
          children: [
            Text('${snapshot.error}'),
            TextButton(onPressed: retry, child: const Text('다시 시도')),
          ],
        );
      }
      final rows = (snapshot.data?['results'] as List?) ?? [];
      if (rows.isEmpty) {
        return const Padding(
          padding: EdgeInsets.all(32),
          child: Text('아직 표시할 내역이 없습니다.'),
        );
      }
      return Column(
        children: rows
            .map((row) => item(Map<String, dynamic>.from(row as Map)))
            .toList(),
      );
    },
  );
}
// 최종 수정 일 : 2026-10-24
