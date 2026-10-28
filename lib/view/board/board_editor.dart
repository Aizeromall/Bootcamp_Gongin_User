// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';

import '../shared/ui.dart';

// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 실패 시 입력을 보존하고 확인된 저장 후에만 대화상자를 닫습니다.
class BoardEditor extends StatefulWidget {
  const BoardEditor({
    super.key,
    required this.save,
    this.initial = const {},
    this.comment = false,
  });
  final Future<void> Function(Map<String, dynamic>) save;
  final Map<String, dynamic> initial;
  final bool comment;
  @override
  State<BoardEditor> createState() => _BoardEditorState();
}

class _BoardEditorState extends State<BoardEditor> {
  final form = GlobalKey<FormState>();
  late final title = TextEditingController(
    text: '${widget.initial['board_title'] ?? ''}',
  );
  late final content = TextEditingController(
    text:
        '${widget.initial[widget.comment ? 'comment_content' : 'board_content'] ?? ''}',
  );
  late String sport = '${widget.initial['event_category'] ?? '축구'}';
  late String category = '${widget.initial['board_category'] ?? '자유'}';
  bool busy = false;
  @override
  void dispose() {
    title.dispose();
    content.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    setState(() => busy = true);
    try {
      await widget.save(
        widget.comment
            ? {'comment_content': content.text.trim()}
            : {
                'board_title': title.text.trim(),
                'board_content': content.text.trim(),
                'event_category': sport,
                'board_category': category,
              },
      );
      if (mounted) Navigator.pop(context, true);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 게시글 작성은 전체 화면, 짧은 댓글 수정·답글은 대화상자로 구분합니다.
  @override
  Widget build(BuildContext context) {
    final fields = Form(
      key: form,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (!widget.comment) ...[
            DropdownButtonFormField<String>(
              initialValue: sport,
              decoration: const InputDecoration(labelText: '종목'),
              items: [
                '축구',
                '배구',
                '농구',
                '야구',
              ].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
              onChanged: busy ? null : (v) => sport = v!,
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              initialValue: category,
              decoration: const InputDecoration(labelText: '분류'),
              items: [
                '팀원모집',
                '매칭신청',
                '후기',
                '자유',
              ].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
              onChanged: busy ? null : (v) => category = v!,
            ),
            const SizedBox(height: 18),
            TextFormField(
              controller: title,
              enabled: !busy,
              maxLength: 200,
              decoration: const InputDecoration(labelText: '제목'),
              validator: (v) =>
                  (v ?? '').trim().isEmpty ? '제목을 입력해 주세요.' : null,
            ),
          ],
          const SizedBox(height: 12),
          TextFormField(
            controller: content,
            enabled: !busy,
            minLines: widget.comment ? 4 : 10,
            maxLines: widget.comment ? 9 : 18,
            maxLength: widget.comment ? 5000 : 10000,
            decoration: const InputDecoration(labelText: '내용'),
            validator: (v) => (v ?? '').trim().isEmpty ? '내용을 입력해 주세요.' : null,
          ),
        ],
      ),
    );
    final save = FilledButton(
      onPressed: busy ? null : submit,
      child: Text(busy ? '저장 중…' : '저장'),
    );
    if (widget.comment) {
      return PopScope(
        canPop: !busy,
        child: AlertDialog(
          title: const Text('댓글 작성·수정'),
          content: SizedBox(
            width: 460,
            child: SingleChildScrollView(child: fields),
          ),
          actions: [
            TextButton(
              onPressed: busy ? null : () => Navigator.pop(context),
              child: const Text('돌아가기'),
            ),
            save,
          ],
        ),
      );
    }
    return Dialog.fullscreen(
      child: PopScope(
        canPop: !busy,
        child: Scaffold(
          appBar: AppBar(
            leading: IconButton(
              tooltip: '글쓰기 닫기',
              onPressed: busy ? null : () => Navigator.pop(context),
              icon: const Icon(Icons.close),
            ),
            title: const Text('게시글 작성·수정'),
            actions: [
              Padding(padding: const EdgeInsets.only(right: 12), child: save),
            ],
          ),
          body: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 700),
              child: ListView(
                padding: const EdgeInsets.all(20),
                children: [fields],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
