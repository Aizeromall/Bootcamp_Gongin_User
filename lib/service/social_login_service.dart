// 작업자 : 최현준
// 최초 작업 일 : 2026-10-28
// 수정 일 : 2026-10-29 / 작업자 : 최현준
// Google iOS 설정 누락은 Firebase 앱 설정 파일 재다운로드 절차로 안내합니다.
import 'dart:async';

import 'package:firebase_auth/firebase_auth.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:naver_login_sdk/naver_login_sdk.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:kakao_flutter_sdk_user/kakao_flutter_sdk_user.dart';

import 'social_login_exception.dart';

/// 토큰은 서버 검증에만 사용합니다. SDK·설정 조회는 가상 테스트에서 교체합니다.
class SocialLoginService {
  SocialLoginService({
    this.settings = const {
      'KAKAO_NATIVE_APP_KEY': String.fromEnvironment('KAKAO_NATIVE_APP_KEY'),
      'NAVER_CLIENT_ID': String.fromEnvironment('NAVER_CLIENT_ID'),
      'NAVER_CLIENT_SECRET': String.fromEnvironment('NAVER_CLIENT_SECRET'),
      'NAVER_URL_SCHEME': String.fromEnvironment(
        'NAVER_URL_SCHEME',
        defaultValue: 'gongin-naver',
      ),
    },
    this.platform,
    this.readNativeSettings,
    this.authenticateSdk,
  });
  final Map<String, String> settings;
  final TargetPlatform? platform;
  final Future<Map<String, dynamic>> Function()? readNativeSettings;
  final Future<String> Function(String provider, String? googleClientId)?
  authenticateSdk;
  Future<void>? _googleReady;
  bool _busy = false;
  final _active = <String>{};
  static const labels = {'google': 'Google', 'kakao': '카카오', 'naver': '네이버'};
  String _setting(String key) => (settings[key] ?? '').trim();

  Future<void> signOut(String? provider) async {
    if (kIsWeb || !_active.contains(provider)) return;
    switch (provider) {
      case 'google':
        await FirebaseAuth.instance.signOut();
        await GoogleSignIn.instance.signOut();
      case 'kakao':
        await UserApi.instance.logout();
      case 'naver':
        await NaverLoginSDK.logout();
    }
    _active.remove(provider);
  }

  /* **********************
   * 버그 발생 일 : 2026-10-28 / 위치 : Google iOS SDK 초기화
   * 1. 발생 위치 : clientID가 없는 상태의 initialize/authenticate
   * 2. 버그 내용 : 네이티브 NSException으로 Dart catch 전에 앱 종료
   * 3. 디버깅 내용 : 실제 Bundle 설정·콜백 스킴 확인 후 SDK 호출 허용
   * 4. 테스트 사항 : 누락·스킴 불일치·취소·재시도·중복 제출 mock 검사
   * 5. 결과 및 추후 보완 사항 : 실제 공급자 인증은 콘솔 설정 후 별도 확인
   ************************/
  Future<String?> _preflight(String provider) async {
    final target = platform ?? defaultTargetPlatform;
    final label = labels[provider];
    if (label == null) throw const SocialLoginException('지원하지 않는 로그인 방식입니다.');
    if (kIsWeb ||
        (target != TargetPlatform.android && target != TargetPlatform.iOS)) {
      throw SocialLoginException('$label 로그인은 Android·iOS 앱에서 이용해 주세요.');
    }
    if (provider == 'kakao' &&
        !RegExp(r'^[a-fA-F0-9]{32}$')
            .hasMatch(_setting('KAKAO_NATIVE_APP_KEY'))) {
      throw const SocialLoginException(
        '카카오 네이티브 앱 키가 없거나 올바르지 않습니다. 앱 설정이 필요합니다.',
      );
    }
    if (provider == 'naver' &&
        (_setting('NAVER_CLIENT_ID').isEmpty ||
            _setting('NAVER_CLIENT_SECRET').isEmpty)) {
      throw const SocialLoginException(
        '네이버 Client ID·Secret이 없습니다. 앱 설정이 필요합니다.',
      );
    }
    if (target != TargetPlatform.iOS) return null;
    final native =
        await (readNativeSettings?.call() ??
            const MethodChannel('gongin/social_preflight')
                .invokeMapMethod<String, dynamic>('settings')
                .then((value) => value ?? <String, dynamic>{}));
    final schemes = (native['schemes'] as List? ?? [])
        .whereType<String>()
        .toSet();
    String callback;
    String? client;
    if (provider == 'google') {
      // Google ID는 네이티브 Firebase 설정에서만 읽습니다. 중복 Dart 설정은 제거합니다.
      client = (native['googleClientId'] as String? ?? '').trim();
      if (!RegExp(r'^[a-zA-Z0-9-]+\.apps\.googleusercontent\.com$')
          .hasMatch(client)) {
        throw const SocialLoginException(
          'Firebase에서 Google 로그인을 활성화한 뒤 iOS GoogleService-Info.plist를 다시 받아 앱을 빌드해 주세요.',
        );
      }
      callback =
          'com.googleusercontent.apps.${client.split('.apps.googleusercontent.com').first}';
    } else if (provider == 'kakao') {
      callback = 'kakao${_setting('KAKAO_NATIVE_APP_KEY')}';
    } else {
      callback = _setting('NAVER_URL_SCHEME');
      if (!RegExp(r'^[a-zA-Z][a-zA-Z0-9+.-]*$').hasMatch(callback)) {
        throw const SocialLoginException('네이버 iOS URL Scheme 설정이 올바르지 않습니다.');
      }
    }
    if (!schemes.contains(callback)) {
      throw SocialLoginException(
        '$label iOS 콜백 스킴이 앱에 등록되지 않았습니다. 설정 후 다시 빌드해 주세요.',
      );
    }
    return client;
  }

