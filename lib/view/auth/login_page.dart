// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../shared/ui.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import 'register_page.dart';

class LoginPage extends ConsumerStatefulWidget {
  const LoginPage({super.key});
  @override
  ConsumerState<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends ConsumerState<LoginPage> {
  final form = GlobalKey<FormState>();
  final id = TextEditingController();
  final password = TextEditingController();
  bool busy = false;
  @override
  void dispose() {
    id.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> login() async {
    if (!form.currentState!.validate()) {
      return;
    }
    setState(() => busy = true);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            '/auth/login',
            body: {'c_id': id.text.trim(), 'c_pw': password.text},
          );
      if (!mounted) {
        return;
      }
      final available = (result['preferred_stocks'] as List)
          .map((v) => int.tryParse('$v'))
          .whereType<int>()
          .where(sports.containsKey)
          .toList();
      if (available.isEmpty) {
        throw Exception('가입 종목 정보를 확인할 수 없습니다.');
      }
      ref.read(sportProvider.notifier).select(available.first);
      ref.read(sessionProvider.notifier).signIn(result);
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
    body: SafeArea(
      child: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(28),
          child: SizedBox(
            width: 420,
            child: Form(
              key: form,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  // 수정 일 : 2026-10-28 / 작업자 : 양태건
                  // 아이디 로그인 API가 제공하는 실제 흐름만 표시합니다.
                  const Align(
                    alignment: Alignment.centerLeft,
                    child: MemberBrand(),
                  ),
                  const SizedBox(height: 12),
                  const Text(
                    '다시 만나 반가워요. 오늘은 어떤 경기를 뛸까요?',
                    style: TextStyle(fontSize: 12, color: MemberStyle.muted),
                  ),
                  const SizedBox(height: 28),
                  TextFormField(
                    controller: id,
                    decoration: const InputDecoration(
                      labelText: '아이디',
                      hintText: '종목 번호를 제외한 아이디',
                    ),
                    validator: (v) =>
                        (v ?? '').trim().isEmpty ? '아이디를 입력해 주세요.' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: password,
                    obscureText: true,
                    decoration: const InputDecoration(labelText: '비밀번호'),
                    validator: (v) =>
                        (v ?? '').length < 8 ? '8자 이상 입력해 주세요.' : null,
                    onFieldSubmitted: (_) {
                      if (!busy) {
                        login();
                      }
                    },
                  ),
                  const SizedBox(height: 24),
                  FilledButton(
                    onPressed: busy ? null : login,
                    child: Text(busy ? '로그인 중…' : '로그인'),
                  ),
                  TextButton(
                    onPressed: busy
                        ? null
                        : () => Navigator.push(
                            context,
                            MaterialPageRoute<void>(
                              builder: (_) => const RegisterPage(),
                            ),
                          ),
                    child: const Text('처음이신가요? 회원가입'),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
