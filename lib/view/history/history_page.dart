// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../payment/payment_page.dart';
import '../shared/ui.dart';

class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});
  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  String kind = 'reservation';
  String? memberId;
  late Future<Map<String, dynamic>> future;
  void load() {
    future = ref
        .read(memberApiProvider)
        .request('/match/$kind/customer/${Uri.encodeComponent(memberId!)}');
  }

  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    if (id != memberId) {
      memberId = id;
      load();
    }
    return pageContent([
      heading(
        '나의 플레이 기록',
        '${sports[ref.watch(sportProvider)]} 예약과 결제 내역을 확인하세요.',
      ),
      SegmentedButton<String>(
        segments: const [
          ButtonSegment(value: 'reservation', label: Text('예약')),
          ButtonSegment(value: 'payment', label: Text('결제')),
        ],
        selected: {kind},
        onSelectionChanged: (v) => setState(() {
          kind = v.first;
          load();
        }),
      ),
      Align(
        alignment: Alignment.centerRight,
        child: TextButton.icon(
          onPressed: () => setState(load),
          icon: const Icon(Icons.refresh),
          label: const Text('새로고침'),
        ),
      ),
      ResultList(
        future: future,
        retry: () => setState(load),
        item: (row) => Card(
          child: Padding(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${row['g_name']}',
                  style: const TextStyle(
                    fontSize: 21,
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${row['r_date']} · ${row['rs_time']} ~ ${row['re_time']}',
                ),
                if (kind == 'payment')
                  Text(
                    '${row['p_amount']}원 · ${row['p_method']}\n결제번호 ${row['p_num']}',
                  )
                else ...[
                  Text(row['is_paid'] == true ? '결제 기록 완료' : '결제 대기'),
                  if (row['is_paid'] != true)
                    FilledButton.tonal(
                      onPressed: () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) => PaymentPage(
                              rSeq: row['r_seq'] as int,
                              memberId: id,
                              groundName: '${row['g_name']}',
                            ),
                          ),
                        );
                        if (mounted) {
                          setState(load);
                        }
                      },
                      child: const Text('결제 이어하기'),
                    ),
                ],
              ],
            ),
          ),
        ),
      ),
    ]);
  }
}
// 최종 수정 일 : 2026-10-24
