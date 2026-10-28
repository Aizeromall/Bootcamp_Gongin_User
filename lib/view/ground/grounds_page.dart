// 최초 작업자 : 최현준 / 최초 작업일 : 2026-10-24
// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 첨부 홈 목업의 종목 카드·배너·바로가기·필터·목록을 실제 구장 데이터에 적용합니다.
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';
import 'ground_detail_page.dart';
import '../reservation/reservation_page.dart';
import '../board/board_page.dart';

const _regions = {
  '서울': ['서울', '서울시', '서울특별시'],
  '경기': ['경기', '경기도'],
  '인천': ['인천', '인천시', '인천광역시'],
  '부산': ['부산', '부산시', '부산광역시'],
  '대구': ['대구', '대구시', '대구광역시'],
  '광주': ['광주', '광주시', '광주광역시'],
  '대전': ['대전', '대전시', '대전광역시'],
  '울산': ['울산', '울산시', '울산광역시'],
  '세종': ['세종', '세종시', '세종특별자치시'],
  '강원': ['강원', '강원도', '강원특별자치도'],
  '충북': ['충북', '충청북도'],
  '충남': ['충남', '충청남도'],
  '전북': ['전북', '전라북도', '전북특별자치도'],
  '전남': ['전남', '전라남도'],
  '경북': ['경북', '경상북도'],
  '경남': ['경남', '경상남도'],
  '제주': ['제주', '제주도', '제주특별자치도'],
};

class GroundsPage extends ConsumerStatefulWidget {
  const GroundsPage({
    super.key,
    this.onOpenBoard,
    this.onOpenTeamMatch,
    this.matchOnly = false,
  });
  final bool matchOnly;
  final VoidCallback? onOpenBoard;
  final VoidCallback? onOpenTeamMatch;
  @override
  ConsumerState<GroundsPage> createState() => _GroundsPageState();
}

class _GroundsPageState extends ConsumerState<GroundsPage> {
  final search = TextEditingController();
  final scroll = ScrollController();
  final searchFocus = FocusNode();
  final filterKey = GlobalKey();
  String searchField = 'g_name';
  String keyword = '';
  bool searchVisible = false;
  final query = apiQuery('/ground');
  void refresh() => ref.invalidate(apiDocumentProvider(query));
  @override
  void dispose() {
    search.dispose();
    scroll.dispose();
    searchFocus.dispose();
    super.dispose();
  }

  bool matches(Map<String, dynamic> row, int sport, String region) {
    final sportText =
        RegExp(r'(?:^|/)\s*종목\s*:\s*([^/]+)')
            .firstMatch('${row['g_information'] ?? ''}')
            ?.group(1) ??
        '';
    final supported = sportText.split(RegExp(r'[,·、\s]+'));
    final first = '${row['g_address'] ?? ''}'
        .trim()
        .split(RegExp(r'\s+'))
        .first;
    return supported.contains(sports[sport]) &&
        (region == '전체 지역' || (_regions[region]?.contains(first) ?? false)) &&
        '${row[searchField] ?? ''}'.toLowerCase().contains(keyword);
  }

