// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/all_members_state.dart';
import '../../vm/history_state.dart';
import '../payment/payment_page.dart';
import '../shared/ui.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import 'reservation_detail_page.dart';
import 'cancellation_time.dart';

class HistoryPage extends ConsumerStatefulWidget {
  const HistoryPage({super.key});
  @override
  ConsumerState<HistoryPage> createState() => _HistoryPageState();
}

class _HistoryPageState extends ConsumerState<HistoryPage> {
  String kind = 'reservation';
  bool cancelBusy = false;
  String? memberId;
  Timer? cutoffTimer;
  @override
  void initState() {
    super.initState();
    cutoffTimer = Timer.periodic(const Duration(seconds: 1), (_) {
      if (mounted) setState(() {});
    });
  }

  @override
  void dispose() {
    cutoffTimer?.cancel();
    super.dispose();
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 종목 Dropdown 제거: 가입한 모든 종목의 내역을 합쳐 보여주고, 새로고침 시 종목별 조회를 모두 갱신합니다.
  Future<Map<String, dynamic>> get future =>
      ref.watch(allHistoryProvider(kind == 'cancel').future);
  void load() {
    ref.invalidate(historyProvider);
    ref.invalidate(allHistoryProvider);
  }

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
            '${'${row['reservation_category']}' == '2' ? '/ground/reservation' : '/cancel/reservation'}/${row['r_seq']}',
            method: 'DELETE',
            query: {'c_id_seq': id, 'r_c_category': reason},
          );
      if (!mounted) return;
      showMessage(context, '예약이 취소되었습니다.');
      setState(() {
        kind = 'cancel';
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
    // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 행마다 그 예약의 내 종목 ID(member_id)를 사용합니다.
    final fallbackId = ref.watch(memberIdProvider);
    return pageContent([
      heading('나의 플레이 기록', '가입한 모든 종목의 예약·결제와 취소 내역을 확인하세요.'),
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
        item: (row) => historyCard(row, '${row['member_id'] ?? fallbackId}'),
      ),
    ]);
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 내역 카드: 종목 배지와 취소·결제 요청은 그 예약의 내 종목 회원 ID(id) 기준입니다.
  Widget historyCard(Map<String, dynamic> row, String id) => Card(
    child: Padding(
      padding: const EdgeInsets.all(20),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 수정 일 : 2026-10-28 / 작업자 : 양태건
          Wrap(
            spacing: 6,
            runSpacing: 6,
            children: [
              MemberStatusBadge(
                kind == 'cancel'
                    ? '취소 내역'
                    : row['is_paid'] == true
                    ? '결제 기록 완료'
                    : '결제 대기',
                color: kind == 'cancel' ? Colors.red : MemberStyle.blue,
              ),
              MemberStatusBadge(sports[sportOfMember(id)] ?? ''),
              if ('${row['reservation_category']}' == '2')
                const MemberStatusBadge('구장 전체 대여'),
            ],
          ),
          const SizedBox(height: 12),
          Text(
            '${row['g_name']}',
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
          ),
          // 수정 일 : 2026-10-28 / 작업자 : 양태건
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: () async {
                await Navigator.push(
                  context,
                  MaterialPageRoute<void>(
                    builder: (_) => ReservationDetailPage(
                      seq: row['r_seq'] as int,
                      rental: '${row['reservation_category']}' == '2',
                    ),
                  ),
                );
                if (mounted) setState(load);
              },
              icon: const Icon(Icons.confirmation_number_outlined),
              label: const Text('예약 상세'),
            ),
          ),
          const SizedBox(height: 8),
          // 수정 일 : 2026-10-30 / 작업자 : 최현준
          // 예약 일시를 카드의 보조 정보로 명확히 구분합니다.
          Text(
            '${row['r_date']} · ${row['rs_time']} ~ ${row['re_time']}',
            style: TextStyle(
              fontSize: 13,
              height: 1.5,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
          const SizedBox(height: 12),
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
          if (kind != 'cancel')
            TextButton.icon(
              onPressed: cancelBusy || !canCancelReservation(row)
                  ? null
                  : () => cancelReservation(row, id),
              icon: const Icon(Icons.cancel_outlined),
              label: const Text('예약 취소'),
            ),
          if (kind != 'cancel' && !canCancelReservation(row))
            const Text(
              '경기 시간 확인이 필요하거나 취소 가능 시간이 지났습니다.',
              style: TextStyle(fontSize: 12, color: MemberStyle.muted),
            ),
        ],
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (종목 Dropdown 제거: 전 종목 예약·결제·취소 내역 통합)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (대여 취소 경로 구분)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
