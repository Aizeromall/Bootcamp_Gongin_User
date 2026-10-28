# 알림 Backend 1차 — 채팅·매치 성사·경기 시작 전후

작업자 : 최현준 / 최초 작업 일 : 2026-10-28

후속 승인 반영: Android 프론트 연결 및 동일 계정의 모든 가입 종목 수신을 추가했습니다.
[현재 설정·검증 내역](mobile_auth_notification_setup.md)을 우선 참고하세요. 아래 Front 미연결 설명은 최초 Backend 단계 기록입니다.

## 구현 범위

| 구분 | 대상 및 시점 |
| --- | --- |
| 채팅 | 메시지 저장 성공 시 현재 방 참여자. 발신자 제외. 개인·단체 방에 동일 적용 |
| 매치 성사 | 실력 매칭 예약 정원 충족으로 `r_check=1`이 된 슬롯의 유효 예약 회원 |
| 경기 10분 전 | 성사된 유효 예약 회원 전체 |
| 경기 10분 후 | 해당 예약·회원·구장의 최신 출석값이 **정확히 0**인 회원 |

현재 수신 기기는 **활성 Android FCM 토큰**만 대상으로 합니다. iOS·웹 발송은 이번 범위에 포함하지 않습니다.
팀 가입/팀 매칭 신청·성사, 관리자 임의 발송은 별도 후속 기능입니다. 구장 전체 대여의 `r_check`는 이 단계의 개인 실력 매칭과 구분합니다.
Front 변경은 없으며 실제 앱 토큰 등록·알림 권한·수신 처리 연결 및 실기기 검증은 별도 필요합니다.

## 처리 순서

```text
채팅 메시지 저장 또는 개인 매치 정원 충족
  → 같은 DB 트랜잭션에서 notification_event 저장
  → commit 성공
  → 별도 worker가 대상·시간·예약 취소·출석·활성 기기를 다시 확인
  → Firebase Admin으로 FCM 전송
  → notification_delivery에 기기별 접수/실패 결과 기록
```

- 메시지나 예약 저장이 실패하면 알림 이벤트도 rollback됩니다. 알림 기록 실패 시 업무 저장도 rollback됩니다.
- worker는 기존 성사 경기의 시간 알림도 생성하지만, 과거 매치 성사 알림을 소급해서 일괄 발송하지 않습니다.
- 경기 시각은 `r_date + rs_time`, 한국 시각 기준입니다. `c_r_r_date`를 경기 시각으로 사용하지 않습니다.
- 22~24시 종료는 다음 날 00시로 계산합니다. 예약 시작 시각이 변경되면 예전 시각 이벤트는 취소하고 시간 알림을 새로 계획합니다.
- 출석은 `c_result_record.r_seq + c_id_seq + g_code`로 확인합니다. 같은 조합의 기록이 여러 개면 최신 `c_r_r_seq`를 사용합니다.
  기록 없음·NULL·1은 10분 후 알림 대상이 아닙니다. 첫 유효 시점 점검에서 대상이 아니면 해당 이벤트를 취소합니다.
- 시간 알림은 worker가 실행 중이어야 하며 기본 5초 간격으로 점검합니다. 부하/네트워크 상황에 따라 실제 처리 지연이 가능합니다.

## DB 및 중복 처리

기존에 준비된 `fcm_device`, `notification_event`, `notification_delivery`, `c_result_record.r_seq`를 사용합니다.
새 DDL·자동 마이그레이션은 없습니다. 이벤트는 UNIQUE `(n_key,c_id_seq)`, 기기별 발송은 UNIQUE `(n_seq,f_seq)`가 필요합니다.
서버가 재시작되어도 DB에 기록된 대기 이벤트와 이력은 유지됩니다.

- 메시지 키는 메시지 PK, 경기 알림 키는 예약 PK+시작 시각을 사용합니다.
- MySQL named lock으로 소비자 동시 실행을 차단합니다. 모든 worker는 같은 업무 DB를 사용해야 합니다.
- 발송 의도를 먼저 `processing`과 120초 lease로 기록합니다. 중단 후 lease가 지난 작업은 복구합니다.
- 일시 오류는 최대 3회 시도하며 1차 실패 후 60초, 2차 실패 후 120초 뒤 재시도합니다.
- 만료된 이벤트는 더 보내지 않습니다. 채팅은 발생 후 24시간, 성사/10분 전은 경기 시작까지,
  10분 후 출석 알림은 해당 경기 종료까지 유효합니다. FCM TTL에도 남은 시간을 적용합니다.
- 기기가 없으면 유효기간 내 등록을 기다립니다. 이벤트 점검을 15초 뒤로 분산해 미등록 회원이 큐를 독점하지 않도록 합니다.
- `UNREGISTERED`만 해당 기기를 비활성화합니다. 잘못된 payload/서버 설정 오류로 모든 기기를 삭제하지 않습니다.
- FCM 접수 직후 서버가 중단되는 등 경계 상황의 중복은 완전히 제거할 수 없습니다.
  Front는 data의 `event_id`로 중복을 구분해야 합니다. Android notification tag도 이벤트 ID로 고정합니다.

