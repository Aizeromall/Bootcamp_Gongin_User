// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';
import '../../vm/member_state.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 증빙은 실제 API가 허용하는 공유 링크로만 받고 파일 업로드를 가장하지 않습니다.
class AppealPage extends ConsumerStatefulWidget {
  const AppealPage({super.key, this.sanction});
  final Map<String, dynamic>? sanction;
  @override
  ConsumerState<AppealPage> createState() => _AppealPageState();
}

class _AppealPageState extends ConsumerState<AppealPage> {
  final form = GlobalKey<FormState>();
  final reason = TextEditingController();
  final evidence = TextEditingController();
  String type = '사실과 다름';
  bool busy = false;
  @override
  void dispose() {
    reason.dispose();
    evidence.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy || !form.currentState!.validate()) return;
    // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 제재를 받은 종목 회원 ID로 이의신청합니다.
    final id = '${widget.sanction?['member_id'] ?? ref.read(memberIdProvider)}';
    setState(() => busy = true);
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/appeal/insert',
            body: {
              'c_id_seq': id,
              'cs_seq': widget.sanction!['cs_seq'],
              'a_type': type,
              'a_reason': reason.text.trim(),
              'a_evidence': evidence.text
                  .split('\n')
                  .map((v) => v.trim())
                  .where((v) => v.isNotEmpty)
                  .toList(),
            },
          );
      if (!mounted) return;
      ref.invalidate(
        apiDocumentProvider(apiQuery('/appeal/list', {'c_id_seq': id})),
      );
      showMessage(context, '이의신청이 접수되었습니다.');
      Navigator.pop(context, true);
    } catch (error) {
      if (mounted) showMessage(context, error);
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final writing = widget.sanction != null;
    return Scaffold(
      appBar: AppBar(title: Text(writing ? '이의신청' : '이의신청 내역')),
      bottomNavigationBar: !writing
          ? null
          : SafeArea(
              top: false,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: FilledButton(
                  onPressed: busy ? null : submit,
                  child: Text(busy ? '접수 중…' : '이의신청 제출'),
                ),
              ),
            ),
      body: Form(
        key: form,
        child: pageContent(
          writing
              ? [
                  MemberPanel(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${widget.sanction!['sanction_type'] ?? '제재'}',
                          style: const TextStyle(
                            color: Colors.red,
                            fontWeight: FontWeight.w800,
                          ),
                        ),
                        const SizedBox(height: 8),
                        Text('${widget.sanction!['cs_detail'] ?? ''}'),
                      ],
                    ),
                  ),
                  const Text(
                    '이의 사유',
                    style: TextStyle(fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 10),
                  Wrap(
                    spacing: 6,
                    children: [
                      for (final value in ['사실과 다름', '과도한 제재', '신고자 오인'])
                        ChoiceChip(
                          label: Text(value),
                          selected: type == value,
                          onSelected: busy
                              ? null
                              : (_) => setState(() => type = value),
                        ),
                    ],
                  ),
                  const SizedBox(height: 18),
                  TextFormField(
                    controller: reason,
                    enabled: !busy,
                    maxLength: 1000,
                    minLines: 5,
                    maxLines: 9,
                    decoration: const InputDecoration(
                      labelText: '상세 내용',
                      hintText: '이의신청 내용을 구체적으로 작성해 주세요.',
                    ),
                    validator: (v) =>
                        (v ?? '').trim().length < 5 ? '5자 이상 입력해 주세요.' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: evidence,
                    enabled: !busy,
                    minLines: 2,
                    maxLines: 5,
                    decoration: const InputDecoration(
                      labelText: '증빙 공유 링크 (선택)',
                      hintText: 'http(s):// 주소를 한 줄에 하나씩, 최대 3개 입력',
                    ),
                    validator: (v) {
                      final links = (v ?? '')
                          .split('\n')
                          .map((v) => v.trim())
                          .where((v) => v.isNotEmpty)
                          .toList();
                      if (links.length > 3 ||
                          links.toSet().length != links.length) {
                        return '서로 다른 링크를 최대 3개 입력해 주세요.';
                      }
                      if (links.any(
                        (link) =>
                            !RegExp(r'^https?://[^\s,\[\]]+$').hasMatch(link),
                      )) {
                        return '올바른 http(s):// 링크를 입력해 주세요.';
                      }
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  const Text(
                    '검토 결과와 진행 상황은 이의신청 내역에서 확인할 수 있습니다.',
                    style: TextStyle(fontSize: 12, color: MemberStyle.muted),
                  ),
                ]
              : [
                  // 수정 일 : 2026-10-30 / 작업자 : 김병재 — 모든 종목의 이의신청 내역을 합쳐 표시
                  ApiContent(
                    allMembers: true,
                    query: apiQuery('/appeal/list', {'c_id_seq': '{id}'}),
                    builder: (data) => FeedItems(
                      data: data,
                      item: (row) => MemberPanel(
                        color: Colors.white,
                        child: ExpansionTile(
                          tilePadding: EdgeInsets.zero,
                          title: Text(
                            '${row['title']}',
                            style: const TextStyle(fontWeight: FontWeight.w700),
                          ),
                          subtitle: Text(
                            '${row['state_text']} · ${row['a_date']}',
                          ),
                          children: [
                            Align(
                              alignment: Alignment.centerLeft,
                              child: Text(
                                '${row['a_reason'] ?? ''}',
                                style: const TextStyle(height: 1.7),
                              ),
                            ),
                            const SizedBox(height: 14),
                            for (final step in row['steps'] as List? ?? [])
                              ListTile(
                                dense: true,
                                leading: Icon(
                                  step['done'] == true
                                      ? Icons.check_circle
                                      : Icons.circle_outlined,
                                  color: step['done'] == true
                                      ? MemberStyle.blue
                                      : MemberStyle.muted,
                                ),
                                title: Text('${step['name']}'),
                              ),
                            for (final link in row['a_evidence'] as List? ?? [])
                              SelectableText(
                                '$link',
                                style: const TextStyle(
                                  color: MemberStyle.blue,
                                  fontSize: 12,
                                ),
                              ),
                          ],
                        ),
                      ),
                    ),
                  ),
                ],
        ),
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 김병재 (제재 종목 회원 ID로 이의신청·전 종목 내역)