  void browse() {
    final target = filterKey.currentContext;
    if (target != null) {
      Scrollable.ensureVisible(
        target,
        duration: const Duration(milliseconds: 300),
        alignment: 0.05,
      );
    } else if (scroll.hasClients) {
      scroll.animateTo(
        math.min(360, scroll.position.maxScrollExtent),
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    }
  }

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 게시판 자체 AppBar를 사용하여 중복 헤더 없이 이동합니다.
  void openBoard({bool matching = false}) {
    final callback = matching ? widget.onOpenTeamMatch : widget.onOpenBoard;
    if (callback != null) {
      callback();
      return;
    }
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (_) => BoardPage(initialCategory: matching ? '매칭신청' : '전체'),
      ),
    );
  }

  void reserve(Map<String, dynamic> row, int sport) {
    final registered =
        (ref.read(sessionProvider)?['preferred_stocks'] as List? ?? [])
            .map((v) => int.tryParse('$v'))
            .toSet();
    if (!registered.contains(sport)) {
      showMessage(context, '${sports[sport]} 종목으로 가입한 회원만 예약할 수 있습니다.');
      return;
    }
    ref.read(sportProvider.notifier).select(sport);
    Navigator.push(
      context,
      MaterialPageRoute<void>(
        builder: (_) => widget.matchOnly
            ? ReservationPage(ground: row)
            : GroundDetailPage(code: '${row['g_code']}'),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final sport = ref.watch(groundSportProvider);
    final region = ref.watch(groundRegionProvider);
    return Center(
      child: ConstrainedBox(
        constraints: const BoxConstraints(maxWidth: 900),
        child: ListView(
          controller: scroll,
          padding: const EdgeInsets.only(top: 8, bottom: 24),
          children: [
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: MemberStyle.sidePadding,
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  GridView(
                    key: const ValueKey('sportGrid'),
                    gridDelegate:
                        const SliverGridDelegateWithFixedCrossAxisCount(
                          crossAxisCount: 4,
                          crossAxisSpacing: 6,
                          mainAxisExtent: 72,
                        ),
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    children: [
                      for (final code in [1, 4, 2, 3])
                        Semantics(
                          selected: sport == code,
                          button: true,
                          child: Material(
                            color: sport == code
                                ? MemberStyle.greenSurface
                                : Colors.white,
                            shape: RoundedRectangleBorder(
                              borderRadius: BorderRadius.circular(14),
                              side: BorderSide(
                                color: sport == code
                                    ? MemberStyle.green
                                    : MemberStyle.line,
                                width: sport == code ? 1.3 : 1,
                              ),
                            ),
                            clipBehavior: Clip.antiAlias,
                            child: InkWell(
                              key: ValueKey('groundSport$code'),
                              onTap: () => ref
                                  .read(groundSportProvider.notifier)
                                  .select(code),
                              child: Column(
                                mainAxisAlignment: MainAxisAlignment.center,
                                children: [
                                  Text(
                                    {1: '⚽', 4: '🏐', 2: '🏀', 3: '⚾'}[code]!,
                                    style: const TextStyle(
                                      fontSize: 25,
                                      height: 1.2,
                                    ),
                                  ),
                                  const SizedBox(height: 4),
                                  Text(
                                    sports[code]!,
                                    style: TextStyle(
                                      fontSize: 15,
                                      fontWeight: FontWeight.w800,
                                      color: sport == code
                                          ? MemberStyle.green
                                          : MemberStyle.ink,
                                    ),
                                  ),
                                ],
                              ),
                            ),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 16),
                  Material(
                    color: MemberStyle.navy,
                    borderRadius: BorderRadius.circular(19),
                    clipBehavior: Clip.antiAlias,
                    child: InkWell(
                      onTap: browse,
                      child: Stack(
                        children: [
                          Positioned.fill(
                            child: DecoratedBox(
                              decoration: const BoxDecoration(
                                gradient: LinearGradient(
                                  colors: [MemberStyle.navy, MemberStyle.blue],
                                ),
                              ),
                            ),
                          ),
                          Positioned(
                            right: -55,
                            top: -36,
                            bottom: -36,
                            child: Container(
                              width: 190,
                              decoration: BoxDecoration(
                                shape: BoxShape.circle,
                                border: Border.all(
                                  color: const Color(0xFF5C93EE)
                                      .withValues(alpha: 0.32),
                                  width: 20,
                                ),
                              ),
                            ),
                          ),
                          Padding(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 18,
                              vertical: 20,
                            ),
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  '${ref.watch(sessionProvider)?['c_name'] ?? '회원'}님의 ${sports[sport]} 구장 찾기',
                                  style: const TextStyle(
                                    color: Color(0xFFCDDCFF),
                                    fontSize: 13,
                                    fontWeight: FontWeight.w500,
                                  ),
                                ),
                                const SizedBox(height: 10),
                                const Text(
                                  '오늘은 어디서 뛸까요?',
                                  style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 23,
                                    fontWeight: FontWeight.w800,
                                    letterSpacing: -0.6,
                                  ),
                                ),
                                const SizedBox(height: 9),
                                const Text(
                                  '구장 살펴보기 →',
                                  style: TextStyle(
                                    color: Color(0xFFD4E4FF),
                                    fontSize: 14,
                                    fontWeight: FontWeight.w600,
                                  ),
                                ),
                              ],
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                  const SizedBox(height: 18),
                  if (!widget.matchOnly)
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        _shortcut('🏟️', '구장 예약', browse),
                        _shortcut(
                          '🎯',
                          '실력 매칭',
                          () => Navigator.push(
                            context,
                            MaterialPageRoute<void>(
                              builder: (_) => Scaffold(
                                appBar: AppBar(title: const Text('실력 매칭')),
                                body: const GroundsPage(matchOnly: true),
                              ),
                            ),
                          ),
                        ),
                        _shortcut(
                          '🤝',
                          '팀 매치',
                          () => openBoard(matching: true),
                        ),
                        _shortcut('📋', '게시판', () => openBoard()),
                      ],
                    ),
                  const SizedBox(height: 22),
                  Row(
                    key: filterKey,
                    children: [
                      Expanded(
                        flex: 5,
                        child: _filterBox(
                          DropdownButton<String>(
                            key: const ValueKey('groundRegion'),
                            value: region,
                            isExpanded: true,
                            isDense: true,
                            underline: const SizedBox(),
                            icon: const Icon(Icons.arrow_drop_down, size: 17),
                            style: const TextStyle(
                              color: MemberStyle.ink,
                              fontWeight: FontWeight.w800,
                              fontFamily: 'IBM Plex Sans KR',
                              fontSize: 13,
                            ),
                            items: ['전체 지역', ..._regions.keys]
                                .map(
                                  (v) => DropdownMenuItem(
                                    value: v,
                                    child: Text(
                                      v,
                                      overflow: TextOverflow.ellipsis,
                                    ),
                                  ),
                                )
                                .toList(),
                            onChanged: (v) {
                              if (v != null) {
                                ref
                                    .read(groundRegionProvider.notifier)
                                    .select(v);
                              }
                            },
                          ),
                          strong: true,
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        flex: 4,
                        child: _filterBox(
                          DropdownButton<String>(
                            key: const ValueKey('groundSearchField'),
                            value: searchField,
                            isExpanded: true,
                            isDense: true,
                            underline: const SizedBox(),
                            icon: const Icon(Icons.arrow_drop_down, size: 17),
                            style: const TextStyle(
                              color: MemberStyle.ink,
                              fontSize: 13,
                              fontFamily: 'IBM Plex Sans KR',
                            ),
                            items: const [
                              DropdownMenuItem(
                                value: 'g_name',
                                child: Text('이름'),
                              ),
                              DropdownMenuItem(
                                value: 'g_address',
                                child: Text('장소(주소)'),
                              ),
                            ],
                            onChanged: (v) {
                              if (v != null) setState(() => searchField = v);
                            },
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      IconButton.outlined(
                        onPressed: refresh,
                        tooltip: '구장 새로고침',
                        style: IconButton.styleFrom(
                          side: const BorderSide(color: MemberStyle.line),
                        ),
                        icon: const Icon(Icons.refresh, size: 21),
                      ),
                      IconButton.outlined(
                        tooltip: '구장 검색',
                        style: IconButton.styleFrom(
                          side: const BorderSide(color: MemberStyle.line),
                        ),
                        icon: const Icon(Icons.search, size: 22),
                        onPressed: () {
                          setState(() => searchVisible = !searchVisible);
                          if (searchVisible) {
                            WidgetsBinding.instance.addPostFrameCallback((_) {
                              if (mounted) searchFocus.requestFocus();
                            });
                          } else {
                            searchFocus.unfocus();
                          }
                        },
                      ),
                    ],
                  ),
                  if (searchVisible || keyword.isNotEmpty) ...[
                    const SizedBox(height: 12),
                    TextField(
                      controller: search,
                      focusNode: searchFocus,
                      onChanged: (v) =>
                          setState(() => keyword = v.trim().toLowerCase()),
                      onSubmitted: (v) =>
                          setState(() => keyword = v.trim().toLowerCase()),
                      decoration: InputDecoration(
                        hintText: searchField == 'g_name' ? '구장명 검색' : '주소 검색',
                        prefixIcon: const Icon(Icons.search),
                        suffixIcon: IconButton(
                          tooltip: '검색어 지우기',
                          onPressed: () {
                            search.clear();
                            setState(() => keyword = '');
                          },
                          icon: const Icon(Icons.close, size: 18),
                        ),
                        filled: true,
                        fillColor: MemberStyle.surface,
                        isDense: true,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                          borderSide: BorderSide.none,
                        ),
                      ),
                    ),
                  ],
                  const SizedBox(height: 12),
                ],
              ),
            ),
            ApiContent(
              query: query,
              builder: (data) {
                final rows = apiRows(data)
                    .where((row) => matches(row, sport, region))
                    .toList();
                return Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Container(
                      padding: const EdgeInsets.symmetric(
                        horizontal: 16,
                        vertical: 12,
                      ),
                      color: MemberStyle.surface,
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              '$region · ${sports[sport]} 구장',
                              style: const TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w800,
                                color: MemberStyle.ink,
                              ),
                            ),
                          ),
                          Text(
                            '${rows.length}개',
                            style: const TextStyle(
                              color: MemberStyle.muted,
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ],
                      ),
                    ),
                    if (rows.isEmpty)
                      const Padding(
                        padding: EdgeInsets.all(32),
                        child: Text(
                          '조건에 맞는 구장이 없습니다.',
                          textAlign: TextAlign.center,
                        ),
                      ),
                    for (final row in rows) _groundRow(row, sport),
                  ],
                );
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _shortcut(String emoji, String label, VoidCallback action) => Expanded(
    child: Material(
      color: Colors.white,
      borderRadius: BorderRadius.circular(16),
      clipBehavior: Clip.antiAlias,
      child: InkWell(
        onTap: action,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Column(
            children: [
              Container(
                width: 49,
                height: 49,
                decoration: BoxDecoration(
                  color: MemberStyle.surface,
                  borderRadius: BorderRadius.circular(17),
                ),
                child: Center(
                  child: Text(emoji, style: const TextStyle(fontSize: 25)),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                style: const TextStyle(fontSize: 12, color: MemberStyle.ink),
              ),
            ],
          ),
        ),
      ),
    ),
  );
  Widget _filterBox(Widget child, {bool strong = false}) => Container(
    height: 38,
    padding: const EdgeInsets.symmetric(horizontal: 11),
    decoration: BoxDecoration(
      border: Border.all(
        color: strong ? const Color(0xFF172541) : MemberStyle.line,
        width: strong ? 1.2 : 1,
      ),
      borderRadius: BorderRadius.circular(24),
    ),
    child: Center(child: child),
  );
  Widget _groundRow(Map<String, dynamic> row, int sport) => LayoutBuilder(
    builder: (context, constraints) {
      final time = '${row['g_time'] ?? ''}'.trim();
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 19),
        decoration: const BoxDecoration(
          border: Border(bottom: BorderSide(color: MemberStyle.line)),
        ),
        child: Row(
          children: [
            if (constraints.maxWidth >= 370) ...[
              SizedBox(
                width: 53,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    if (time.isNotEmpty) ...[
                      const Text(
                        '운영시간',
                        style: TextStyle(fontSize: 9, color: MemberStyle.muted),
                      ),
                      Text(
                        time.split(RegExp(r'[~～–]')).first.trim(),
                        style: const TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: MemberStyle.ink,
                        ),
                      ),
                    ] else
                      const Icon(
                        Icons.stadium_outlined,
                        color: MemberStyle.muted,
                        size: 27,
                      ),
                  ],
                ),
              ),
              const SizedBox(width: 9),
            ],
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    '${row['g_name'] ?? ''}',
                    style: const TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: MemberStyle.ink,
                      letterSpacing: -0.35,
                    ),
                  ),
                  const SizedBox(height: 5),
                  Text(
                    '${row['g_address'] ?? ''}',
                    style: const TextStyle(
                      fontSize: 11,
                      color: MemberStyle.muted,
                    ),
                  ),
                  const SizedBox(height: 7),
                  Wrap(
                    spacing: 4,
                    runSpacing: 4,
                    children: [
                      _tag(sports[sport]!, blue: true),
                      if (row['g_num'] != null) _tag('${row['g_num']}명'),
                      if (time.isNotEmpty) _tag(time),
                    ],
                  ),
                  const SizedBox(height: 6),
                  if (row['g_price'] != null)
                    Text(
                      '이용료 ${row['g_price']}원',
                      style: const TextStyle(
                        fontSize: 11,
                        color: MemberStyle.muted,
                      ),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 10),
            SizedBox(
              width: 80,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: MemberStyle.blue,
                  foregroundColor: Colors.white,
                  padding: const EdgeInsets.symmetric(
                    horizontal: 8,
                    vertical: 12,
                  ),
                  minimumSize: const Size(0, 44),
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(10),
                  ),
                ),
                onPressed: () => reserve(row, sport),
                child: const Text(
                  '시간 선택 · 예약',
                  textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 12, fontWeight: FontWeight.w800),
                ),
              ),
            ),
          ],
        ),
      );
    },
  );
  Widget _tag(String text, {bool blue = false}) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
    decoration: BoxDecoration(
      color: blue ? const Color(0xFFE8EEFF) : MemberStyle.surface,
      borderRadius: BorderRadius.circular(5),
    ),
    child: Text(
      text,
      style: TextStyle(
        fontSize: 11,
        fontWeight: FontWeight.w700,
        color: blue ? MemberStyle.blue : MemberStyle.muted,
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
