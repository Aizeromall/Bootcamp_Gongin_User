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
// 팀장이 가진 실제 구장대여를 선택하여 신청 가능한 매칭 글을 생성합니다.
class TeamMatchPostPage extends ConsumerStatefulWidget {
  const TeamMatchPostPage({super.key});
  @override
  ConsumerState<TeamMatchPostPage> createState() => _TeamMatchPostPageState();
}

class _TeamMatchPostPageState extends ConsumerState<TeamMatchPostPage> {
  final content = TextEditingController();
  int? selected;
  bool busy = false;
  @override
  void dispose() {
    content.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || selected == null) return;
    final id = ref.read(memberIdProvider);
    setState(() => busy = true);
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/team_match/post',
            body: {
              'c_id_seq': id,
              'r_seq': selected,
              'board_content': content.text.trim(),
            },
          );
      if (!mounted) return;
      ref.invalidate(
        apiDocumentProvider(
          apiQuery('/team_match/rentals/${Uri.encodeComponent(id)}'),
        ),
      );
      showMessage(context, '구장대여와 연결된 매칭 글이 등록되었습니다.');
      Navigator.pop(context, true);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('팀 매칭 글쓰기')),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton(
            onPressed: busy || selected == null ? null : submit,
            child: Text(busy ? '등록 중…' : '매칭 글 등록'),
          ),
        ),
      ),
      body: pageContent([
        const Text(
          '대여한 경기 선택',
          style: TextStyle(fontSize: 20, fontWeight: FontWeight.w800),
        ),
        const SizedBox(height: 8),
        const Text(
          '본인 팀의 대여 중, 매칭 글이 없는 예약을 선택하세요.',
          style: TextStyle(fontSize: 12, color: MemberStyle.muted),
        ),
        const SizedBox(height: 20),
        ApiContent(
          query: apiQuery('/team_match/rentals/${Uri.encodeComponent(id)}'),
          builder: (data) => FeedItems(
            data: data,
            item: (row) {
              final disabled = busy || row['has_post'] == true;
              return MemberPanel(
                color: selected == row['r_seq']
                    ? const Color(0xFFEAF1FF)
                    : Colors.white,
                child: ListTile(
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    '${row['g_name']}',
                    style: const TextStyle(fontWeight: FontWeight.w800),
                  ),
                  subtitle: Text(
                    '${row['r_date']} · ${row['rs_time']} ~ ${row['re_time']}\n${row['has_post'] == true ? '매칭 글 등록 완료' : '선택 가능'}',
                  ),
                  leading: Icon(
                    selected == row['r_seq']
                        ? Icons.radio_button_checked
                        : Icons.radio_button_off,
                    color: disabled ? MemberStyle.muted : MemberStyle.blue,
                  ),
                  onTap: disabled
                      ? null
                      : () => setState(() => selected = row['r_seq'] as int),
                ),
              );
            },
          ),
        ),
        const SizedBox(height: 16),
        TextField(
          controller: content,
          enabled: !busy,
          maxLength: 1000,
          minLines: 4,
          maxLines: 8,
          decoration: const InputDecoration(
            labelText: '추가 내용',
            hintText: '상대 팀에게 전할 내용을 입력하세요.',
          ),
        ),
      ]),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
