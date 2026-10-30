// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/history_state.dart';
import '../../vm/all_members_state.dart';
import '../shared/ui.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';

class PaymentPage extends ConsumerStatefulWidget {
  const PaymentPage({
    super.key,
    this.rSeq,
    required this.memberId,
    required this.groundName,
    this.expectedAmount,
    this.reservationPath,
    this.reservationBody,
  });
  final int? rSeq;
  final String memberId;
  final String groundName;
  final int? expectedAmount;
  final String? reservationPath;
  final Map<String, dynamic>? reservationBody;
  @override
  ConsumerState<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends ConsumerState<PaymentPage> {
  String method = '카드 결제';
  bool busy = false;
  Map<String, dynamic>? receipt;
  Future<void> pay() async {
    if (busy) return;
    setState(() => busy = true);
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('결제 기록을 저장할까요?'),
        content: const Text('결제 내역만 저장합니다. 실제 카드·간편결제 승인 및 출금은 진행되지 않습니다.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context, false),
            child: const Text('돌아가기'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, true),
            child: const Text('기록 저장'),
          ),
        ],
      ),
    );
    if (confirmed != true || !mounted) {
      if (mounted) setState(() => busy = false);
      return;
    }
    try {
      // 신규 예약은 서버에서 예약·결제 기록을 한 번에 확정합니다.
      final result = await ref
          .read(memberApiProvider)
          .request(
            widget.reservationPath ?? '/match/payment',
            body: widget.reservationPath == null
                ? {
                    'r_seq': widget.rSeq,
                    'c_id_seq': widget.memberId,
                    'p_method': method,
                  }
                : {...?widget.reservationBody, 'p_method': method},
          );
      if (mounted) {
        ref.invalidate(historyProvider);
        ref.invalidate(allHistoryProvider);
        setState(
          () => receipt = widget.reservationPath == null
              ? result
              : Map<String, dynamic>.from(result['payment'] as Map),
        );
      }
    } catch (error) {
      if (mounted) {
        showMessage(context, error);
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 목업의 결제 수단 카드·금액 요약을 적용하며 실제 PG 승인으로 표시하지 않습니다.
  @override
  Widget build(BuildContext context) => PopScope(
    canPop: !busy,
    child: Scaffold(
      appBar: AppBar(title: const Text('예약 결제')),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton(
            onPressed: busy
                ? null
                : receipt == null
                ? pay
                : () => Navigator.pop(context, true),
            child: Text(
              busy
                  ? '저장 중…'
                  : receipt == null
                  ? '결제 기록 저장'
                  : '완료',
            ),
          ),
        ),
      ),
      body: pageContent([
        MemberPanel(
          color: Colors.white,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                widget.groundName,
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 20,
                ),
              ),
              const SizedBox(height: 6),
              if (widget.rSeq != null)
                Text(
                  '예약 #${widget.rSeq}',
                  style: const TextStyle(color: MemberStyle.muted),
                ),
            ],
          ),
        ),
        if (receipt == null) ...[
          const Text(
            '결제 수단',
            style: TextStyle(fontSize: 17, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 16),
          GridView.count(
            crossAxisCount: 2,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            childAspectRatio: 2.8,
            crossAxisSpacing: 10,
            mainAxisSpacing: 10,
            children: [
              for (final entry in {
                '카드 결제': Icons.credit_card,
                '카카오페이': Icons.chat_bubble_outline,
                '네이버페이': Icons.payment,
                '토스 페이': Icons.account_balance_wallet_outlined,
                '휴대폰 결제': Icons.phone_android,
                '애플 페이': Icons.phone_iphone,
              }.entries)
                Material(
                  color: method == entry.key
                      ? Theme.of(context).colorScheme.primaryContainer
                      : Theme.of(context).colorScheme.surfaceContainerHigh,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(
                      color: method == entry.key
                          ? MemberStyle.blue
                          : MemberStyle.line,
                    ),
                  ),
                  clipBehavior: Clip.antiAlias,
                  child: InkWell(
                    onTap: busy
                        ? null
                        : () => setState(() => method = entry.key),
                    child: Padding(
                      padding: const EdgeInsets.symmetric(horizontal: 12),
                      child: Row(
                        children: [
                          Icon(entry.value, size: 21, color: MemberStyle.blue),
                          const SizedBox(width: 7),
                          Expanded(
                            child: Text(
                              entry.key,
                              style: const TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ),
            ],
          ),
          const SizedBox(height: 26),
          MemberPanel(
            child: Column(
              children: [
                MemberInfoRow('선택 수단', method),
                MemberInfoRow(
                  '예상 금액',
                  widget.expectedAmount == null
                      ? '저장 후 확정 금액 확인'
                      : '${widget.expectedAmount}원',
                ),
                const Divider(),
                const Text(
                  '실제 승인·출금 없이 결제 내역만 저장됩니다. 최종 금액은 서버의 저장 결과를 확인해 주세요.',
                  style: TextStyle(
                    fontSize: 12,
                    color: MemberStyle.muted,
                    height: 1.7,
                  ),
                ),
              ],
            ),
          ),
        ] else ...[
          const Icon(Icons.check_circle, size: 64, color: MemberStyle.blue),
          const SizedBox(height: 16),
          const Text(
            '결제 기록이 저장되었어요',
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
          ),
          const SizedBox(height: 22),
          MemberPanel(
            child: Column(
              children: [
                MemberInfoRow('결제번호', receipt!['p_num']),
                MemberInfoRow('금액', '${receipt!['p_amount']}원'),
                MemberInfoRow('결제 수단', receipt!['p_method']),
                MemberInfoRow('저장일', receipt!['p_date']),
              ],
            ),
          ),
        ],
      ]),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (테마 대비 적용)
