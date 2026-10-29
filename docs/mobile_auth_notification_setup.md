# 모바일 간편 로그인·FCM 프론트 연결

작업자 : 최현준 / 최초 작업 일 : 2026-10-28

## 구현 내용

- 로그인 버튼 아래 Google·카카오·네이버를 추가했습니다.
- Google SDK → Firebase ID 토큰 → `POST /auth/google/login`.
- 카카오 SDK 토큰 → `POST /auth/kakao/mobile`. 서버에서 회원 번호·앱 ID·만료를 검증합니다.
- 네이버 SDK 토큰 → `POST /auth/naver/mobile`. 서버가 공급자 프로필 API에서 회원 ID를 확인합니다. 앱 입력 ID는 신뢰하지 않습니다.
- 미가입자는 기존 `RegisterPage`에서 전화번호·이름·주소·성별·생년월일·선호 종목·포지션을 입력합니다. 비밀번호/팀 선택은 받지 않습니다.
- MySQL 회원 확인/가입 후 서비스 JWT를 발급합니다. 간편가입자는 `POST /chat/session-token`으로 본인 종목의 채팅 인증을 받을 수 있습니다.
- 신규 페이지·Python 요청 클래스·DB 컬럼은 추가하지 않았습니다. 실제 DB 데이터도 수정하지 않았습니다.

## Android 실행 준비

1. `config/social.example.json`을 참고해 Git 제외된 `config/social.local.json`을 작성합니다. 서버 `.env` 전체를 복사하지 마세요.
2. `API_BASE_URL`: 에뮬레이터는 `http://10.0.2.2:8000`, 실기기는 폰에서 접근 가능한 서버 주소입니다. 운영은 HTTPS가 필요합니다.
   Android debug에서만 개발용 HTTP를 허용했습니다. release와 iOS는 기본 네트워크 보안 정책을 유지합니다.
