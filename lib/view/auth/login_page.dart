// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/social_login_state.dart';
import '../../service/member_api.dart';
import '../../service/social_login_exception.dart';
import '../../service/social_login_service.dart';
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

  // 수정 일 : 2026-10-28 / 작업자 : 최현준
  // 신규 소셜 회원은 기존 가입 화면에서 추가 정보를 입력합니다.
  Future<void> socialLogin(String provider) async {
    if (busy) return;
    setState(() => busy = true);
    // 이전 오류가 쌓여 같은 메시지만 반복되는 것처럼 보이지 않게 합니다.
    ScaffoldMessenger.of(context).hideCurrentSnackBar();
    try {
      final result = await ref.read(socialLoginProvider)(provider);
      if (!mounted) return;
      if (result['signup_required'] == true) {
        await Navigator.push(
          context,
          MaterialPageRoute<void>(
            builder: (_) =>
                RegisterPage(signupTicket: result['signup_ticket'] as String),
          ),
        );
      } else {
        acceptMemberSession(ref, result);
      }
    } on SocialLoginException catch (error) {
      if (mounted) showMessage(context, error.message);
    } on ApiException catch (error) {
      if (mounted) {
        showMessage(
          context,
          '${SocialLoginService.labels[provider]} 서버 오류 (${error.statusCode}): ${error.message}',
        );
      }
    } on TimeoutException {
      if (mounted) {
        showMessage(
          context,
          '${SocialLoginService.labels[provider]} 서버 응답 시간이 초과되었습니다. 다시 시도해 주세요.',
        );
      }
    } catch (_) {
      if (mounted) {
        showMessage(
          context,
          '${SocialLoginService.labels[provider]} 로그인 응답 또는 연결을 확인할 수 없습니다. 다시 시도해 주세요.',
        );
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  void dispose() {
    id.dispose();
    password.dispose();
    super.dispose();
  }

  Future<void> login() async {
    if (busy) return;
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
      acceptMemberSession(ref, result);
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
                    child: Padding(
                      padding: const EdgeInsets.all(14),
                      child: Text(busy ? '로그인 중…' : '로그인'),
                    ),
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
                  const Divider(height: 32),
                  const Center(child: Text('간편 로그인')),
                  const SizedBox(height: 12),
                  // 수정 일 : 2026-10-28 / 작업자 : 최현준
                  // 제공된 원본 비율을 유지하며 이미지 탭은 기존 인증 동작에 연결합니다.
                  for (final provider in const {
                    'google': (
                      'Google',
                      'assets/images/Theme=Light, Show text=Yes, Shape=Square, Platform=Android+Web@4x.png',
                    ),
                    'kakao': ('카카오', 'assets/images/kakao_login_en_medium.png'),
                    'naver': (
                      '네이버',
                      'assets/images/NAVER_login_Light_KR_green_narrow_H56.png',
                    ),
                  }.entries)
                    Padding(
                      padding: const EdgeInsets.only(bottom: 8),
                      child: TextButton(
                        key: ValueKey('social-${provider.key}'),
                        style: TextButton.styleFrom(padding: EdgeInsets.zero),
                        onPressed: busy
                            ? null
                            : () => socialLogin(provider.key),
                        child: Opacity(
                          opacity: busy ? 0.5 : 1,
                          child: Image.asset(
                            provider.value.$2,
                            height: 56,
                            width: double.infinity,
                            fit: BoxFit.contain,
                            semanticLabel: '${provider.value.$1}로 계속하기',
                          ),
                        ),
                      ),
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
// 최종 수정 일 : 2026-10-28 / 작업자 : 최현준
