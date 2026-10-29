// 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/account_state.dart';
import '../../vm/member_state.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';

class AccountProfilePage extends ConsumerWidget {
  const AccountProfilePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) => Scaffold(
    appBar: AppBar(title: const Text('회원정보 수정')),
    body: ref
        .watch(accountProfileProvider)
        .when(
          loading: () => const Center(child: CircularProgressIndicator()),
          error: (error, _) => Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text('$error', textAlign: TextAlign.center),
                  TextButton(
                    onPressed: () => ref.invalidate(accountProfileProvider),
                    child: const Text('다시 시도'),
                  ),
                ],
              ),
            ),
          ),
          data: (data) {
            final members = (data['members'] as List).cast<Map>();
            if (!members.any((row) => row['c_deletdate'] == null)) {
              return const Center(child: Text('활성 종목이 없습니다. 다시 로그인해 주세요.'));
            }
            return _ProfileForm(
              key: ValueKey(ref.watch(sessionProvider)?['c_id']),
              members: members,
            );
          },
        ),
  );
}

class _ProfileForm extends ConsumerStatefulWidget {
  const _ProfileForm({super.key, required this.members});
  final List<Map> members;
  @override
  ConsumerState<_ProfileForm> createState() => _ProfileFormState();
}

class _ProfileFormState extends ConsumerState<_ProfileForm> {
  final form = GlobalKey<FormState>();
  final fields = <String, TextEditingController>{};
  final positions = <String, String?>{};
  final selected = <int>{};
  late final String? owner;
  bool confirming = false;
  static const labels = {
    'c_name': '이름',
    'c_address': '주소',
    'c_phone': '전화번호',
    'c_gender': '성별',
    'c_birthday': '생년월일',
  };
  static const limits = {
    'c_name': 50,
    'c_address': 255,
    'c_phone': 20,
    'c_gender': 10,
  };
  // 수정 일 : 2026-10-29 / 작업자 : 최현준
  // 화면·컨트롤러·검증에서 같은 비밀번호 항목과 종목 조회를 재사용합니다.
  static const passwordLabels = {
    'current_password': '현재 비밀번호',
    'c_pw': '새 비밀번호',
    'confirmation': '새 비밀번호 확인',
  };
  Map? memberFor(int sport) => widget.members
      .where((row) => '${row['c_prefer_stock']}' == '$sport')
      .firstOrNull;
  Map get initial =>
      widget.members.firstWhere((row) => row['c_deletdate'] == null);
  Set<int> get originalSports => widget.members
      .where((r) => r['c_deletdate'] == null)
      .map((r) => int.parse('${r['c_prefer_stock']}'))
      .toSet();
  bool get local => initial['c_login_type'] == 'local';

  @override
  void initState() {
    super.initState();
    owner = ref.read(sessionProvider)?['c_id'] as String?;
    for (final key in [...labels.keys, if (local) ...passwordLabels.keys]) {
      fields[key] = TextEditingController(
        text: labels.containsKey(key) ? '${initial[key] ?? ''}' : '',
      );
    }
    for (final row in widget.members) {
      positions['${row['c_prefer_stock']}'] = row['c_position'] as String?;
    }
    selected.addAll(originalSports);
  }

  @override
  void dispose() {
    for (final field in fields.values) {
      field.dispose();
    }
    super.dispose();
  }

  Future<void> pickBirthday() async {
    final today = DateUtils.dateOnly(DateTime.now());
    final parsed = DateTime.tryParse(fields['c_birthday']!.text);
    final value = await showDatePicker(
      context: context,
      firstDate: DateTime(1900),
      lastDate: today,
      initialDate:
          parsed != null && !parsed.isAfter(today) && parsed.year >= 1900
          ? parsed
          : today,
    );
    if (value != null && mounted) {
      setState(() => fields['c_birthday']!.text = day(value));
    }
  }