## 기기 등록 및 개인 정보

기존 `POST /notifications/devices`, `POST /notifications/devices/deactivate`를 사용합니다.
일반/간편 로그인에서 발급받은 **서비스 JWT**로 본인임을 확인합니다.

후속 사용자 승인으로 동일 계정의 모든 가입 종목 수신을 지원합니다. 기기 FK 하나는 유지하고,
발송 조회 시 마지막 종목 suffix만 제거한 기본 ID와 로그인 방식을 대조합니다.
해시 대소문자·밑줄은 BINARY 비교로 보존하며, 발송 직전에도 계정 재연결·탈퇴·해제를 재검사합니다.
로그아웃 시 앱에서 기기 해제를 호출하고, FCM 토큰 갱신 시 다시 등록해야 합니다.
발송 직전 기기 행을 잠가 재연결/해제와 순서를 맞춥니다. 기기 해제는 이미 FCM에 접수된 알림을 회수하지는 못합니다.

푸시의 표시 제목/본문에는 상세 채팅 내용·회원 개인정보를 싣지 않습니다. data에는 `event_id`, `type`, `r_seq` 또는 `s_me_id`와 계정 전환 후 소유권 검사용 `c_id_seq`를 넣습니다. 앱은 이 회원 FK를 로그나 잠금 화면에 표시하지 않습니다.
기기 토큰·서비스 계정 키·FCM 오류 원문을 로그나 문서에 출력하지 않습니다.

## 실행 방법

프로젝트 루트에서 실행합니다. `.env`는 기존 서버 설정을 사용합니다.

```bash
python3 -m pip install -r python/requirements-notification.txt

# 안전 점검: SELECT만 수행. 이벤트·기기 수만 출력하며 발송하지 않음
python3 -m python.FastAPI.notification.worker

# 아래 명령은 실제 DB 처리 및 실제 FCM 전송을 수행합니다. 이번 작업에서는 실행하지 않았습니다.
python3 -m python.FastAPI.notification.worker --send

# 운영 상시 처리: API 서버와 별도 프로세스로 실행
python3 -m python.FastAPI.notification.worker --send --loop
```

API 서버의 main.py는 router 연결 역할을 유지하며 자동으로 worker를 띄우지 않습니다.
운영 배포에서는 프로세스 관리자로 worker를 재실행하도록 구성해야 합니다.
Firebase project ID와 서버 자격 증명이 없으면 실제 발송 worker는 시작할 수 없습니다.

Swagger에서는 `GET /notifications/events`로 **본인 계정의** 알림 상태만 조회할 수 있습니다.
401 인증 오류, 422 조회 개수 검증, 500 DB 오류, 503 JWT 설정 오류 등을 문서화했습니다.
임의 회원에게 발송하는 공개 API는 만들지 않았습니다. WebSocket 메시지는 별도 클라이언트로 전송해야 합니다.

`accepted`는 Firebase가 전송 요청을 접수했다는 뜻입니다. 앱 표시·기기 도착·읽음 완료가 아닙니다.
Android의 알림 권한, 강제 중지, 네트워크와 OS 제한에 따라 표시/전달이 달라질 수 있으므로 실기기 테스트가 필요합니다.
서버가 접수 이력을 가졌다는 이유만으로 사용자에게 도착했다고 표시하지 않습니다.

## 수행한 검증 및 미검증

- 신규 알림 테스트 19개와 기존 인증·기기·채팅·예약·간편로그인·회원가입 회귀 테스트 합계 77개가 통과했습니다.
- 신규 알림 모의 테스트에서 시간 경계, 발신자 제외, 취소/탈퇴, 최신 출석 0/1/NULL, 중복 키,
  기기 재연결, lease 복구, 재시도, outbox 실패 rollback 및 FCM payload를 확인합니다.
- 실제 DB에서는 테이블/컬럼 조회와 읽기 전용 worker preview만 실행했습니다.
  점검 시 알림 이벤트와 활성 기기는 없었습니다. DB 쓰기·테스트 데이터 생성·실제 FCM 발송은 하지 않았습니다.
- `compileall`, `git diff --check`, main 앱 TestClient의 `/docs`, `/health`, 미인증 이력 조회 401을 확인했습니다.
- 설치된 SDK에서 `Message.token` 지원 중단 예고와 기존 TestClient httpx 지원 중단 예고 경고가 있습니다.
  현재 테스트는 통과하지만 추후 SDK 변경 시 FCM 메시지 API 호환성을 재확인해야 합니다.
- 소셜 회원 ID 길이 충돌은 이후 사용자 승인으로 예약·결제·대여 API의 회원 ID 제한을 50자로 맞춰 해결했습니다.

```bash
python3 -m unittest python.tests.test_notification_events python.tests.test_notification_auth python.tests.test_chat python.tests.test_ground_assignment python.tests.test_social_login python.tests.test_register -v
```

최종 수정 일 : 2026-10-28
