// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../shared/ui.dart';
import '../reservation/reservation_page.dart';

class GroundsPage extends ConsumerStatefulWidget {
  const GroundsPage({super.key});
  @override
  ConsumerState<GroundsPage> createState() => _GroundsPageState();
}

class _GroundsPageState extends ConsumerState<GroundsPage> {
  final search = TextEditingController();
  late Future<Map<String, dynamic>> results;
  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    results = ref
        .read(memberApiProvider)
        .request('/match/ground', query: {'keyword': search.text.trim()});
  }

  void refresh() => setState(load);
  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => pageContent([
    heading(
      '오늘은 어디서 뛸까요?',
      '${ref.watch(sessionProvider)?['c_name']}님, 함께할 구장을 찾아보세요.',
    ),
    Card(
      color: const Color(0xFFDDEFD3),
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Row(
          children: [
            const Icon(Icons.sports, size: 48),
            const SizedBox(width: 20),
            Expanded(
              child: Text(
                '가볍게 모여, 즐겁게 플레이\n${sports[ref.watch(sportProvider)]}와 함께하는 오늘',
                style: const TextStyle(
                  fontSize: 21,
                  fontWeight: FontWeight.bold,
                ),
              ),
            ),
          ],
        ),
      ),
    ),
    const SizedBox(height: 20),
    TextField(
      controller: search,
      onSubmitted: (_) => refresh(),
      decoration: InputDecoration(
        hintText: '구장명 또는 주소 검색',
        prefixIcon: const Icon(Icons.search),
        suffixIcon: IconButton(
          onPressed: refresh,
          icon: const Icon(Icons.arrow_forward),
        ),
      ),
    ),
    const SizedBox(height: 16),
    ResultList(
      future: results,
      retry: refresh,
      item: (row) => Card(
        child: Padding(
          padding: const EdgeInsets.all(20),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  const Icon(Icons.stadium, color: Color(0xFF298653)),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      '${row['g_name']}',
                      style: const TextStyle(
                        fontSize: 21,
                        fontWeight: FontWeight.bold,
                      ),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Text('${row['g_address']}'),
              const SizedBox(height: 8),
              Text('${row['g_num']}명 · 구장 이용료 ${row['g_price']}원'),
              if (row['g_information'] != null)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  child: Text('${row['g_information']}'),
                ),
              FilledButton.tonal(
                onPressed: () => Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => ReservationPage(ground: row),
                  ),
                ),
                child: const Text('시간 선택 · 예약'),
              ),
            ],
          ),
        ),
      ),
    ),
  ]);
}
// 최종 수정 일 : 2026-10-24