3. `KAKAO_NATIVE_APP_KEY`에 네이티브 앱 키를 입력합니다. Android 콜백 manifest에도 빌드 시 전달됩니다. 서버 `.env`에는 별도 숫자 앱 ID인 `KAKAO_APP_ID`가 필요합니다. 기존 REST 키/시크릿/URI는 브라우저 흐름용으로 유지합니다.
4. 카카오 콘솔에 Android 패키지명·서명 키 해시를 등록하고 로그인을 활성화합니다.
5. 네이버 콘솔에 Android 패키지명·앱명을 등록합니다. 로컬 JSON에 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`을 입력합니다. 모바일 SDK가 요구하는 값으로 앱 바이너리에 포함되며, Git 제외/난독화가 추출 방지를 보장하지 않습니다. 서버 JWT 비밀키·서비스 계정 JSON은 절대 앱에 넣지 않습니다.
6. Firebase Authentication에서 Google 활성화 및 Android SHA 인증서 등록 후 `android/app/google-services.json`을 다시 다운로드합니다. 현재 파일은 `oauth_client`가 비어 있습니다. 내부 OAuth 설정이 필요하다는 뜻이지 웹앱 로그인을 구현한다는 뜻이 아닙니다.
7. 앱 패키지명은 기존 `com.example.bootcamp_project_gongin_admin_app`을 유지합니다.

```sh
flutter pub get
flutter run --dart-define-from-file=config/social.local.json
```

선택한 네이버 패키지는 `naver_login_sdk` 3.2.1입니다. 처음 검토한 `flutter_naver_login` 2.1.1은 Android 초기화 시 Client Secret 출력 코드가 있어 제거했습니다. 대체 패키지의 Flutter/native 초기화 래퍼에서 같은 출력을 발견하지 않았다는 확인이며, 전체 공급망 보안 감사는 아닙니다.

## iOS 로그인 준비

- 이번 푸시는 **Android만 등록/발송**합니다. iOS FCM/APNs는 추가하지 않았습니다.
- 간편 로그인 SDK 호출은 Android·iOS를 지원합니다. iOS 실로그인은 콘솔/콜백 설정 후 별도 검증해야 합니다.
- Google 활성화 후 iOS `GoogleService-Info.plist`도 다시 받습니다. 현재 파일에는 CLIENT_ID·REVERSED_CLIENT_ID가 없습니다.
- `python3 tools/prepare_mobile_config.py`로 `.env`의 모바일 허용 목록과 Firebase plist에서 로컬 JSON/xcconfig를 생성합니다. Google ID를 별도로 입력하지 않습니다.
- 콘솔에 iOS Bundle ID/URL Scheme을 등록합니다. 상세 설정은 `developer_login_setup.md`를 따릅니다.
- 후속 호환성 검증에서 iOS 시뮬레이터 빌드·시작 화면 표시를 확인했습니다. 실제 기기 서명·간편 로그인은 미검증입니다.

### iOS 패키지 호환 수정 (2026-10-28 / 최현준)

pub.dev 전체 최신 Firebase 5.1.0/7.0.1/17.0.1은 GoogleSignIn iOS 9.x와 GTMSessionFetcher 조건이 충돌했습니다.
`firebase_core 4.15.2`, `firebase_auth 6.7.1`, `firebase_messaging 16.7.1`을 정확한 버전으로 고정했습니다.
Google Flutter 패키지 7.2.0 및 iOS 플러그인 6.3.8은 최신을 유지합니다.
SPM 실제 해결 결과는 Firebase iOS 12.19.3 / GoogleSignIn 9.2.0 / GTMSessionFetcher 3.5.0입니다.
Flutter 테스트 48개, 관련 Dart 정적 검사, 시뮬레이터 빌드·실행을 확인했습니다.
네이버 SDK는 CocoaPods 병행 경고가 있으며, iOS 푸시 미설정에 따른 aps-environment 경고도 있습니다. 실제 공급자 인증·FCM 발송은 검증하지 않았습니다.

## 알림 프로세스

1. 로그인 → Android 알림 권한 요청 → FCM 토큰 발급 → 서비스 JWT로 `/notifications/devices` 자동 등록. 사용자가 토큰을 복사/입력하지 않습니다.
2. DB 기기 FK 하나를 유지하면서 발송 대상은 같은 기본 ID·로그인 방식의 **모든 가입 종목**으로 확장합니다. 마지막 `_01`~`_04`만 제거하고 BINARY 비교해 해시 대소문자/밑줄을 보존합니다. 발송 직전에도 재연결·탈퇴·해제를 검사합니다.
3. 채팅·매치 성사·경기 10분 전·시작 10분 후 출석값 `0` 이벤트는 기존 서버 worker가 발송합니다. 프론트에 경기 타이머를 중복 생성하지 않습니다.
4. 실행 중에는 안내 배너, 백그라운드/종료 상태에서는 서버 notification payload를 OS가 표시합니다. 탭하면 로그인·회원 소유 여부를 확인해 기존 메시지 목록 또는 예약 상세를 엽니다.
5. `s_me_id`는 방 번호가 아닌 메시지 번호이므로 채팅은 목록으로 이동합니다.
6. 토큰 갱신 시 자동 등록, 로그아웃 시 서버 해제 및 로컬 FCM 토큰 폐기를 수행합니다. 서버 오류 시에도 로컬 폐기를 시도합니다. FCM 접수가 OS 표시/읽음을 보장하지는 않습니다.
7. 홈 ‘푸시 알림 설정’에서 상태·권한 확인·재연결이 가능합니다. 차단된 권한은 Android 시스템 설정에서 허용해야 합니다.

서비스 JWT는 현재 30분이며 자동 갱신 API는 없습니다. 만료 후 보호 API 실패 시 재로그인이 필요합니다. 등록된 기기의 서버 푸시 발송이 JWT 30분에 맞춰 종료되는 것은 아닙니다. 실제 발송에는 서버 worker 운영도 필요하며, 이번 작업에서 실제 발송 명령은 실행하지 않았습니다.

## 검증과 후속 확인

2026-10-28 후속 종료 방어 수정 / 작업자: 최현준

- iOS `AppDelegate`의 읽기 전용 채널에서 앱 Bundle의 Google Client ID와 등록 콜백 스킴만 조회합니다. 비밀값·회원 정보·SDK 인증 API는 호출하지 않습니다.
- Google Client ID가 없거나 세 공급자의 콜백 스킴이 맞지 않으면 인증 SDK 진입 전에 차단합니다. 카카오·네이버 모바일 키 누락도 먼저 검사합니다.
- 공급자별 설정 오류·취소·SDK/Firebase 오류·서버 상태 코드를 구분합니다. 네이버 SDK의 false 결과는 취소/실패를 정확히 구분할 수 없어 이를 안내합니다.
- 실패한 Google 초기화 Future를 폐기하고 로그인 요청을 직렬화합니다. 기존 스낵바는 새 요청 시 숨깁니다.
- 새 회귀 테스트 13개 포함 Flutter 전체 61개 통과, 수정 Dart 정적 검사 통과. 테스트는 SDK/서버 응답을 가상화하며, 네이티브 SDK 자체의 모든 예외나 실제 인증 성공을 보장하지 않습니다.
- Swift 변경은 hot reload만으로 반영되지 않으므로 앱을 완전히 다시 빌드해야 합니다. 키/콘솔 설정은 임의로 만들거나 변경하지 않았습니다.
- 수정 후 iOS 시뮬레이터 debug 빌드 통과. 이번 요청에서는 실물폰 재설치·실제 공급자 인증·DB 쓰기·푸시 발송을 하지 않았습니다.

- 외부 소켓을 차단한 Backend mock 테스트 205개 통과.
- Flutter 전체 테스트 48개 통과. 새 6개는 중복 등록·갱신·권한 거부·로그아웃 실패·종료 상태 탭·계정 소유권·재시도·간편가입 화면을 검증합니다.
- 변경 Dart 파일 정적 검사 통과. 전체 분석에는 기존 모델 snake_case 명명 관련 경고가 남아 있습니다.
- Android debug APK 빌드 성공: `build/app/outputs/flutter-apk/app-debug.apk`. 플러그인의 기존 Kotlin Gradle Plugin 및 Java 8/deprecated API 경고가 발생했습니다. 빌드 성공이 실제 로그인/푸시 수신 성공을 뜻하지 않습니다.
- `pubspec.yaml`에 등록된 `images/` 폴더가 없어 Flutter 경고가 발생합니다. 사용자 설정이므로 임의로 삭제하지 않았습니다.
- 실제 공급자 인증·DB 쓰기·FCM 발송·기기 수신·강제 종료/절전 정책은 미검증입니다. mock 통과를 실제 연동 완료로 판단하지 마세요.
- Google 설정 파일 재다운로드, 플랫폼별 키/서명 등록, 서버 `KAKAO_APP_ID`, worker 실행 설정 후 실기기로 확인해야 합니다.

참고: [Firebase 로그인](https://firebase.google.com/docs/auth/flutter/federated-auth), [FCM 수신](https://firebase.google.com/docs/cloud-messaging/flutter/receive-messages), [카카오 Flutter](https://developers.kakao.com/docs/en/kakaologin/flutter), [네이버 SDK](https://developers.naver.com/docs/login/sdks/sdks.md), [선택한 네이버 패키지](https://pub.dev/packages/naver_login_sdk).

최종 수정 일 : 2026-10-28 / 작업자 : 최현준