  Future<void> save() async {
    if (ref.read(sessionProvider)?['c_id'] != owner) return;
    if (ref.read(accountActionsProvider) || !form.currentState!.validate()) {
      return;
    }
    final changes = <String, dynamic>{};
    for (final key in labels.keys) {
      if (fields[key]!.text.trim() != '${initial[key] ?? ''}') {
        changes[key] = fields[key]!.text.trim();
      }
    }
    final changedPositions = <String, String>{};
    final sportsChanged =
        selected.length != originalSports.length ||
        !selected.containsAll(originalSports);
    if (sportsChanged) {
      changes['preferred_stocks'] = selected.toList()..sort();
    }
    for (final sportNumber in selected) {
      final row = memberFor(sportNumber);
      final sport = '$sportNumber';
      if (sportsChanged || positions[sport] != row?['c_position']) {
        changedPositions[sport] = positions[sport]!;
      }
    }
    if (changedPositions.isNotEmpty || sportsChanged) {
      changes['c_position'] = changedPositions;
    }
    if (local && fields['c_pw']!.text.isNotEmpty) {
      changes['c_pw'] = fields['c_pw']!.text;
      changes['current_password'] = fields['current_password']!.text;
    }
    if (changes.isEmpty) {
      showMessage(context, '변경한 정보가 없습니다.');
      return;
    }
    if (originalSports.difference(selected).isNotEmpty) {
      final before = ref.read(sessionProvider);
      final yes = await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: const Text('선호 종목 삭제 신청'),
          content: Text(
            '선택을 해제한 종목에 삭제 신청일을 기록합니다. 30일 내에는 복구할 수 있습니다. '
            '예약·결제는 자동 취소되지 않습니다.${selected.isEmpty ? '\n모든 종목을 해제하면 로그아웃됩니다.' : ''}',
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('취소'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context, true),
              child: const Text('저장'),
            ),
          ],
        ),
      );
      if (!mounted ||
          yes != true ||
          !identical(before, ref.read(sessionProvider))) {
        return;
      }
    }
    try {
      await ref.read(accountActionsProvider.notifier).save(changes);
      if (!mounted) return;
      if (ref.read(sessionProvider) == null) {
        Navigator.of(context).popUntil((route) => route.isFirst);
        return;
      }
      showMessage(context, '회원정보를 수정했습니다.');
      Navigator.pop(context);
    } catch (error) {
      if (mounted) showMessage(context, error);
    }
  }

  Future<void> withdraw() async {
    if (confirming || ref.read(accountActionsProvider)) return;
    final before = ref.read(sessionProvider);
    if (before?['c_id'] != owner) return;
    confirming = true;
    var agreed = false;
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, update) => AlertDialog(
          title: const Text('계정 삭제 안내 및 동의'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text(
                  '계정 삭제를 신청하면 가입한 모든 종목에 삭제 신청일이 기록되고 로그아웃됩니다.\n\n'
                  '각 종목의 삭제 신청 후 30일이 지나기 전에는 같은 계정으로 로그인해 복구할 수 있습니다. '
                  '30일이 지난 종목은 복구할 수 없습니다.\n\n'
                  '기존 예약·결제는 자동 취소·환불되지 않습니다. '
                  '관련 이력이 남아 있으면 영구 삭제는 이력 정리 후 진행됩니다.',
                ),
                CheckboxListTile(
                  contentPadding: EdgeInsets.zero,
                  value: agreed,
                  onChanged: (value) => update(() => agreed = value ?? false),
                  title: const Text('안내 내용을 확인했고 삭제 신청에 동의합니다.'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context, false),
              child: const Text('취소'),
            ),
            TextButton(
              onPressed: agreed ? () => Navigator.pop(context, true) : null,
              child: const Text('삭제 신청'),
            ),
          ],
        ),
      ),
    );
    confirming = false;
    if (confirmed != true || !mounted) return;
    if (!identical(ref.read(sessionProvider), before)) return;
    try {
      await ref.read(accountActionsProvider.notifier).withdraw();
      if (!mounted) return;
      Navigator.of(context).popUntil((route) => route.isFirst);
    } catch (error) {
      if (mounted) showMessage(context, error);
    }
  }

  @override
  Widget build(BuildContext context) {
    final busy = ref.watch(accountActionsProvider);
    return PopScope(
      canPop: !busy,
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 600),
          child: Form(
            key: form,
            // 소수의 고정 입력 필드는 함께 유지해 스크롤 밖 필수값도 Form 검증에 포함합니다.
            child: SingleChildScrollView(
              keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const Text(
                    '내 정보',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w800),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    '로그인 방식: ${{'local': '일반', 'google': 'Google', 'kakao': '카카오', 'naver': '네이버'}[initial['c_login_type']] ?? '확인 필요'}',
                  ),
                  const Text(
                    '아이디·등급·가입일·팀 정보는 이 화면에서 변경할 수 없습니다.',
                    style: TextStyle(color: MemberStyle.muted),
                  ),
                  const SizedBox(height: 20),
                  for (final key in labels.keys)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: TextFormField(
                        key: ValueKey('profile-$key'),
                        controller: fields[key],
                        enabled: !busy,
                        readOnly: key == 'c_birthday',
                        onTap: key == 'c_birthday' ? pickBirthday : null,
                        maxLength: limits[key],
                        decoration: InputDecoration(labelText: labels[key]),
                        keyboardType: key == 'c_phone'
                            ? TextInputType.phone
                            : TextInputType.text,
                        validator: (value) => (value ?? '').trim().isEmpty
                            ? '${labels[key]}을(를) 입력해 주세요.'
                            : null,
                      ),
                    ),
                  const Text(
                    '선호 종목 · 포지션',
                    style: TextStyle(fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 12),
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final sport in sports.entries)
                        FilterChip(
                          key: ValueKey('profile-sport-${sport.key}'),
                          label: Text(sport.value),
                          selected: selected.contains(sport.key),
                          onSelected: busy
                              ? null
                              : (value) => setState(() {
                                  if (value) {
                                    selected.add(sport.key);
                                    positions['${sport.key}'] =
                                        memberFor(sport.key)?['c_position']
                                            as String?;
                                  } else {
                                    selected.remove(sport.key);
                                    positions.remove('${sport.key}');
                                  }
                                }),
                        ),
                    ],
                  ),
                  const Padding(
                    padding: EdgeInsets.symmetric(vertical: 12),
                    child: Text(
                      '선택 해제는 삭제 신청, 삭제 유예 중인 종목을 다시 선택하면 복구입니다. 저장할 때 반영됩니다.',
                    ),
                  ),
                  for (final row in widget.members.where(
                    (row) => row['c_deletdate'] != null,
                  ))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: Text(
                        '${sports[int.tryParse('${row['c_prefer_stock']}')] ?? '종목'} 삭제 신청일: ${row['c_deletdate'].toString().split('T').first}',
                        style: const TextStyle(color: MemberStyle.muted),
                      ),
                    ),
                  for (final entry in positions.entries.where(
                    (entry) => selected.contains(int.tryParse(entry.key)),
                  ))
                    Padding(
                      padding: const EdgeInsets.only(bottom: 16),
                      child: DropdownButtonFormField<String>(
                        key: ValueKey('profile-position-${entry.key}'),
                        initialValue:
                            (sportPositions[int.tryParse(entry.key)] ?? [])
                                .contains(entry.value)
                            ? entry.value
                            : null,
                        decoration: InputDecoration(
                          labelText:
                              '${sports[int.tryParse(entry.key)] ?? '가입 종목'} 포지션',
                        ),
                        items: [
                          for (final value
                              in sportPositions[int.tryParse(entry.key)] ??
                                  <String>[])
                            DropdownMenuItem(value: value, child: Text(value)),
                        ],
                        onChanged: busy
                            ? null
                            : (value) =>
                                  setState(() => positions[entry.key] = value),
                        validator: (value) =>
                            value == null ? '포지션을 선택해 주세요.' : null,
                      ),
                    ),
                  if (local) ...[
                    const Text(
                      '비밀번호 변경 (선택)',
                      style: TextStyle(fontWeight: FontWeight.w700),
                    ),
                    for (final entry in passwordLabels.entries)
                      Padding(
                        padding: const EdgeInsets.only(top: 12),
                        child: TextFormField(
                          key: ValueKey('profile-${entry.key}'),
                          controller: fields[entry.key],
                          enabled: !busy,
                          obscureText: true,
                          enableSuggestions: false,
                          autocorrect: false,
                          decoration: InputDecoration(labelText: entry.value),
                          validator: (value) {
                            if (passwordLabels.keys.every(
                              (key) => fields[key]!.text.isEmpty,
                            )) {
                              return null;
                            }
                            if ((value ?? '').length < 8 ||
                                value!.length > 128) {
                              return '8~128자로 입력해 주세요.';
                            }
                            if (entry.key == 'confirmation' &&
                                value != fields['c_pw']!.text) {
                              return '새 비밀번호가 일치하지 않습니다.';
                            }
                            return null;
                          },
                        ),
                      ),
                  ],
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: busy ? null : save,
                    child: Text(busy ? '처리 중…' : '저장'),
                  ),
                  const SizedBox(height: 36),
                  const Divider(),
                  TextButton(
                    onPressed: busy ? null : withdraw,
                    style: TextButton.styleFrom(
                      foregroundColor: Colors.red.shade700,
                    ),
                    child: const Text('계정 삭제'),
                  ),
                  const SizedBox(height: 20),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
