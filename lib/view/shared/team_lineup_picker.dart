// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/team_match_lineup_state.dart';

// 취소는 null, 확인은 선택 회원 ID 목록을 반환합니다.
Future<List<String>?> selectTeamLineup(
  BuildContext context, {
  required LineupQuery query,
  List<String> initial = const [],
}) => showDialog<List<String>>(
  context: context,
  builder: (_) => _LineupDialog(query: query, initial: initial),
);

class _LineupDialog extends ConsumerStatefulWidget {
  const _LineupDialog({required this.query, required this.initial});
  final LineupQuery query;
  final List<String> initial;

  @override
  ConsumerState<_LineupDialog> createState() => _LineupDialogState();
}

class _LineupDialogState extends ConsumerState<_LineupDialog> {
  late final Set<String> selected = widget.initial.toSet();

  @override
  Widget build(BuildContext context) {
    final data = ref.watch(teamMatchLineupProvider(widget.query));
    return AlertDialog(
      title: const Text('출전 팀원 선택'),
      content: SizedBox(
        width: 400,
        child: data.when(
          loading: () => const SizedBox(
            height: 80,
            child: Center(child: CircularProgressIndicator()),
          ),
          error: (error, _) => Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text('$error'),
              TextButton(
                onPressed: () =>
                    ref.invalidate(teamMatchLineupProvider(widget.query)),
                child: const Text('다시 시도'),
              ),
            ],
          ),
          data: (data) {
            final requiredCount = data['required_count'];
            final rows = data['results'];
            if (requiredCount is! int ||
                requiredCount <= 0 ||
                rows is! List ||
                rows.any((row) => row is! Map)) {
              return const Text('팀원 목록을 확인할 수 없습니다. 다시 시도해 주세요.');
            }
            final members = rows.cast<Map>();
            final validIds = members
                .map((m) => m['c_id_seq'])
                .whereType<String>()
                .toSet();
            final count = selected.intersection(validIds).length;
            return Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '구장 정원의 절반인 $requiredCount명을 선택해 주세요. ($count/$requiredCount)',
                ),
                if (members.length < requiredCount)
                  const Text('선택할 수 있는 팀원이 부족합니다.'),
                Flexible(
                  child: ListView(
                    shrinkWrap: true,
                    children: [
                      for (final member in members)
                        if (member['c_id_seq'] is String)
                          CheckboxListTile(
                            title: Text('${member['c_name'] ?? '팀원'}'),
                            subtitle: Text('${member['c_position'] ?? ''}'),
                            value: selected.contains(member['c_id_seq']),
                            onChanged:
                                !selected.contains(member['c_id_seq']) &&
                                    count >= requiredCount
                                ? null
                                : (value) => setState(() {
                                    if (value == true) {
                                      selected.add(
                                        member['c_id_seq'] as String,
                                      );
                                    } else {
                                      selected.remove(member['c_id_seq']);
                                    }
                                  }),
                          ),
                    ],
                  ),
                ),
                FilledButton(
                  onPressed: count == requiredCount
                      ? () => Navigator.pop(
                          context,
                          selected.intersection(validIds).toList()..sort(),
                        )
                      : null,
                  child: const Text('선택 완료'),
                ),
              ],
            );
          },
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('취소'),
        ),
      ],
    );
  }
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
