// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:firebase_core/firebase_core.dart';

import 'app.dart';
import 'firebase_options.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // gongin 프로젝트의 플랫폼별 SDK 설정을 앱 진입 전에 초기화합니다.
  // 알림 권한·토큰 등록·경기 시간 예약은 별도 알림 기능에서 처리합니다.
  await Firebase.initializeApp(options: DefaultFirebaseOptions.currentPlatform);
  runApp(const ProviderScope(child: MyApp()));
}
// 최종 수정 일 : 2026-10-27
