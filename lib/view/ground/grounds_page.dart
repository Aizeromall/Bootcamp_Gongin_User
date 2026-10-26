// 최초 작업자 : 최현준 / 최초 작업일 : 2026-10-24
// 디버그: 실제 구장 설명의 종목과 주소로 필터링하며 조회 종목과 가입 종목을 분리합니다.
// 작업자 : 양태건 / 최종 수정일 : 2026-10-26
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../shared/ui.dart';
import '../reservation/reservation_page.dart';

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
  const GroundsPage({super.key});
  @override
  ConsumerState<GroundsPage> createState() => _GroundsPageState();
}

class _GroundsPageState extends ConsumerState<GroundsPage> {
  final search = TextEditingController();
  String searchField = 'g_name';
  String keyword = '';
  late Future<Map<String, dynamic>> results;

  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    results = ref.read(memberApiProvider).request('/match/ground');
  }

  void refresh() => setState(load);

  @override
  void dispose() {
    search.dispose();
    super.dispose();
  }

  bool matches(Map<String, dynamic> row, int sport, String region) {
    // 종목을 추측하거나 예약 이력으로 분류하지 않고 실제 설명의 명시된 종목만 사용합니다.
    final sportText =
        RegExp(r'(?:^|/)\s*종목\s*:\s*([^/]+)')
            .firstMatch('${row['g_information'] ?? ''}')
            ?.group(1) ??
        '';
    final supported = sportText.split(RegExp(r'[,·、\s]+'));
    final address = '${row['g_address'] ?? ''}'.trim();
    final first = address.split(RegExp(r'\s+')).first;
    return supported.contains(sports[sport]) &&
        (region == '전체 지역' || _regions[region]!.contains(first)) &&
        '${row[searchField] ?? ''}'.toLowerCase().contains(keyword);
  }

  void reserve(Map<String, dynamic> row, int sport) {
    final registered =
        (ref.read(sessionProvider)?['preferred_stocks'] as List? ?? [])
            .map((value) => int.tryParse('$value'))
            .toSet();
    if (!registered.contains(sport)) {
      showMessage(context, '${sports[sport]} 종목으로 가입한 회원만 예약할 수 있습니다.');
      return;
    }
    ref.read(sportProvider.notifier).select(sport);
    Navigator.push(
      context,
      MaterialPageRoute<void>(builder: (_) => ReservationPage(ground: row)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final sport = ref.watch(groundSportProvider);
    final region = ref.watch(groundRegionProvider);
    const blue = Color(0xFF1976F9);
    const ink = Color(0xFF141A24);
    return pageContent([
      GridView(
        key: const ValueKey('sportGrid'),
        gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
          crossAxisCount: 4,
          crossAxisSpacing: 8,
          mainAxisExtent: 100,
        ),
        shrinkWrap: true,
        physics: const NeverScrollableScrollPhysics(),
        children: [
          for (final code in [1, 4, 2, 3])
            Semantics(
              selected: sport == code,
              button: true,
              child: Material(
                color: sport == code ? const Color(0xFFE6F5EC) : Colors.white,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(18),
                  side: BorderSide(
                    color: sport == code
                        ? const Color(0xFF08A54C)
                        : const Color(0xFFE7EAF0),
                    width: sport == code ? 1.5 : 1,
                  ),
                ),
                clipBehavior: Clip.antiAlias,
                child: InkWell(
                  key: ValueKey('groundSport$code'),
                  onTap: () =>
                      ref.read(groundSportProvider.notifier).select(code),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Icon(
                        {
                          1: Icons.sports_soccer,
                          4: Icons.sports_volleyball,
                          2: Icons.sports_basketball,
                          3: Icons.sports_baseball,
                        }[code],
                        size: 32,
                        color: sport == code ? const Color(0xFF08A54C) : ink,
                      ),
                      const SizedBox(height: 6),
                      Text(
                        sports[code]!,
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.w800,
                          color: sport == code ? const Color(0xFF08A54C) : ink,
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
        ],
      ),
      const SizedBox(height: 22),
      Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          gradient: const LinearGradient(colors: [Color(0xFF142D92), blue]),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              '${ref.watch(sessionProvider)?['c_name'] ?? '회원'}님, ${sports[sport]}와 함께하는 오늘',
              style: const TextStyle(color: Color(0xFFD4E4FF)),
            ),
            const SizedBox(height: 12),
            const Text(
              '오늘은 어디서 뛸까요?',
              style: TextStyle(
                color: Colors.white,
                fontSize: 24,
                fontWeight: FontWeight.w800,
              ),
            ),
            const SizedBox(height: 10),
            const Text(
              '원하는 지역의 구장을 찾아 예약해 보세요.',
              style: TextStyle(color: Color(0xFFD4E4FF)),
            ),
          ],
        ),
      ),
      const SizedBox(height: 24),
      Row(
        children: [
          Expanded(
            child: _filterBox(
              DropdownButton<String>(
                key: const ValueKey('groundRegion'),
                value: region,
                isExpanded: true,
                underline: const SizedBox(),
                items: ['전체 지역', ..._regions.keys]
                    .map(
                      (value) =>
                          DropdownMenuItem(value: value, child: Text(value)),
                    )
                    .toList(),
                onChanged: (value) {
                  if (value != null) {
                    ref.read(groundRegionProvider.notifier).select(value);
                  }
                },
              ),
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: _filterBox(
              DropdownButton<String>(
                key: const ValueKey('groundSearchField'),
                value: searchField,
                isExpanded: true,
                underline: const SizedBox(),
                items: const [
                  DropdownMenuItem(value: 'g_name', child: Text('이름')),
                  DropdownMenuItem(value: 'g_address', child: Text('장소(주소)')),
                ],
                onChanged: (value) {
                  if (value != null) setState(() => searchField = value);
                },
              ),
            ),
          ),
          IconButton(
            onPressed: refresh,
            tooltip: '구장 새로고침',
            icon: const Icon(Icons.refresh),
          ),
        ],
      ),
      const SizedBox(height: 12),
      TextField(
        controller: search,
        onChanged: (value) =>
            setState(() => keyword = value.trim().toLowerCase()),
        onSubmitted: (value) =>
            setState(() => keyword = value.trim().toLowerCase()),
        decoration: InputDecoration(
          hintText: searchField == 'g_name' ? '구장명 검색' : '주소 검색',
          prefixIcon: const Icon(Icons.search),
          filled: true,
          fillColor: const Color(0xFFF5F6F9),
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(16),
            borderSide: BorderSide.none,
          ),
        ),
      ),
      const SizedBox(height: 18),
      Text(
        '$region · ${sports[sport]} 구장',
        style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w800),
      ),
      ResultList(
        future: results.then(
          (data) => {
            ...data,
            'results': (data['results'] as List)
                .where(
                  (row) => matches(
                    Map<String, dynamic>.from(row as Map),
                    sport,
                    region,
                  ),
                )
                .toList(),
          },
        ),
        retry: refresh,
        item: (row) => Container(
          padding: const EdgeInsets.symmetric(vertical: 20),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: Color(0xFFE7EAF0))),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${row['g_name']}',
                style: const TextStyle(
                  fontSize: 20,
                  color: ink,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '${row['g_address']}',
                style: const TextStyle(color: Color(0xFF6D7585)),
              ),
              const SizedBox(height: 12),
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  _tag(sports[sport]!),
                  _tag('${row['g_num']}명'),
                  if (row['g_time'] != null) _tag('${row['g_time']}'),
                ],
              ),
              const SizedBox(height: 14),
              Row(
                children: [
                  Expanded(child: Text('구장 이용료 ${row['g_price']}원')),
                  FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: blue,
                      foregroundColor: Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: () => reserve(row, sport),
                    child: const Text('시간 선택 · 예약'),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    ]);
  }

  Widget _filterBox(Widget child) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 14),
    decoration: BoxDecoration(
      border: Border.all(color: const Color(0xFFE0E4ED)),
      borderRadius: BorderRadius.circular(28),
    ),
    child: child,
  );

  Widget _tag(String label) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: const Color(0xFFF0F4FF),
      borderRadius: BorderRadius.circular(7),
    ),
    child: Text(
      label,
      style: const TextStyle(
        color: Color(0xFF2265CD),
        fontWeight: FontWeight.w600,
      ),
    ),
  );
}
