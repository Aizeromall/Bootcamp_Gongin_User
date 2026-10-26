// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
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
  late Future<Map<String, dynamic>> future;
  void load() {
    future = ref
        .read(memberApiProvider)
        .request('/inquiry/list', query: {'c_id_seq': memberId!});
  }

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

  @override
  Widget build(BuildContext context) {
    final id = ref.watch(memberIdProvider);
    if (id != memberId) {
      memberId = id;
      load();
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
            title: Text('${row['title']}'),
            subtitle: Text('${row['i_date']}'),
            children: [
              Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('${row['post']}'),
                    const Divider(),
                    Text(
                      row['inquiry_detail'] == null
                          ? '답변을 기다리고 있어요.'
                          : '답변: ${row['inquiry_detail']}',
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
// 최종 수정 일 : 2026-10-24
