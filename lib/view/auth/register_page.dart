// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../shared/ui.dart';

class RegisterPage extends ConsumerStatefulWidget {
  const RegisterPage({super.key});
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
  static const positionOptions = {
    1: ['FW', 'MF', 'DF', 'GK'],
    2: ['센터', '가드', '포워드'],
    3: ['투수', '포수', '내야수', '외야수'],
    4: ['세터', '리베로', '센터', '레프트', '라이트'],
  };
  String gender = '남성';
  DateTime? birthday;
  bool busy = false;
  @override
  void dispose() {
    for (final c in fields.values) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> submit() async {
    if (!form.currentState!.validate()) {
      return;
    }
    if (selected.isEmpty || birthday == null) {
      showMessage(context, '생년월일과 선호 종목을 선택해 주세요.');
      return;
    }
    setState(() => busy = true);
    try {
      await ref
          .read(memberApiProvider)
          .request(
            '/auth/register',
            body: {
              for (final entry in fields.entries)
                entry.key: entry.key == 'c_pw'
                    ? entry.value.text
                    : entry.value.text.trim(),
              'c_team': '무소속',
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
      showMessage(context, '가입이 완료되었습니다. 로그인해 주세요.');
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

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('회원가입')),
    body: Form(
      key: form,
      child: pageContent([
        heading('새로운 경기를 시작해요', '선호 종목은 최대 4개까지 선택할 수 있어요.'),
        for (final entry in {
          'c_id': '아이디',
          'c_pw': '비밀번호 (8~128자)',
          'c_name': '이름',
          'c_address': '주소',
          'c_phone': '전화번호',
        }.entries)
          Padding(
            padding: const EdgeInsets.only(bottom: 16),
            child: TextFormField(
              controller: fields[entry.key],
              obscureText: entry.key == 'c_pw',
              maxLength: {
                'c_id': 40,
                'c_pw': 128,
                'c_name': 45,
                'c_address': 255,
                'c_phone': 30,
              }[entry.key],
              decoration: InputDecoration(labelText: entry.value),
              validator: (v) {
                if ((v ?? '').trim().isEmpty) {
                  return '필수 입력 항목입니다.';
                }
                if (entry.key == 'c_pw' && v!.length < 8) {
                  return '8자 이상 입력해 주세요.';
                }
                return null;
              },
            ),
          ),
        DropdownButtonFormField<String>(
          initialValue: gender,
          decoration: const InputDecoration(labelText: '성별'),
          items: [
            '남성',
            '여성',
            '기타',
          ].map((v) => DropdownMenuItem(value: v, child: Text(v))).toList(),
          onChanged: (v) => setState(() => gender = v!),
        ),
        ListTile(
          title: Text(birthday == null ? '생년월일 선택' : day(birthday!)),
          trailing: const Icon(Icons.calendar_today),
          onTap: () async {
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
              decoration: InputDecoration(labelText: '${sports[sport]} 선호 포지션'),
              items: positionOptions[sport]!
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
        const SizedBox(height: 24),
        FilledButton(
          onPressed: busy ? null : submit,
          child: Text(busy ? '가입 중…' : '회원가입'),
        ),
      ]),
    ),
  );
}
// 최종 수정 일 : 2026-10-26 / 작업자 : 양태건
