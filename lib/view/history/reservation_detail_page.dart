// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';
import '../../vm/member_state.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../payment/payment_page.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
class ReservationDetailPage extends ConsumerWidget {
  const ReservationDetailPage({super.key, required this.seq});
  final int seq;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final id = ref.watch(memberIdProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('예약 상세')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          ApiContent(
            query: apiQuery('/match/reservation/$seq'),
            builder: (row) {
              if (row['c_id_seq'] != id) return const Text('현재 회원의 예약이 아닙니다.');
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
                              memberId: id,
                              groundName: '${row['g_name']}',
                            ),
                          ),
                        );
                        if (context.mounted) {
                          ref.invalidate(
                            apiDocumentProvider(
                              apiQuery('/match/reservation/$seq'),
                            ),
                          );
                        }
                      },
                      child: const Text('결제 이어하기'),
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
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (예약 분류 문자열 비교)
