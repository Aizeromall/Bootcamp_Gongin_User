// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/ui.dart';
import 'appeal_page.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
class SanctionPage extends ConsumerWidget {
  const SanctionPage({super.key});
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    // 수정 일 : 2026-10-30 / 작업자 : 김병재
    // 종목 Dropdown 제거: 제재·경고 횟수는 종목 회원 ID별이므로 가입한 종목마다 구역을 나눠 모두 보여줍니다.
    final ids = ref.watch(memberIdsProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('제재 내역')),
      body: pageContent([
        for (final id in ids) ...[
          if (ids.length > 1)
            Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 10),
              child: Text(
                '${sports[sportOfMember(id)] ?? id} 제재 내역',
                style: const TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
          sanctionSection(
            context,
            ref,
            id,
            apiQuery('/sanction/list', {'c_id_seq': id}),
          ),
        ],
        TextButton.icon(
          onPressed: () => Navigator.push(
            context,
            MaterialPageRoute<void>(builder: (_) => const AppealPage()),
          ),
          icon: const Icon(Icons.history),
          label: const Text('이의신청 내역'),
        ),
      ]),
    );
  }

  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 한 종목 회원 ID의 제재 현황·내역 구역입니다. 이의신청은 그 종목 회원 ID로 접수합니다.
  Widget sanctionSection(
    BuildContext context,
    WidgetRef ref,
    String id,
    ApiQuery query,
  ) => ApiContent(
    query: query,
    builder: (data) => Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        MemberPanel(
          color: Theme.of(context).brightness == Brightness.dark
              ? Theme.of(context).colorScheme.surfaceContainerHigh
              : const Color(0xFFFFF6E7),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '현재 상태 · 경고 ${data['warning_count'] ?? 0}회',
                style: const TextStyle(fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(
                '${data['notice'] ?? ''}',
                style: const TextStyle(fontSize: 12, height: 1.7),
              ),
              if (data['next_expire_date'] != null)
                Text(
                  '다음 소멸일 ${data['next_expire_date']}',
                  style: const TextStyle(fontSize: 12),
                ),
            ],
          ),
        ),
        FeedItems(
          data: data,
          item: (row) => MemberPanel(
            color: Colors.white,
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  '${row['tag'] ?? row['sanction_type']}',
                  style: const TextStyle(
                    color: Colors.red,
                    fontSize: 12,
                    fontWeight: FontWeight.w800,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  '${row['cs_detail']}',
                  style: const TextStyle(fontWeight: FontWeight.w700),
                ),
                MemberInfoRow('제재일', row['cs_date']),
                MemberInfoRow('이의신청 기한', row['appeal_deadline']),
                if (row['can_appeal'] == true)
                  SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () async {
                        await Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) =>
                                AppealPage(sanction: {...row, 'member_id': id}),
                          ),
                        );
                        if (context.mounted) {
                          ref.invalidate(apiDocumentProvider(query));
                        }
                      },
                      child: const Text('이의신청 하기'),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ],
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (전 종목 제재 내역 표시)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (테마 대비 적용)
