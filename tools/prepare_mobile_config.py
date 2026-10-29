# 작업자 : 최현준 / 최초 작업 일 : 2026-10-29
"""서버 .env 전체가 아닌 모바일 SDK 허용 목록만 로컬 실행 설정에 전달합니다."""
import json
import os
import plistlib
from pathlib import Path

from dotenv import dotenv_values


def prepare(root: Path) -> None:
    values = dotenv_values(root / '.env')
    target = root / 'config/social.local.json'
    config = json.loads(target.read_text()) if target.exists() else {}
    # DB 비밀번호, JWT 서명키, 서비스 계정은 절대 앱 설정에 복사하지 않습니다.
    allowed = ('API_BASE_URL', 'KAKAO_NATIVE_APP_KEY', 'NAVER_CLIENT_ID',
               'NAVER_CLIENT_SECRET', 'NAVER_URL_SCHEME')
    # 서버 주소만 기존 실행 설정을 유지합니다. 삭제한 SDK 키를 재사용하지 않습니다.
    config = {'API_BASE_URL': config['API_BASE_URL']} if config.get('API_BASE_URL') else {}
    for key in allowed:
        if values.get(key):
            config[key] = values[key]
    config.setdefault('NAVER_URL_SCHEME', 'gongin-naver')

    # Google iOS 식별자는 Firebase가 발급한 앱 설정 파일에서만 가져옵니다.
    plist = root / 'ios/Runner/GoogleService-Info.plist'
    google = plistlib.loads(plist.read_bytes()) if plist.exists() else {}
    native = {'GOOGLE_IOS_CLIENT_ID': google.get('CLIENT_ID', ''),
              'GOOGLE_REVERSED_CLIENT_ID': google.get('REVERSED_CLIENT_ID', ''),
              'KAKAO_NATIVE_APP_KEY': config.get('KAKAO_NATIVE_APP_KEY', ''),
              'NAVER_URL_SCHEME': config['NAVER_URL_SCHEME']}
    # xcconfig에 줄바꿈/구문이 섞인 값을 기록하지 않습니다.
    if any(not isinstance(v, str) or any(c in v for c in '\r\n;$"') for v in native.values()):
        raise ValueError('모바일 설정 형식이 올바르지 않습니다. 값은 출력하지 않습니다.')
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(config, ensure_ascii=False, indent=2) + '\n')
    os.chmod(target, 0o600)
    xcconfig = root / 'ios/Flutter/Social.local.xcconfig'
    xcconfig.write_text('// 자동 생성: tools/prepare_mobile_config.py (Git 제외)\n' +
                        '\n'.join(f'{k} = {v}' for k, v in native.items()) + '\n')
    os.chmod(xcconfig, 0o600)
    print('모바일 허용 목록 동기화 완료. 서버 비밀값은 복사하지 않았습니다.')
    if not google.get('CLIENT_ID') or not google.get('REVERSED_CLIENT_ID'):
        print('Google: Firebase Authentication Google 활성화 후 iOS 설정 파일을 다시 내려받으세요.')
    if not config.get('KAKAO_NATIVE_APP_KEY'):
        print('Kakao: .env에 KAKAO_NATIVE_APP_KEY를 설정하세요. REST API 키와 다릅니다.')


if __name__ == '__main__':
    prepare(Path(__file__).resolve().parents[1])
# 최종 수정 일 : 2026-10-29 / 작업자 : 최현준
