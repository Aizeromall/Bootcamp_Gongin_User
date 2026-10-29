# 모바일 로그인 개발자 설정

작업자: 최현준 / 작업일: 2026-10-29

## 실행 설정

VS Code의 `공IN 회원앱 (로컬 설정)` 실행은 먼저 `.env`에서 모바일 허용 목록만 동기화합니다.
터미널에서는 다음 순서로 실행합니다.

```sh
python3 tools/prepare_mobile_config.py
flutter run --release --dart-define-from-file=config/social.local.json
```

`API_BASE_URL`은 실제 폰에서 접근 가능한 FastAPI 주소를 사용합니다. 미지정 시 기존 로컬 JSON 값을 유지합니다.
DB 비밀번호, AUTH_TOKEN_SECRET, GOOGLE_APPLICATION_CREDENTIALS는 앱으로 전달하지 않습니다.
Naver 모바일 SDK는 Client Secret을 요구하므로 앱에서 추출 가능한 값입니다. 서버 전용 비밀값과 혼용하지 않습니다.

## Google / Firebase

1. Firebase 콘솔 → Authentication → 로그인 제공업체 → Google 활성화 및 지원 이메일 저장.
2. 프로젝트 설정 → 내 앱에서 실제 Android applicationId / iOS Bundle ID와 일치하는 앱 선택.
3. Android 앱에 개발·릴리즈 서명의 SHA-1/SHA-256 등록 후 최신 `google-services.json`을 `android/app/`에 저장.
4. iOS 앱의 최신 `GoogleService-Info.plist`를 `ios/Runner/`에 저장. 파일에 `CLIENT_ID`, `REVERSED_CLIENT_ID`가 포함되어야 합니다.
5. 위 동기화 명령 후 완전히 다시 빌드. 수동 GOOGLE_IOS_CLIENT_ID 입력은 필요하지 않습니다.

FIREBASE_PROJECT_ID와 GOOGLE_APPLICATION_CREDENTIALS는 서버 Admin SDK의 검증/발송 설정입니다.
이 두 값으로 모바일 OAuth 앱 설정을 대체하거나 서비스 계정 파일을 앱에 포함하지 않습니다.

## Kakao

Kakao Developers → 내 애플리케이션 → 앱 키의 **네이티브 앱 키**를 `.env`의
`KAKAO_NATIVE_APP_KEY`에 입력합니다. REST API 키를 대신 사용하지 않습니다.
카카오 로그인 활성화, Android 패키지명·키 해시 및 iOS Bundle ID를 등록합니다.
서버의 기존 REST API 키·앱 ID 검증 설정은 같은 Kakao 애플리케이션을 가리켜야 합니다.
`KAKAO_APP_ID`는 해당 앱의 숫자 ID입니다. 서버 `.env` 변경 후에는 FastAPI를 재시작해야 합니다.

## Naver

Naver Developers 애플리케이션에서 네이버 로그인 API를 사용 설정하고 Android 패키지명,
iOS URL Scheme(`gongin-naver`) 등 플랫폼 정보를 등록합니다.
기존 `.env`의 NAVER_CLIENT_ID / NAVER_CLIENT_SECRET을 동기화해 사용합니다.
기존 서버 웹 콜백 흐름을 사용할 때만 해당 서버 콜백 URI도 정확히 등록합니다. Swagger `/docs`는 콜백이 아닙니다.

키 또는 콘솔 설정 변경 후 hot reload가 아닌 완전한 재빌드가 필요합니다.
실제 공급자 로그인·FCM 수신은 기기에서 별도 검증해야 합니다.

<!-- 최종 수정 일 : 2026-10-29 / 작업자 : 최현준 -->
