// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/ui.dart';

class AnnouncementPage extends ConsumerStatefulWidget {
  const AnnouncementPage({super.key});
  @override
  ConsumerState<AnnouncementPage> createState() => _AnnouncementPageState();
}

class _AnnouncementPageState extends ConsumerState<AnnouncementPage> {
  String? category;
  int offset = 0;
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('공지사항')),
    body: pageContent([
      heading('공In 소식', '운영 소식과 이벤트를 확인하세요.'),
      ApiContent(
        query: apiQuery('/announce/categories'),
        builder: (data) => Wrap(
          spacing: 8,
          children: [
            for (final v in [null, ...data['results'] as List])
              ChoiceChip(
                label: Text('${v ?? '전체'}'),
                selected: category == v,
                onSelected: (_) => setState(() {
                  category = v as String?;
                  offset = 0;
                }),
              ),
          ],
        ),
      ),
      ApiContent(
        query: apiQuery('/announce', {
          'limit': '20',
          'offset': '$offset',
          'a_classify': ?category,
        }),
        builder: (data) => Column(
          children: [
            FeedItems(
              data: data,
              item: (row) => Card(
                child: ExpansionTile(
                  title: Text('${row['a_title']}'),
                  subtitle: Text(
                    '${row['a_classify'] ?? '공지'} · ${row['a_date'] ?? ''}',
                  ),
                  childrenPadding: const EdgeInsets.all(20),
                  expandedCrossAxisAlignment: CrossAxisAlignment.start,
                  children: [Text('${row['a_detail'] ?? ''}')],
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
                  onPressed: apiRows(data).length < 20
                      ? null
                      : () => setState(() => offset += 20),
                  child: const Text('다음'),
                ),
              ],
            ),
          ],
        ),
      ),
    ]),
  );
}
// 최종 수정 일 : 2026-10-27 / 작업자 : 양태건
