// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/all_members_state.dart';
import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/ui.dart';

class InquiryPage extends ConsumerStatefulWidget {
  const InquiryPage({super.key});
  @override
  ConsumerState<InquiryPage> createState() => _InquiryPageState();
}

class _InquiryPageState extends ConsumerState<InquiryPage> {
  final content = TextEditingController();
  int option = 2;
  bool busy = false;
  String? memberId;
  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 수정 일 : 2026-10-30 / 작업자 : 김병재
  // 종목 Dropdown 제거: 모든 종목 회원 ID로 남긴 문의를 합쳐 보여주고, 새로고침 시 종목별 조회를 모두 갱신합니다.
  ApiQuery get query => apiQuery('/inquiry/list', {'c_id_seq': '{id}'});
  Future<Map<String, dynamic>> get future =>
      ref.watch(allMembersDocumentProvider(query).future);
  void load() => ref.invalidate(apiDocumentProvider);

  @override
  void dispose() {
    content.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (content.text.trim().isEmpty) {
      showMessage(context, '문의 내용을 입력해 주세요.');
      return;
    }
    setState(() => busy = true);
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/inquiry/insert',
            body: {
              'c_id_seq': memberId,
              'i_option': option,
              'post': content.text.trim(),
            },
          );
      if (mounted) {
        content.clear();
        setState(load);
        showMessage(context, '문의가 등록되었습니다.');
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

  // 수정 일 : 2026-10-26 / 작업자 : 양태건
  // 디버그: 기존 문의·답변을 유지하고 선택한 부모 ID로 추가 답변을 전송합니다.
  Future<void> replyTo(Map<String, dynamic> row) async {
    if (busy) return;
    // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 원 문의를 남긴 종목 회원 ID로 답글을 작성합니다.
    final id = '${row['member_id'] ?? memberId}';
    final api = ref.read(memberApiProvider);
    setState(() => busy = true);
    try {
      final formKey = GlobalKey<FormState>();
      var text = '';
      var sending = false;
      String? errorText;
      final sent = await showDialog<bool>(
        context: context,
        barrierDismissible: false,
        builder: (dialogContext) => StatefulBuilder(
          builder: (dialogContext, updateDialog) => PopScope(
            canPop: !sending,
            child: AlertDialog(
              title: const Text('추가 답변 작성'),
              content: SingleChildScrollView(
                child: Form(
                  key: formKey,
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        '답변 대상: ${row['title'] ?? row['post']}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      const SizedBox(height: 16),
                      TextFormField(
                        autofocus: true,
                        readOnly: sending,
                        maxLength: 5000,
                        minLines: 3,
                        maxLines: 6,
                        decoration: const InputDecoration(
                          labelText: '추가 답변 내용',
                        ),
                        onChanged: (value) => text = value,
                        validator: (value) => (value ?? '').trim().isEmpty
                            ? '답변 내용을 입력해 주세요.'
                            : null,
                      ),
                      if (errorText != null)
                        Text(
                          errorText!,
                          style: TextStyle(
                            color: Theme.of(context).colorScheme.error,
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              actions: [
                TextButton(
                  onPressed: sending
                      ? null
                      : () => Navigator.pop(dialogContext, false),
                  child: const Text('돌아가기'),
                ),
                FilledButton(
                  onPressed: sending
                      ? null
                      : () async {
                          if (!formKey.currentState!.validate()) return;
                          updateDialog(() {
                            sending = true;
                            errorText = null;
                          });
                          try {
                            await api.request(
                              '/inquiry/insert',
                              body: {
                                'c_id_seq': id,
                                'post': text.trim(),
                                'i_comment_seq': row['i_seq'],
                              },
                            );
                            if (dialogContext.mounted) {
                              Navigator.pop(dialogContext, true);
                            }
                          } catch (error) {
                            if (dialogContext.mounted) {
                              updateDialog(() {
                                sending = false;
                                errorText = error.toString().replaceFirst(
                                  'Exception: ',
                                  '',
                                );
                              });
                            }
                          }
                        },
                  child: Text(sending ? '전송 중…' : '답변 보내기'),
                ),
              ],
            ),
          ),
        ),
      );
      if (sent == true && mounted) {
        setState(load);
        showMessage(context, '추가 답변이 등록되었습니다.');
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  // 수정 일 : 2026-10-26 / 작업자 : 양태건
  // 디버그: 원글과 모든 깊이의 후속 글, 기존 inquiry_detail 답변을 함께 표시합니다.
  Widget conversationEntry(Map<String, dynamic> row) {
    final level = int.tryParse('${row['level']}') ?? 0;
    final answered = '${row['inquiry_detail'] ?? ''}'.trim().isNotEmpty;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        (level.clamp(0, 3) * 8).toDouble(),
        12,
        0,
        12,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            '${level == 0 ? '문의' : '추가 문의'} · ${row['i_date']}',
            style: const TextStyle(color: Color(0xFF647568)),
          ),
          const SizedBox(height: 8),
          Text('${row['post']}'),
          const SizedBox(height: 12),
          if (answered) ...[
            Text(
              '답변 · ${row['h_name'] ?? '담당자'}',
              style: const TextStyle(fontWeight: FontWeight.bold),
            ),
            Text('${row['inquiry_detail']}'),
            if (row['i_answer_date'] != null) Text('${row['i_answer_date']}'),
          ] else
            const Text('답변을 기다리고 있어요.'),
          TextButton.icon(
            key: ValueKey('replyTo${row['i_seq']}'),
            onPressed: busy ? null : () => replyTo(row),
            icon: const Icon(Icons.reply),
            label: Text(answered ? '답변에 답변하기' : '추가 문의하기'),
          ),
          const Divider(),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    if (id != memberId) {
      memberId = id;
    }
    return pageContent([
      heading('무엇을 도와드릴까요?', '남겨주신 문의와 답변을 이곳에서 확인하세요.'),
      DropdownButtonFormField<int>(
        initialValue: option,
        decoration: const InputDecoration(labelText: '문의 유형'),
        items: const [
          DropdownMenuItem(value: 1, child: Text('매니저 신고 문의')),
          DropdownMenuItem(value: 2, child: Text('구장 예약 문의')),
          DropdownMenuItem(value: 3, child: Text('환불 문의')),
          DropdownMenuItem(value: 4, child: Text('기타 문의')),
        ],
        onChanged: busy ? null : (v) => setState(() => option = v!),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: content,
        readOnly: busy,
        maxLength: 5000,
        maxLines: 5,
        decoration: const InputDecoration(labelText: '문의 내용'),
      ),
      FilledButton(
        onPressed: busy ? null : submit,
        child: Text(busy ? '등록 중…' : '문의 등록'),
      ),
      const SizedBox(height: 24),
      ResultList(
        future: future,
        retry: () => setState(load),
        item: (row) => Card(
          child: ExpansionTile(
            key: PageStorageKey('inquiry:$id:${row['i_seq']}'),
            maintainState: true,
            title: Text('${row['title']}'),
            subtitle: Text('${row['i_date']}'),
            children: [
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    conversationEntry(row),
                    for (final reply in (row['replies'] as List? ?? []))
                      conversationEntry(
                        Map<String, dynamic>.from(reply as Map),
                      ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    ]);
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (전 종목 문의 통합·원 문의 종목 ID로 답글)
