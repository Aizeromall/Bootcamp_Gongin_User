// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter/services.dart';

import '../../vm/member_state.dart';
import '../../vm/social_login_state.dart';
import '../shared/ui.dart';
import '../shared/member_style.dart';

class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key, this.signupTicket});
  final String? signupTicket;
  @override
  ConsumerState<RegisterPage> createState() => _RegisterPageState();
}

class _RegisterPageState extends ConsumerState<RegisterPage> {
  final form = GlobalKey<FormState>();
  final fields = {
    for (final k in ['c_id', 'c_pw', 'c_name', 'c_address', 'c_phone'])
      k: TextEditingController(),
  };
  // 디버그: 종목 해제 시 포지션도 제거하여 숨은 선택값 전송을 방지합니다.
  // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
  final selected = <int>{};
  final positions = <int, String>{};
  String gender = '남성';
  DateTime? birthday;
  bool busy = false;
  int step = 0;
  bool get social => widget.signupTicket != null;
  @override
  void initState() {
    super.initState();
    if (social) step = 1;
  }

  final confirmation = TextEditingController();
  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    confirmation.dispose();
    super.dispose();
  }

  Future<void> submit() async {
    if (busy) return;
    if (!form.currentState!.validate()) {
      return;
    }
    if (selected.isEmpty || birthday == null) {
      showMessage(context, '생년월일과 선호 종목을 선택해 주세요.');
      return;
    }
    // 수정 일 : 2026-10-28 / 작업자 : 양태건
    // 스크롤 밖의 필드도 입력 상태를 확인하여 누락된 포지션을 전송하지 않습니다.
    if (fields.entries
            .where((entry) => !social || !['c_id', 'c_pw'].contains(entry.key))
            .any((entry) => entry.value.text.trim().isEmpty) ||
        selected.any((sport) => positions[sport] == null)) {
      showMessage(context, '기본 정보와 선택한 종목의 포지션을 모두 입력해 주세요.');
      return;
    }
    setState(() => busy = true);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            social ? '/auth/social/register' : '/auth/register',
            body: {
              for (final entry in fields.entries)
                if (!social || !['c_id', 'c_pw'].contains(entry.key))
                  entry.key: entry.key == 'c_pw'
                      ? entry.value.text
                      : entry.value.text.trim(),
              if (social) 'signup_ticket': widget.signupTicket,
              if (!social) 'c_team': '무소속',
              // 디버그: JSON 객체 키는 문자열, 값은 해당 종목의 포지션입니다.
              // 작업자 : 양태건 / 최종 수정일 : 2026-10-26
              'c_position': {
                for (final sport in selected) '$sport': positions[sport]!,
              },
              'c_gender': gender,
              'c_birthday': day(birthday!),
              'preferred_stocks': selected.toList()..sort(),
            },
          );
      if (!mounted) {
        return;
      }
      if (social) acceptMemberSession(ref, result);
      showMessage(
        context,
        social ? '간편가입이 완료되었습니다.' : '가입이 완료되었습니다. 로그인해 주세요.',
      );
      Navigator.pop(context);
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

  // 수정 일 : 2026-10-28 / 작업자 : 양태건
  // 계정 정보와 기본 정보를 나누되 확인 비밀번호는 서버로 전송하지 않습니다.
  Widget input(String key, String label) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: TextFormField(
      key: ValueKey(key),
      controller: fields[key],
      enabled: !busy,
      // 수정 일 : 2026-10-30 / 작업자 : 최현준 — 일반·간편가입 전화번호는 숫자만 입력합니다.
      keyboardType: key == 'c_phone' ? TextInputType.number : null,
      inputFormatters: key == 'c_phone'
          ? [FilteringTextInputFormatter.digitsOnly]
          : null,
      obscureText: key == 'c_pw',
      maxLength: {
        'c_id': 40,
        'c_pw': 128,
        'c_name': 45,
        'c_address': 255,
        'c_phone': 20,
      }[key],
      decoration: InputDecoration(labelText: label),
      validator: (value) {
        if ((value ?? '').trim().isEmpty) return '필수 입력 항목입니다.';
        if (key == 'c_phone' && !RegExp(r'^[0-9]+$').hasMatch(value!)) {
          return '전화번호는 숫자만 입력해 주세요.';
        }
        if (key == 'c_pw' && value!.length < 8) return '8자 이상 입력해 주세요.';
        return null;
      },
    ),
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('회원가입'),
      leading: step == 0 || social
          ? null
          : BackButton(onPressed: busy ? null : () => setState(() => step = 0)),
    ),
    body: Form(
      key: form,
      child: pageContent([
        if (!social)
          Row(
            children: [
              Text(
                '1 계정 정보',
                style: TextStyle(
                  color: step == 0 ? MemberStyle.blue : MemberStyle.muted,
                  fontWeight: FontWeight.w800,
                ),
              ),
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 12),
                child: Icon(
                  Icons.chevron_right,
                  size: 16,
                  color: MemberStyle.muted,
                ),
              ),
              Text(
                '2 기본 정보',
                style: TextStyle(
                  color: step == 1 ? MemberStyle.blue : MemberStyle.muted,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ],
          ),
        const SizedBox(height: 24),
        if (step == 0) ...[
          heading('계정 정보를 입력해 주세요', '로그인에 사용할 아이디와 비밀번호를 설정하세요.'),
          input('c_id', '아이디'),
          input('c_pw', '비밀번호 (8~128자)'),
          TextFormField(
            key: const ValueKey('confirmPassword'),
            controller: confirmation,
            enabled: !busy,
            obscureText: true,
            maxLength: 128,
            decoration: const InputDecoration(labelText: '비밀번호 확인'),
            validator: (value) =>
                value != fields['c_pw']!.text ? '비밀번호가 일치하지 않습니다.' : null,
          ),
          const SizedBox(height: 16),
          input('c_phone', '전화번호'),
        ] else ...[
          heading('기본 정보를 입력해 주세요', '선호 종목마다 포지션을 하나씩 선택해 주세요.'),
          if (social) input('c_phone', '전화번호'),
          input('c_name', '이름'),
          input('c_address', '주소'),
          DropdownButtonFormField<String>(
            initialValue: gender,
            decoration: const InputDecoration(labelText: '성별'),
            items: [
              '남성',
              '여성',
              '기타',
            ].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
            onChanged: busy ? null : (v) => setState(() => gender = v!),
          ),
          ListTile(
            title: Text(birthday == null ? '생년월일 선택' : day(birthday!)),
            trailing: const Icon(Icons.calendar_today),
            onTap: busy
                ? null
                : () async {
                    final value = await showDatePicker(
                      context: context,
                      firstDate: DateTime(1900),
                      lastDate: DateTime.now(),
                      initialDate: birthday ?? DateTime(2000),
                    );
                    if (value != null && mounted) {
                      setState(() => birthday = value);
                    }
                  },
          ),
          const ListTile(title: Text('소속팀'), subtitle: Text('무소속')),
          Text(selected.isEmpty ? '선호 종목: 선택 없음' : '선호 종목'),
          Wrap(
            spacing: 8,
            children: sports.entries
                .map(
                  (e) => FilterChip(
                    label: Text(e.value),
                    selected: selected.contains(e.key),
                    onSelected: busy
                        ? null
                        : (value) => setState(() {
                            if (value) {
                              selected.add(e.key);
                            } else {
                              selected.remove(e.key);
                              positions.remove(e.key);
                            }
                          }),
                  ),
                )
                .toList(),
          ),
          for (final sport in sports.keys.where(selected.contains))
            Padding(
              padding: const EdgeInsets.only(top: 16),
              child: DropdownButtonFormField<String>(
                key: ValueKey(sport),
                initialValue: positions[sport],
                decoration: InputDecoration(
                  labelText: '${sports[sport]} 선호 포지션',
                ),
                items: sportPositions[sport]!
                    .map((p) => DropdownMenuItem(value: p, child: Text(p)))
                    .toList(),
                onChanged: busy
                    ? null
                    : (value) => setState(() {
                        positions[sport] = value!;
                      }),
                validator: (value) => value == null ? '포지션을 선택해 주세요.' : null,
              ),
            ),
        ],
        const SizedBox(height: 24),
        FilledButton(
          onPressed: busy
              ? null
              : step == 1
              ? submit
              : () {
                  if (form.currentState!.validate()) setState(() => step = 1);
                },
          child: Text(
            busy
                ? '가입 중…'
                : step == 0
                ? '다음'
                : '회원가입',
          ),
        ),
      ]),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준 (간편가입 화면 재사용)
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준 (공통 종목 포지션 재사용)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
