// 2026-10-28
// 작업자 : 양태건
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';
import '../../vm/member_state.dart';
import '../../vm/history_state.dart';
import '../../vm/all_members_state.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../payment/payment_page.dart';
import '../shared/ui.dart';
import 'cancellation_time.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
class ReservationDetailPage extends ConsumerStatefulWidget {
  const ReservationDetailPage({
    super.key,
    required this.seq,
    this.rental = false,
  });
  final int seq;
  final bool rental;
  @override
  ConsumerState<ReservationDetailPage> createState() =>
      _ReservationDetailPageState();
}

class _ReservationDetailPageState extends ConsumerState<ReservationDetailPage> {
  bool cancelBusy = false;
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

  Future<void> cancel(Map<String, dynamic> row) async {
    if (cancelBusy) return;
    var input = '';
    final reason = await showDialog<String>(
      context: context,
      builder: (dialog) => AlertDialog(
        title: const Text('예약 취소'),
        content: TextField(
          onChanged: (value) => input = value,
          maxLength: 50,
          decoration: const InputDecoration(labelText: '취소 사유를 입력해 주세요'),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(dialog),
            child: const Text('돌아가기'),
          ),
          FilledButton(
            onPressed: () {
              if (input.trim().isNotEmpty) Navigator.pop(dialog, input.trim());
            },
            child: const Text('취소 확정'),
          ),
        ],
      ),
    );
    if (!mounted || reason == null) return;
    setState(() => cancelBusy = true);
    try {
      final path = '${row['reservation_category']}' == '2'
          ? '/ground/reservation'
          : '/cancel/reservation';
      await ref
          .read(memberApiProvider)
          .request(
            '$path/${widget.seq}',
            method: 'DELETE',
            query: {'c_id_seq': '${row['c_id_seq']}', 'r_c_category': reason},
          );
      ref.invalidate(historyProvider);
      ref.invalidate(allHistoryProvider);
      ref.invalidate(
        apiDocumentProvider(
          apiQuery(
            '${widget.rental ? '/ground' : '/match'}/reservation/${widget.seq}',
          ),
        ),
      );
      if (mounted) showMessage(context, '예약이 취소되었습니다.');
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => cancelBusy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final seq = widget.seq;
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 종목 Dropdown 제거: 내 모든 종목 회원 ID 중 하나의 예약이면 상세를 보여줍니다.
    final ids = ref.watch(memberIdsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('예약 상세')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          ApiContent(
            query: apiQuery(
              '${widget.rental ? '/ground' : '/match'}/reservation/$seq',
            ),
            builder: (row) {
              if (!ids.contains(row['c_id_seq'])) {
                return const Text('현재 회원의 예약이 아닙니다.');
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    '${row['g_name']}',
                    style: const TextStyle(
                      fontSize: 23,
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '${row['r_date']} · ${row['rs_time']} ~ ${row['re_time']}',
                    style: const TextStyle(color: MemberStyle.muted),
                  ),
                  const SizedBox(height: 22),
                  MemberPanel(
                    color: Colors.white,
                    child: Column(
                      children: [
                        const Icon(
                          Icons.confirmation_number_outlined,
                          color: MemberStyle.blue,
                          size: 44,
                        ),
                        const SizedBox(height: 12),
                        const Text(
                          '예약번호',
                          style: TextStyle(color: MemberStyle.muted),
                        ),
                        Text(
                          '#$seq',
                          style: const TextStyle(
                            fontSize: 27,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 8),
                        const Text(
                          '예약 번호와 이용 시간을 확인해 주세요.',
                          style: TextStyle(
                            fontSize: 12,
                            color: MemberStyle.muted,
                          ),
                        ),
                      ],
                    ),
                  ),
                  MemberPanel(
                    child: Column(
                      children: [
                        MemberInfoRow(
                          '이용 구분',
                          // 수정 일 : 2026-10-28 / 작업자 : 최현준 (예약 분류 문자열 계약)
                          row['reservation_category'] == '2'
                              ? '구장 전체 대여'
                              : '실력 매칭',
                        ),
                        MemberInfoRow('구장', row['g_name']),
                        MemberInfoRow('담당 매니저', row['m_name'] ?? '배정 정보 없음'),
                        MemberInfoRow(
                          '상태',
                          row['is_canceled'] == true
                              ? '취소'
                              : row['is_paid'] == true
                              ? '결제 기록 완료'
                              : '결제 대기',
                        ),
                        if (row['is_canceled'] == true)
                          MemberInfoRow('취소 사유', row['cancel_reason']),
                      ],
                    ),
                  ),
                  if (row['is_paid'] == true)
                    ApiContent(
                      query: apiQuery('/match/payment/reservation/$seq'),
                      builder: (payment) => MemberPanel(
                        child: Column(
                          children: [
                            MemberInfoRow('결제번호', payment['p_num']),
                            MemberInfoRow('저장 금액', '${payment['p_amount']}원'),
                            MemberInfoRow('결제 수단', payment['p_method']),
                          ],
                        ),
                      ),
                    ),
                  if (row['is_paid'] != true && row['is_canceled'] != true)
                    FilledButton(
                      onPressed: () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) => PaymentPage(
                              rSeq: seq,
                              // 결제는 이 예약의 종목 회원 ID로 진행합니다.
                              memberId: '${row['c_id_seq']}',
                              groundName: '${row['g_name']}',
                            ),
                          ),
                        );
                        if (context.mounted) {
                          ref.invalidate(
                            apiDocumentProvider(
                              apiQuery(
                                '${widget.rental ? '/ground' : '/match'}/reservation/$seq',
                              ),
                            ),
                          );
                        }
                      },
                      child: const Text('결제 이어하기'),
                    ),
                  OutlinedButton(
                    onPressed: cancelBusy || !canCancelReservation(row)
                        ? null
                        : () => cancel(row),
                    child: Text(cancelBusy ? '취소 처리 중…' : '예약 취소'),
                  ),
                  if (row['is_canceled'] != true && !canCancelReservation(row))
                    const Text(
                      '경기 시간 확인이 필요하거나 취소 가능 시간이 지났습니다.',
                      style: TextStyle(fontSize: 12, color: MemberStyle.muted),
                    ),
                ],
              );
            },
          ),
        ],
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (예약 분류 문자열 비교)
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (전 종목 예약 상세·결제 회원 ID)
