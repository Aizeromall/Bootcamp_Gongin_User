// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/history_state.dart';
import '../payment/payment_page.dart';
import '../shared/ui.dart';
import 'reservation_detail_page.dart';

class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});
  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  String kind = 'reservation';
  bool cancelBusy = false;
  String? memberId;
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  ({String id, bool canceled}) get historyKey =>
      (id: memberId!, canceled: kind == 'cancel');
  Future<Map<String, dynamic>> get future =>
      ref.watch(historyProvider(historyKey).future);
  void load() => ref.invalidate(historyProvider(historyKey));

  // 디버그: 기존 페이지의 대화상자에서 직접 작성한 사유를 전송합니다.
  // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
  Future<void> cancelReservation(Map<String, dynamic> row, String id) async {
    if (cancelBusy) return;
    setState(() => cancelBusy = true);
    try {
      final formKey = GlobalKey<FormState>();
      var text = '';
      final reason = await showDialog<String>(
        context: context,
        builder: (dialogContext) => AlertDialog(
          title: const Text('예약 취소'),
          content: Form(
            key: formKey,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('${row['g_name']} 예약을 취소하시겠어요?'),
                const SizedBox(height: 16),
                TextFormField(
                  autofocus: true,
                  maxLength: 50,
                  minLines: 2,
                  maxLines: 3,
                  decoration: const InputDecoration(
                    labelText: '취소 사유',
                    hintText: '취소 사유를 직접 입력해 주세요.',
                  ),
                  onChanged: (value) => text = value,
                  validator: (value) =>
                      (value ?? '').trim().isEmpty ? '취소 사유를 입력해 주세요.' : null,
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(dialogContext),
              child: const Text('돌아가기'),
            ),
            FilledButton(
              onPressed: () {
                if (formKey.currentState!.validate()) {
                  Navigator.pop(dialogContext, text.trim());
                }
              },
              child: const Text('취소 확정'),
            ),
          ],
        ),
      );
      if (reason == null || !mounted) return;
      await ref
          .read(memberApiProvider)
          .request(
            '/cancel/reservation/${row['r_seq']}',
            method: 'DELETE',
            query: {'c_id_seq': id, 'r_c_category': reason},
          );
      if (!mounted) return;
      showMessage(context, '예약이 취소되었습니다.');
      setState(() {
        if (memberId == id) kind = 'cancel';
        load();
      });
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => cancelBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    if (id != memberId) {
      memberId = id;
    }
    return pageContent([
      heading(
        '나의 플레이 기록',
        '${sports[ref.watch(sportProvider)]} 예약·결제와 취소 내역을 확인하세요.',
      ),
      SegmentedButton<String>(
        segments: const [
          ButtonSegment(value: 'reservation', label: Text('예약·결제')),
          ButtonSegment(value: 'cancel', label: Text('취소')),
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
                // 수정 일 : 2026-10-28 / 작업자 : 양태건
                Align(
                  alignment: Alignment.centerRight,
                  child: TextButton.icon(
                    onPressed: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute<void>(
                          builder: (_) =>
                              ReservationDetailPage(seq: row['r_seq'] as int),
                        ),
                      );
                      if (mounted) setState(load);
                    },
                    icon: const Icon(Icons.confirmation_number_outlined),
                    label: const Text('예약 상세'),
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${row['r_date']} · ${row['rs_time']} ~ ${row['re_time']}',
                ),
                // 디버그: 취소일 대신 실제 취소 사유를 표시합니다.
                // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
                if (kind == 'cancel')
                  Text(
                    '취소 사유: ${row['cancel_reason'] ?? {'1': '정원 미달', '2': '우천·기상 악화', '3': '노쇼 및 환불'}['${row['r_c_category']}'] ?? row['r_c_category'] ?? '사유 미등록'}',
                  )
                else if (row['is_paid'] == true && row['p_num'] != null)
                  Text(
                    '${row['p_amount']}원 · ${row['p_method']}\n결제번호 ${row['p_num']}',
                  )
                else ...[
                  Text(row['is_paid'] == true ? '결제 기록 완료' : '결제 대기'),
                  if (row['is_paid'] != true)
                    FilledButton.tonal(
                      onPressed: cancelBusy
                          ? null
                          : () async {
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
                if (kind != 'cancel' &&
                    row['r_check'] != true &&
                    DateTime.tryParse('${row['r_date']}') != null &&
                    !DateTime.parse('${row['r_date']}')
                        .isBefore(DateUtils.dateOnly(DateTime.now())))
                  TextButton.icon(
                    onPressed: cancelBusy
                        ? null
                        : () => cancelReservation(row, id),
                    icon: const Icon(Icons.cancel_outlined),
                    label: const Text('예약 취소'),
                  ),
              ],
            ),
          ),
        ),
      ),
    ]);
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
