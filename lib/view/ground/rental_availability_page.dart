// 작업자 : 최현준
// 최초 작업 일 : 2026-10-30
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_features.dart';
import '../../vm/member_state.dart';
import '../reservation/reservation_page.dart';
import '../shared/member_components.dart';
import '../shared/ui.dart';

// 날짜와 회원 종목을 조회 키로 분리해 이전 검색의 결과가 섞이지 않게 합니다.
final _rentalOptionsProvider = FutureProvider.autoDispose
    .family<
      List<({Map<String, dynamic> ground, Map<String, dynamic> slot})>,
      ({String date, int sport})
    >((ref, key) async {
      final grounds = apiRows(
        await ref.watch(apiDocumentProvider(apiQuery('/ground')).future),
      );
      final matching = grounds.where((ground) {
        final info = '${ground['g_information'] ?? ''}';
        final text =
            RegExp(r'(?:^|/)\s*종목\s*:\s*([^/]+)').firstMatch(info)?.group(1) ??
            '';
        return text.split(RegExp(r'[,·、\s]+')).contains(sports[key.sport]);
      });
      final options = await Future.wait(
        matching.map((ground) async {
          final response = await ref.watch(
            apiDocumentProvider(
              apiQuery('/ground/reservation/slots/${ground['g_code']}', {
                'r_date': key.date,
              }),
            ).future,
          );
          return [
            for (final raw in response['slots'] as List? ?? [])
              if (raw is Map && raw['is_available'] == true)
                (ground: ground, slot: Map<String, dynamic>.from(raw)),
          ];
        }),
      );
      return options.expand((rows) => rows).toList();
    }, retry: (_, _) => null);

class RentalAvailabilityPage extends ConsumerStatefulWidget {
  const RentalAvailabilityPage({super.key});
  @override
  ConsumerState<RentalAvailabilityPage> createState() =>
      _RentalAvailabilityPageState();
}

class _RentalAvailabilityPageState
    extends ConsumerState<RentalAvailabilityPage> {
  DateTime date = DateUtils.dateOnly(DateTime.now());
  int? sport;

  @override
  Widget build(BuildContext context) {
    final availableSports =
        ref
            .watch(memberIdsProvider)
            .map(sportOfMember)
            .whereType<int>()
            .toSet()
            .toList()
          ..sort();
    final selected = availableSports.contains(sport)
        ? sport!
        : availableSports.firstOrNull;
    final key = (date: day(date), sport: selected ?? 0);
    return Scaffold(
      appBar: AppBar(title: const Text('구장 대관')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          const Text('대관 가능한 구장과 시간을 선택해 주세요.'),
          const SizedBox(height: 12),
          Wrap(
            spacing: 8,
            children: [
              for (final code in availableSports)
                ChoiceChip(
                  label: Text(sports[code]!),
                  selected: selected == code,
                  onSelected: (_) => setState(() => sport = code),
                ),
            ],
          ),
          ListTile(
            contentPadding: EdgeInsets.zero,
            title: Text(day(date)),
            trailing: const Icon(Icons.calendar_month),
            onTap: () async {
              final chosen = await showDatePicker(
                context: context,
                initialDate: date,
                firstDate: DateUtils.dateOnly(DateTime.now()),
                lastDate: DateTime.now().add(const Duration(days: 365)),
              );
              if (chosen != null && mounted) setState(() => date = chosen);
            },
          ),
          if (selected == null)
            const Text('가입한 종목을 확인해 주세요.')
          else
            ref
                .watch(_rentalOptionsProvider(key))
                .when(
                  loading: () =>
                      const Center(child: CircularProgressIndicator()),
                  error: (_, _) => Column(
                    children: [
                      const Text('대관 가능 시간을 불러오지 못했습니다.'),
                      TextButton(
                        onPressed: () {
                          ref.invalidate(apiDocumentProvider);
                          ref.invalidate(_rentalOptionsProvider(key));
                        },
                        child: const Text('다시 시도'),
                      ),
                    ],
                  ),
                  data: (options) {
                    final visible = options.where((option) {
                      final parts = '${option.slot['rs_time']}'.split(':');
                      final hour = int.tryParse(parts.first);
                      final minute = parts.length > 1
                          ? int.tryParse(parts[1])
                          : null;
                      return hour != null &&
                          minute != null &&
                          DateTime(
                            date.year,
                            date.month,
                            date.day,
                            hour,
                            minute,
                          ).isAfter(DateTime.now());
                    }).toList();
                    if (visible.isEmpty) {
                      return const Padding(
                        padding: EdgeInsets.all(20),
                        child: Text('선택한 날짜에 대관 가능한 시간이 없습니다.'),
                      );
                    }
                    return Column(
                      children: [
                        for (final option in visible)
                          MemberPanel(
                            color: Colors.white,
                            child: ListTile(
                              contentPadding: EdgeInsets.zero,
                              title: Text('${option.ground['g_name']}'),
                              subtitle: Text(
                                '${option.ground['g_address']}\n${option.slot['rs_time']} ~ ${option.slot['re_time']}',
                              ),
                              trailing: const Icon(Icons.chevron_right),
                              onTap: () async {
                                ref
                                    .read(sportProvider.notifier)
                                    .select(selected);
                                await Navigator.push(
                                  context,
                                  MaterialPageRoute<void>(
                                    builder: (_) => ReservationPage(
                                      ground: option.ground,
                                      rental: true,
                                      initialDate: date,
                                    ),
                                  ),
                                );
                                ref.invalidate(_rentalOptionsProvider(key));
                                ref.invalidate(apiDocumentProvider);
                              },
                            ),
                          ),
                      ],
                    );
                  },
                ),
        ],
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
