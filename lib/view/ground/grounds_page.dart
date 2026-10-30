// 최초 작업자 : 최현준 / 최초 작업일 : 2026-10-24
// 수정 일 : 2026-10-27 / 작업자 : 양태건
// 첨부 홈 목업의 종목 카드·배너·바로가기·필터·목록을 실제 구장 데이터에 적용합니다.
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../shared/api_content.dart';
import '../shared/member_style.dart';
import '../shared/ground_price.dart';
import '../shared/ui.dart';
import 'ground_detail_page.dart';
import 'rental_availability_page.dart';
import '../reservation/reservation_page.dart';
import '../board/board_page.dart';
import '../home/home_banner.dart';

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
  // 수정 일 : 2026-10-30 / 작업자 : 최현준
  // 홈의 날짜는 목록에서 안내하는 다음 경기 시간의 기준입니다.
  DateTime selectedDate = DateUtils.dateOnly(DateTime.now());
  String? get nextSlot {
    final now = DateTime.now();
    for (var hour = 8; hour <= 22; hour += 2) {
      if (DateTime(
        selectedDate.year,
        selectedDate.month,
        selectedDate.day,
        hour,
      ).isAfter(now)) {
        return '${hour.toString().padLeft(2, '0')}:00 ~ ${(hour + 2).toString().padLeft(2, '0')}:00';
      }
    }
    return null;
  }

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
                                : Theme.of(context)
                                      .colorScheme
                                      .surfaceContainerHigh,
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
                                          : Theme.of(context)
                                                .colorScheme
                                                .onSurface,
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
                  // 수정 일 : 2026-10-30 / 작업자 : 최현준 — 활성 배너만 홈 카드 위치에 표시합니다.
                  if (!widget.matchOnly) const HomeBanner(),
                  const SizedBox(height: 18),
                  if (!widget.matchOnly)
                    Row(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        // 수정 일 : 2026-10-30 / 작업자 : 최현준
                        _shortcut(
                          '🏟️',
                          '구장 예약',
                          () => Navigator.push(
                            context,
                            MaterialPageRoute<void>(
                              builder: (_) => const RentalAvailabilityPage(),
                            ),
                          ),
                        ),
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
                  ListTile(
                    contentPadding: EdgeInsets.zero,
                    title: Text('조회 날짜 · ${day(selectedDate)}'),
                    subtitle: Text(
                      nextSlot == null
                          ? '오늘 남은 경기 시간이 없습니다.'
                          : '다음 시간 · $nextSlot',
                    ),
                    trailing: const Icon(Icons.calendar_month),
                    onTap: () async {
                      final chosen = await showDatePicker(
                        context: context,
                        initialDate: selectedDate,
                        firstDate: DateUtils.dateOnly(DateTime.now()),
                        lastDate: DateTime.now().add(const Duration(days: 365)),
                      );
                      if (chosen != null && mounted) {
                        setState(() => selectedDate = chosen);
                      }
                    },
                  ),
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
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onSurface,
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
                            style: TextStyle(
                              color: Theme.of(context).colorScheme.onSurface,
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
                        fillColor: Theme.of(context)
                            .colorScheme
                            .surfaceContainerHighest,
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
                      color: Theme.of(context).colorScheme.surfaceContainerHigh,
                      child: Row(
                        children: [
                          Expanded(
                            child: Text(
                              '$region · ${sports[sport]} 구장',
                              style: TextStyle(
                                fontSize: 15,
                                fontWeight: FontWeight.w800,
                                color: Theme.of(context).colorScheme.onSurface,
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
      color: Theme.of(context).colorScheme.surface,
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
                  color: Theme.of(context).colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(17),
                ),
                child: Center(
                  child: Text(emoji, style: const TextStyle(fontSize: 25)),
                ),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                style: TextStyle(
                  fontSize: 12,
                  color: Theme.of(context).colorScheme.onSurface,
                ),
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
      final individualPrice = individualGroundPrice(
        row['g_price'],
        row['g_num'],
      );
      // 플랩의 목록처럼 정보 단위를 카드로 구분하되 실제 구장 데이터만 표시합니다.
      return Container(
        margin: const EdgeInsets.fromLTRB(16, 5, 16, 7),
        padding: const EdgeInsets.all(15),
        decoration: BoxDecoration(
          color: Theme.of(context).colorScheme.surface,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(
            color: Theme.of(context).colorScheme.outlineVariant,
          ),
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
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: Theme.of(context).colorScheme.onSurface,
                        ),
                      ),
                    ] else
                      const Icon(
                        Icons.stadium_outlined,
                        color: MemberStyle.blue,
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
                    style: TextStyle(
                      fontSize: 16,
                      fontWeight: FontWeight.w800,
                      color: Theme.of(context).colorScheme.onSurface,
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
                  // 수정 일 : 2026-10-30 / 작업자 : 최현준
                  // 선택 날짜의 다음 시간대에 신청한 회원의 평균 티어를 조회합니다.
                  _GroundAverageTier(
                    groundCode: '${row['g_code']}',
                    date: day(selectedDate),
                    sport: sport,
                    start: nextSlot?.substring(0, 5),
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
                  // 수정 일 : 2026-10-30 / 작업자 : 최현준
                  // 실력 매칭 1인 예상 금액과 전체 대여 금액을 혼동하지 않도록 구분합니다.
                  Text(
                    individualPrice == null
                        ? '1인 이용료 확인 불가'
                        : '1인 이용료 $individualPrice원',
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

class _GroundAverageTier extends ConsumerWidget {
  const _GroundAverageTier({
    required this.groundCode,
    required this.date,
    required this.sport,
    required this.start,
  });
  final String groundCode;
  final String date;
  final int sport;
  final String? start;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    if (start == null) return const Text('남은 경기 시간이 없습니다.');
    final query = apiQuery(
      '/match/reservation/ground/${Uri.encodeComponent(groundCode)}/ratings',
      {'r_date': date, 'sport': '$sport'},
    );
    return ref
        .watch(apiDocumentProvider(query))
        .when(
          loading: () => const Text('평균 티어 확인 중…'),
          error: (_, _) => InkWell(
            onTap: () => ref.invalidate(apiDocumentProvider(query)),
            child: const Text('평균 티어 조회 실패 · 다시 시도'),
          ),
          data: (data) {
            final slots = data['slots'];
            if (slots is! List) return const Text('평균 티어 정보 확인 불가');
            final slot = slots
                .whereType<Map>()
                .where((item) => item['rs_time'] == start)
                .firstOrNull;
            if (slot == null) return const Text('평균 티어 정보 확인 불가');
            final count = slot['applicant_count'];
            if (count == 0) return const Text('신청 인원 없음');
            final tier = slot['average_tier'];
            return Text(
              tier == null ? '평균 티어 정보 확인 불가' : '평균 티어 $tier · 신청 $count명',
            );
          },
        );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (홈·구장 테마 대비 적용)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (구장 목록 카드 스타일 정리)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
