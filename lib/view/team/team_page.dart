// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/ui.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import 'team_create_page.dart';
import 'team_detail_page.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 팀 생성·가입 신청·탈퇴·폐지를 실제 API와 연결합니다. 권한 판단은 서버가 최종 수행합니다.
class TeamPage extends ConsumerStatefulWidget {
  const TeamPage({super.key});
  @override
  ConsumerState<TeamPage> createState() => _TeamPageState();
}

class _TeamPageState extends ConsumerState<TeamPage> {
  final search = TextEditingController();
  String keyword = '';
  int offset = 0;
  bool busy = false;
  ApiQuery get query => apiQuery('/team/select', {
    'keyword': keyword,
    'offset': '$offset',
    'limit': '20',
  });
  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  Future<void> create() async {
    await Navigator.push(
      context,
      MaterialPageRoute<void>(builder: (_) => const TeamCreatePage()),
    );
    if (mounted) ref.invalidate(apiDocumentProvider(query));
  }

  Future<void> mutate(
    String path, {
    Map<String, dynamic>? body,
    String? method,
    String? confirm,
  }) async {
    if (busy) return;
    final id = ref.read(memberIdProvider);
    setState(() => busy = true);
    try {
      if (confirm != null) {
        final ok = await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(confirm),
            content: const Text('진행하시겠어요?'),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('돌아가기'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('확인'),
              ),
            ],
          ),
        );
        if (ok != true || !mounted) return;
      }
      await ref
          .read(memberApiProvider)
          .request(
            path,
            body: body,
            method: method,
            query: method == 'DELETE' ? {'c_id_seq': id} : null,
          );
      if (!mounted || ref.read(memberIdProvider) != id) return;
      ref.invalidate(apiDocumentProvider);
      showMessage(
        context,
        path.contains('/apply/')
            ? '가입 신청이 완료되었습니다. 팀장 승인을 기다려 주세요.'
            : '팀 정보가 변경되었습니다.',
      );
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    return pageContent([
      heading('함께 뛰는 우리 팀', '팀을 개설하면 팀장이 됩니다. 팀장이 승인한 후 가입이 완료됩니다.'),
      FilledButton.icon(
        onPressed: busy ? null : create,
        icon: const Icon(Icons.group_add_outlined),
        label: const Text('팀 개설'),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: search,
        maxLength: 50,
        decoration: const InputDecoration(
          labelText: '팀 이름 검색',
          suffixIcon: Icon(Icons.search),
        ),
        onSubmitted: (v) => setState(() {
          keyword = v.trim();
          offset = 0;
        }),
      ),
      ApiContent(
        query: query,
        builder: (data) => Column(
          children: [
            FeedItems(
              data: data,
              item: (row) => Card(
                child: Padding(
                  padding: const EdgeInsets.all(18),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      // 수정 일 : 2026-10-28 / 작업자 : 양태건
                      Row(
                        children: [
                          const CircleAvatar(
                            backgroundColor: MemberStyle.greenSurface,
                            child: Icon(
                              Icons.shield_outlined,
                              color: MemberStyle.green,
                            ),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Text(
                              '${row['t_name']}',
                              style: const TextStyle(
                                fontSize: 17,
                                fontWeight: FontWeight.w800,
                              ),
                            ),
                          ),
                          if (row['captain_id'] == id)
                            const MemberStatusBadge(
                              '팀장',
                              color: MemberStyle.green,
                            ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      Text(
                        '팀장 ${row['captain_name'] ?? '미등록'} · ${row['member_count'] ?? 0}명',
                      ),
                      TextButton.icon(
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute<void>(
                            builder: (_) =>
                                TeamDetailPage(id: row['t_id'] as int),
                          ),
                        ),
                        icon: const Icon(Icons.groups_outlined),
                        label: const Text('팀 정보'),
                      ),
                      if (row['t_rating'] != null)
                        Text('팀 점수 ${row['t_rating']}'),
                      Wrap(
                        spacing: 8,
                        children: [
                          TextButton(
                            onPressed: busy
                                ? null
                                : () => mutate(
                                    '/team/apply/${row['t_id']}',
                                    body: {'c_id_seq': id},
                                    confirm: '팀 가입',
                                  ),
                            child: const Text('가입 신청'),
                          ),
                          if (row['captain_id'] != id)
                            TextButton(
                              onPressed: busy
                                  ? null
                                  : () => mutate(
                                      '/team/leave/${row['t_id']}',
                                      method: 'DELETE',
                                      confirm: '팀 탈퇴',
                                    ),
                              child: const Text('탈퇴'),
                            ),
                          if (row['captain_id'] == id)
                            TextButton(
                              onPressed: busy
                                  ? null
                                  : () => mutate(
                                      '/team/delete/${row['t_id']}',
                                      method: 'DELETE',
                                      confirm: '팀 폐지',
                                    ),
                              child: const Text('팀 폐지'),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
              ),
            ),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                TextButton(
                  onPressed: offset == 0
                      ? null
                      : () => setState(() => offset -= 20),
                  child: const Text('이전'),
                ),
                Text('${offset ~/ 20 + 1} 페이지'),
                TextButton(
                  onPressed: offset + 20 >= (data['total'] as num? ?? 0)
                      ? null
                      : () => setState(() => offset += 20),
                  child: const Text('다음'),
                ),
              ],
            ),
          ],
        ),
      ),
    ]);
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
