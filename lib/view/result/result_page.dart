// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 매니저가 기록한 회원 본인의 결과만 조회하며 상대 스코어·집계 통계를 만들지 않습니다.
class ResultPage extends ConsumerWidget {
  const ResultPage({super.key, this.seq});
  final int? seq;
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final id = ref.watch(memberIdProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('경기 결과')),
      body: pageContent([
        ApiContent(
          query: apiQuery(
            seq == null
                ? '/match/result/customer/${Uri.encodeComponent(id)}'
                : '/match/result/$seq',
          ),
          builder: (data) {
            if (seq != null) {
              if (data['c_id_seq'] != id) {
                return const Text('현재 회원의 경기 기록이 아닙니다.');
              }
              return Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Container(
                    padding: const EdgeInsets.all(24),
                    margin: const EdgeInsets.only(bottom: 22),
                    decoration: BoxDecoration(
                      color: const Color(0xFF172541),
                      borderRadius: BorderRadius.circular(20),
                    ),
                    child: Column(
                      children: [
                        Text(
                          '${data['g_name']}',
                          style: const TextStyle(color: Colors.white),
                        ),
                        const SizedBox(height: 16),
                        Text(
                          '${data['c_r_r_score'] ?? '미기록'}',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 40,
                            fontWeight: FontWeight.w900,
                          ),
                        ),
                        Text(
                          '${data['c_r_r_team'] ?? ''}',
                          style: const TextStyle(color: Colors.white70),
                        ),
                      ],
                    ),
                  ),
                  MemberPanel(
                    child: Column(
                      children: [
                        MemberInfoRow('기록일', data['c_r_r_date']),
                        MemberInfoRow('경기 코드', data['c_r_r_code']),
                        MemberInfoRow('구장', data['g_name']),
                        MemberInfoRow('주소', data['g_address']),
                        MemberInfoRow('매니저', data['m_name']),
                        MemberInfoRow(
                          '출석',
                          data['c_r_r_attendance'] == null
                              ? '미기록'
                              : data['c_r_r_attendance'] == true
                              ? '출석'
                              : '결석',
                        ),
                        MemberInfoRow(
                          '부상 기록',
                          data['c_r_r_injury'] == '_'
                              ? '기록 없음'
                              : data['c_r_r_injury'],
                        ),
                        MemberInfoRow('스탯 코드', data['c_r_r_statcode']),
                      ],
                    ),
                  ),
                ],
              );
            }
            return FeedItems(
              data: data,
              item: (row) => MemberPanel(
                color: Colors.white,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    '${row['g_name']}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(
                    '${row['c_r_r_date']}\n${row['c_r_r_team'] ?? ''}',
                  ),
                  trailing: Text(
                    '${row['c_r_r_score'] ?? '미기록'}',
                    style: const TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.w800,
                      color: MemberStyle.blue,
                    ),
                  ),
                  onTap: () => Navigator.push(
                    context,
                    MaterialPageRoute<void>(
                      builder: (_) => ResultPage(seq: row['c_r_r_seq'] as int),
                    ),
                  ),
                ),
              ),
            );
          },
        ),
      ]),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
