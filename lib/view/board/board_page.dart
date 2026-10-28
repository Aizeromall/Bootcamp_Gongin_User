// 2026-10-27
// 작업자 : 양태건
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../../vm/board_state.dart';
import '../shared/api_content.dart';
import '../shared/member_style.dart';
import 'board_editor.dart';
import 'board_detail_page.dart';
import 'board_widgets.dart';
import 'board_match_action.dart';
import '../team_match/team_match_post_page.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 종목 탭과 카테고리 칩·최신 글 강조·행 목록을 현재 목록 API 필드로 구성합니다.
class BoardPage extends ConsumerStatefulWidget {
  const BoardPage({super.key, this.initialCategory = '전체'});
  final String initialCategory;
  @override
  ConsumerState<BoardPage> createState() => _BoardPageState();
}

class _BoardPageState extends ConsumerState<BoardPage> {
  final search = TextEditingController();
  bool searchVisible = false;
  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  Future<void> write(BoardFilter filter) async {
    final id = ref.read(memberIdProvider);
    await showDialog<bool>(
      context: context,
      builder: (_) => BoardEditor(
        initial: {
          'event_category': sports[filter.sport],
          'board_category': filter.category == '전체' ? '자유' : filter.category,
        },
        save: (body) async {
          await ref
              .read(memberApiProvider)
              .request('/board/insert', body: {...body, 'c_id_seq': id});
          if (mounted) ref.invalidate(apiDocumentProvider(filter.query));
        },
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final provider = boardFiltersProvider(widget.initialCategory);
    final filter = ref.watch(provider);
    final notifier = ref.read(provider.notifier);
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        toolbarHeight: 72,
        titleSpacing: 0,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${sports[filter.sport]} 게시판',
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: MemberStyle.ink,
              ),
            ),
            const SizedBox(height: 3),
            const Text(
              '팀원모집 · 매칭신청 · 후기 · 자유',
              style: TextStyle(fontSize: 11, color: MemberStyle.muted),
            ),
          ],
        ),
        actions: [
          IconButton(
            tooltip: '게시판 검색',
            onPressed: () => setState(() => searchVisible = !searchVisible),
            icon: const Icon(Icons.search),
          ),
          PopupMenuButton<String>(
            tooltip: '게시판 메뉴',
            onSelected: (_) =>
                ref.invalidate(apiDocumentProvider(filter.query)),
            itemBuilder: (_) => const [
              PopupMenuItem(value: 'refresh', child: Text('새로고침')),
            ],
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        elevation: 0,
        focusElevation: 0,
        hoverElevation: 0,
        highlightElevation: 0,
        onPressed: () => write(filter),
        backgroundColor: MemberStyle.blue,
        foregroundColor: Colors.white,
        icon: const Icon(Icons.edit_outlined),
        label: const Text('글쓰기'),
      ),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 900),
          child: Column(
            children: [
              Container(
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: MemberStyle.line)),
                ),
                child: Row(
                  children: [
                    for (final code in [1, 4, 2, 3])
                      Expanded(
                        child: InkWell(
                          key: ValueKey('boardSport$code'),
                          onTap: () => notifier.selectSport(code),
                          child: Container(
                            padding: const EdgeInsets.symmetric(vertical: 14),
                            decoration: BoxDecoration(
                              border: Border(
                                bottom: BorderSide(
                                  color: filter.sport == code
                                      ? const Color(0xFF172541)
                                      : Colors.transparent,
                                  width: 2,
                                ),
                              ),
                            ),
                            child: Text(
                              '${boardEmoji[code]} ${sports[code]}',
                              textAlign: TextAlign.center,
                              style: TextStyle(
                                fontSize: 14,
                                fontWeight: filter.sport == code
                                    ? FontWeight.w800
                                    : FontWeight.w500,
                                color: filter.sport == code
                                    ? const Color(0xFF172541)
                                    : MemberStyle.muted,
                              ),
                            ),
                          ),
                        ),
                      ),
                  ],
                ),
              ),
              if (searchVisible)
                Padding(
                  padding: const EdgeInsets.fromLTRB(16, 12, 16, 0),
                  child: TextField(
                    controller: search,
                    maxLength: 200,
                    decoration: const InputDecoration(
                      hintText: '제목·내용 검색',
                      prefixIcon: Icon(Icons.search),
                      isDense: true,
                    ),
                    onSubmitted: notifier.search,
                  ),
                ),
              SizedBox(
                height: 62,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 12,
                    vertical: 12,
                  ),
                  children: [
                    for (final category in boardCategories)
                      Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: ChoiceChip(
                          label: Text(category),
                          selected: filter.category == category,
                          showCheckmark: false,
                          selectedColor: const Color(0xFFFDEAE7),
                          backgroundColor: MemberStyle.surface,
                          side: BorderSide.none,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(24),
                          ),
                          labelStyle: TextStyle(
                            fontSize: 12,
                            fontWeight: filter.category == category
                                ? FontWeight.w800
                                : FontWeight.w500,
                            color: filter.category == category
                                ? const Color(0xFFD83222)
                                : MemberStyle.muted,
                          ),
                          onSelected: (_) => notifier.selectCategory(category),
                        ),
                      ),
                  ],
                ),
              ),
              if (filter.category == '매칭신청')
                Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  child: OutlinedButton.icon(
                    icon: const Icon(Icons.add_link),
                    label: const Text('대여 경기로 매칭 글쓰기'),
                    onPressed: () async {
                      await Navigator.push(
                        context,
                        MaterialPageRoute<void>(
                          builder: (_) => const TeamMatchPostPage(),
                        ),
                      );
                      if (mounted) {
                        ref.invalidate(apiDocumentProvider(filter.query));
                      }
                    },
                  ),
                ),
              Expanded(
                child: RefreshIndicator(
                  onRefresh: () async {
                    ref.invalidate(apiDocumentProvider(filter.query));
                    try {
                      await ref.read(apiDocumentProvider(filter.query).future);
                    } catch (_) {
                      // ApiContent가 오류와 재시도를 표시하므로 당겨서 새로고침은 정상 종료합니다.
                    }
                  },
                  child: ListView(
                    physics: const AlwaysScrollableScrollPhysics(),
                    padding: const EdgeInsets.only(bottom: 100),
                    children: [
                      ApiContent(
                        query: filter.query,
                        builder: (data) {
                          final rows = apiRows(data);
                          return Column(
                            children: [
                              if (rows.isEmpty)
                                const Padding(
                                  padding: EdgeInsets.all(32),
                                  child: Text('아직 표시할 내역이 없습니다.'),
                                ),
                              for (var index = 0; index < rows.length; index++)
                                _post(
                                  rows[index],
                                  filter,
                                  first: filter.offset == 0 && index == 0,
                                ),
                              Row(
                                mainAxisAlignment:
                                    MainAxisAlignment.spaceBetween,
                                children: [
                                  TextButton(
                                    onPressed: filter.offset == 0
                                        ? null
                                        : () =>
                                              notifier.page(filter.offset - 20),
                                    child: const Text('이전'),
                                  ),
                                  Text(
                                    '${filter.offset ~/ 20 + 1} 페이지',
                                    style: const TextStyle(
                                      fontSize: 12,
                                      color: MemberStyle.muted,
                                    ),
                                  ),
                                  TextButton(
                                    onPressed:
                                        filter.offset + 20 >=
                                            (data['total'] as num? ?? 0)
                                        ? null
                                        : () =>
                                              notifier.page(filter.offset + 20),
                                    child: const Text('다음'),
                                  ),
                                ],
                              ),
                            ],
                          );
                        },
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _post(
    Map<String, dynamic> row,
    BoardFilter filter, {
    required bool first,
  }) => Container(
    margin: first ? const EdgeInsets.fromLTRB(16, 0, 16, 12) : EdgeInsets.zero,
    decoration: BoxDecoration(
      border: first
          ? Border.all(color: MemberStyle.line)
          : const Border(bottom: BorderSide(color: MemberStyle.line)),
      borderRadius: first ? BorderRadius.circular(14) : null,
    ),
    child: Material(
      color: Colors.white,
      borderRadius: first ? BorderRadius.circular(14) : null,
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: () async {
          await Navigator.push(
            context,
            MaterialPageRoute<void>(
              builder: (_) => BoardDetailPage(seq: row['bulletin_seq'] as int),
            ),
          );
          if (mounted) ref.invalidate(apiDocumentProvider(filter.query));
        },
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              if (first)
                const Padding(
                  padding: EdgeInsets.only(bottom: 14),
                  child: Text(
                    '최신 게시글',
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w800,
                      color: MemberStyle.blue,
                    ),
                  ),
                ),
              BoardCategoryBadge('${row['board_category']}'),
              const SizedBox(height: 9),
              // 수정 일 : 2026-10-28 / 작업자 : 양태건
              // 매칭신청은 오른쪽에서 바로 신청하거나 작성 팀장이 신청 목록을 확인합니다.
              Row(
                crossAxisAlignment: CrossAxisAlignment.center,
                children: [
                  Expanded(
                    child: Text(
                      '${row['board_title']}',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w800,
                        color: MemberStyle.ink,
                        height: 1.5,
                      ),
                    ),
                  ),
                  if (row['board_category'] == '매칭신청') ...[
                    const SizedBox(width: 12),
                    BoardMatchAction(
                      key: ValueKey('boardMatchAction${row['bulletin_seq']}'),
                      post: row,
                    ),
                  ],
                ],
              ),
              const SizedBox(height: 12),
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '${boardDateLabel(row['board_date'])}  |  ${row['c_name'] ?? '회원'}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: MemberStyle.muted,
                      ),
                    ),
                  ),
                  if (row['board_views'] != null)
                    Text(
                      '조회 ${row['board_views']}',
                      style: const TextStyle(
                        fontSize: 11,
                        color: MemberStyle.muted,
                      ),
                    ),
                ],
              ),
            ],
          ),
        ),
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
