// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
class TeamCreatePage extends ConsumerStatefulWidget {
  const TeamCreatePage({super.key});
  @override
  ConsumerState<TeamCreatePage> createState() => _TeamCreatePageState();
}

class _TeamCreatePageState extends ConsumerState<TeamCreatePage> {
  final form = GlobalKey<FormState>();
  final name = TextEditingController();
  final logo = TextEditingController();
  bool busy = false;
  @override
  void dispose() {
    name.dispose();
    logo.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() => busy = true);
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/team/create',
            body: {
              'c_id_seq': ref.read(memberIdProvider),
              't_name': name.text.trim(),
              if (logo.text.trim().isNotEmpty) 't_logo': logo.text.trim(),
            },
          );
      if (!mounted) return;
      ref.invalidate(apiDocumentProvider);
      Navigator.pop(context, true);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('팀 개설')),
    bottomNavigationBar: SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FilledButton(
          onPressed: busy ? null : submit,
          child: Text(busy ? '개설 중…' : '팀 만들기'),
        ),
      ),
    ),
    body: Form(
      key: form,
      child: pageContent([
        MemberPanel(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text(
                '함께 뛸 우리 팀을 만들어요',
                style: TextStyle(fontSize: 21, fontWeight: FontWeight.w800),
              ),
              const SizedBox(height: 8),
              Text(
                '현재 종목 · ${sports[ref.watch(sportProvider)]}',
                style: const TextStyle(color: MemberStyle.blue),
              ),
              const Text(
                '팀을 개설한 회원이 팀장이 됩니다.',
                style: TextStyle(fontSize: 12, color: MemberStyle.muted),
              ),
            ],
          ),
        ),
        TextFormField(
          key: const ValueKey('teamName'),
          controller: name,
          enabled: !busy,
          maxLength: 50,
          decoration: const InputDecoration(labelText: '팀 이름'),
          validator: (v) => (v ?? '').trim().isEmpty ? '팀 이름을 입력해 주세요.' : null,
        ),
        const SizedBox(height: 18),
        TextFormField(
          controller: logo,
          enabled: !busy,
          maxLength: 255,
          decoration: const InputDecoration(
            labelText: '팀 로고 URL (선택)',
            hintText: '이미 등록된 이미지 주소',
          ),
        ),
      ]),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
