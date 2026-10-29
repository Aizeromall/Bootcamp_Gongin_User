// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/team_state.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 팀원 조회 API가 없으므로 회원 아이디를 입력받고 실제 소속·권한은 서버가 검증합니다.
class TeamCaptainDialog extends ConsumerStatefulWidget {
  const TeamCaptainDialog({super.key, required this.transferKey});
  final CaptainKey transferKey;
  @override
  ConsumerState<TeamCaptainDialog> createState() => _TeamCaptainDialogState();
}

class _TeamCaptainDialogState extends ConsumerState<TeamCaptainDialog> {
  final form = GlobalKey<FormState>();
  final member = TextEditingController();
  bool confirming = false;
  String? failure;
  @override
  void dispose() {
    member.dispose();
    super.dispose();
  }

  Future<void> transfer() async {
    if (confirming || ref.read(captainTransferProvider(widget.transferKey))) {
      return;
    }
    if (!form.currentState!.validate()) return;
    final target = member.text.trim();
    setState(() {
      confirming = true;
      failure = null;
    });
    try {
      final confirmed = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('팀장을 넘기시겠어요?'),
          content: Text(
            '$target 회원에게 팀장 권한을 넘깁니다.\n\n진행 중인 구장대여와 연결된 매칭 글도 새 팀장에게 이전됩니다. 결제 기록은 기존 결제자에게 유지됩니다.\n\n위임 후에는 팀장 기능을 사용할 수 없습니다.',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('돌아가기'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('위임 확정'),
            ),
          ],
        ),
      );
      if (!mounted || confirmed != true) return;
      final done = await ref
          .read(captainTransferProvider(widget.transferKey).notifier)
          .submit(target);
      if (mounted && done) Navigator.pop(context, true);
    } catch (error) {
      // 실패한 경우 입력을 유지하며 403·409 등 서버의 거절 사유를 표시합니다.
      if (mounted) setState(() => failure = error.toString());
    } finally {
      if (mounted) setState(() => confirming = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final submitting = ref.watch(captainTransferProvider(widget.transferKey));
    final busy = confirming || submitting;
    final active =
        ref.watch(sessionProvider) != null &&
        ref.watch(memberIdProvider) == widget.transferKey.memberId;
    return PopScope(
      canPop: !busy,
      child: AlertDialog(
        title: const Text('팀장 위임'),
        content: SingleChildScrollView(
          child: Form(
            key: form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('같은 팀에 가입 중인 팀원의 종목별 회원 아이디를 입력해 주세요. 예: member_01'),
                if (failure != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    failure!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                TextFormField(
                  controller: member,
                  enabled: !busy && active,
                  maxLength: 50,
                  decoration: const InputDecoration(labelText: '새 팀장 회원 아이디'),
                  validator: (value) {
                    final id = value?.trim() ?? '';
                    if (id.isEmpty) return '회원 아이디를 입력해 주세요.';
                    if (id == widget.transferKey.memberId) {
                      return '본인에게는 위임할 수 없습니다.';
                    }
                    return null;
                  },
                ),
              ],
            ),
          ),
        ),
        actions: [
          TextButton(
            onPressed: busy ? null : () => Navigator.pop(context),
            child: const Text('취소'),
          ),
          FilledButton(
            onPressed: busy || !active ? null : transfer,
            child: Text(busy ? '처리 중…' : '팀장 위임'),
          ),
        ],
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
