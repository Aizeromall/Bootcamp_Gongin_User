// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../shared/ui.dart';

class PaymentPage extends ConsumerStatefulWidget {
  const PaymentPage({
    super.key,
    required this.rSeq,
    required this.memberId,
    required this.groundName,
  });
  final int rSeq;
  final String memberId;
  final String groundName;
  @override
  ConsumerState<PaymentPage> createState() => _PaymentPageState();
}

class _PaymentPageState extends ConsumerState<PaymentPage> {
  String method = '카드 결제';
  bool busy = false;
  Map<String, dynamic>? receipt;
  Future<void> pay() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('결제 기록을 저장할까요?'),
        content: const Text(
          'Version 1은 결제 내역을 저장합니다. 실제 카드·간편결제 승인 및 출금은 진행되지 않습니다.',
        ),
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
      return;
    }
    setState(() => busy = true);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            '/match/payment',
            body: {
              'r_seq': widget.rSeq,
              'c_id_seq': widget.memberId,
              'p_method': method,
            },
          );
      if (mounted) {
        setState(() => receipt = result);
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

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('예약 결제')),
    body: pageContent([
      heading(
        receipt == null ? '결제 수단을 선택해 주세요' : '결제 기록이 저장되었어요',
        '${widget.groundName} · 예약 #${widget.rSeq}',
      ),
      if (receipt == null) ...[
        const Text(
          '실제 결제 승인은 제공되지 않습니다. 금액은 구장 이용료 ÷ 수용 인원을 원 단위로 반올림해 서버에서 확정합니다.',
        ),
        const SizedBox(height: 24),
        DropdownButtonFormField<String>(
          initialValue: method,
          decoration: const InputDecoration(labelText: '결제 수단'),
          items: [
            '카드 결제',
            '카카오페이',
            '네이버페이',
            '토스 페이',
            '휴대폰 결제',
            '애플 페이',
          ].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
          onChanged: busy ? null : (v) => setState(() => method = v!),
        ),
        const SizedBox(height: 24),
        FilledButton(
          onPressed: busy ? null : pay,
          child: Text(busy ? '저장 중…' : '결제 기록 저장'),
        ),
      ] else ...[
        const Icon(Icons.check_circle, color: Color(0xFF298653), size: 72),
        Text(
          '결제번호 ${receipt!['p_num']}\n금액 ${receipt!['p_amount']}원\n${receipt!['p_method']}\n예약일 ${receipt!['p_date']}',
          style: const TextStyle(fontSize: 20, height: 1.8),
        ),
        FilledButton(
          onPressed: () => Navigator.pop(context, true),
          child: const Text('완료'),
        ),
      ],
    ]),
  );
}
// 최종 수정 일 : 2026-10-24