  Future<String> authenticate(String provider) async {
    final label = labels[provider] ?? '간편';
    if (_busy) throw const SocialLoginException('로그인이 진행 중입니다. 잠시 기다려 주세요.');
    _busy = true;
    try {
      final client = await _preflight(provider);
      final token =
          await (authenticateSdk?.call(provider, client) ??
              _authenticateSdk(provider, client));
      if (token.isEmpty) {
        throw SocialLoginException('$label 인증 토큰을 확인할 수 없습니다. 다시 시도해 주세요.');
      }
      _active.add(provider);
      return token;
    } on SocialLoginException {
      rethrow;
    } on GoogleSignInException catch (error) {
      if (error.code == GoogleSignInExceptionCode.canceled) {
        throw const SocialLoginException('Google 로그인을 취소했습니다.');
      }
      if (error.code == GoogleSignInExceptionCode.clientConfigurationError ||
          error.code == GoogleSignInExceptionCode.providerConfigurationError) {
        throw const SocialLoginException('Google 로그인 앱·콘솔 설정을 확인해 주세요.');
      }
      throw const SocialLoginException('Google 인증을 완료하지 못했습니다. 다시 시도해 주세요.');
    } on KakaoClientException catch (error) {
      throw SocialLoginException(
        error.reason == ClientErrorCause.cancelled
            ? '카카오 로그인을 취소했습니다.'
            : '카카오 인증을 완료하지 못했습니다. 다시 시도해 주세요.',
      );
    } on FirebaseAuthException catch (error) {
      throw SocialLoginException(
        error.code == 'network-request-failed'
            ? 'Google 인증 서버에 연결하지 못했습니다. 네트워크를 확인해 주세요.'
            : 'Google Firebase 인증에 실패했습니다. 앱·콘솔 설정을 확인해 주세요.',
      );
    } on PlatformException catch (error) {
      final canceled = [
        'CANCELED',
        'CANCELLED',
        'USER_CANCEL',
        'SIGN_IN_CANCELED',
      ].contains(error.code.toUpperCase());
      throw SocialLoginException(
        canceled ? '$label 로그인을 취소했습니다.' : '$label SDK 연결 또는 앱 설정을 확인해 주세요.',
      );
    } on MissingPluginException {
      throw SocialLoginException(
        '$label 네이티브 설정 확인 기능을 사용할 수 없습니다. 앱을 완전히 다시 빌드해 주세요.',
      );
    } on TimeoutException {
      throw SocialLoginException('$label 인증 응답 시간이 초과되었습니다. 다시 시도해 주세요.');
    } catch (_) {
      throw SocialLoginException('$label 인증을 완료하지 못했습니다. 네트워크와 앱 설정을 확인해 주세요.');
    } finally {
      _busy = false;
    }
  }

  Future<String> _authenticateSdk(String provider, String? iosClient) async {
    switch (provider) {
      case 'google':
        // 실패한 초기화 Future는 재시도할 수 있도록 폐기합니다.
        try {
          await (_googleReady ??= GoogleSignIn.instance.initialize(
            clientId: iosClient,
          ));
        } catch (_) {
          _googleReady = null;
          rethrow;
        }
        final account = await GoogleSignIn.instance.authenticate();
        final credential = GoogleAuthProvider.credential(
          idToken: account.authentication.idToken,
        );
        final result = await FirebaseAuth.instance.signInWithCredential(
          credential,
        );
        return await result.user?.getIdToken() ?? '';
      case 'kakao':
        KakaoSdk.init(nativeAppKey: _setting('KAKAO_NATIVE_APP_KEY'));
        final token = await isKakaoTalkInstalled()
            ? await UserApi.instance.loginWithKakaoTalk()
            : await UserApi.instance.loginWithKakaoAccount();
        return token.accessToken;
      case 'naver':
        final initialized = await NaverLoginSDK.initialize(
          clientId: _setting('NAVER_CLIENT_ID'),
          clientSecret: _setting('NAVER_CLIENT_SECRET'),
          clientName: '공IN 중개사',
          urlScheme: _setting('NAVER_URL_SCHEME'),
        );
        if (!initialized) {
          throw const SocialLoginException(
            '네이버 SDK를 초기화하지 못했습니다. 설정을 확인해 주세요.',
          );
        }
        // false만으로 취소인지 오류인지 단정하지 않습니다.
        if (!await NaverLoginSDK.login()) {
          throw const SocialLoginException(
            '네이버 로그인이 완료되지 않았습니다. 취소했거나 인증에 실패했습니다.',
          );
        }
        return NaverLoginSDK.getAccessToken();
      default:
        throw const SocialLoginException('지원하지 않는 로그인 방식입니다.');
    }
  }
}
// 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
