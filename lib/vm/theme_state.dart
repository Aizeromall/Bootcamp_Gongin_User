// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

final themeModeProvider = NotifierProvider<ThemeModeNotifier, ThemeMode>(
  ThemeModeNotifier.new,
);

class ThemeModeNotifier extends Notifier<ThemeMode> {
  static const _key = 'member_theme_mode';
  int _revision = 0;

  @override
  ThemeMode build() {
    _load();
    return ThemeMode.system;
  }

  Future<void> _load() async {
    final revision = _revision;
    try {
      final preferences = await SharedPreferences.getInstance();
      final saved = preferences.getString(_key);
      if (!ref.mounted || revision != _revision) return;
      state =
          ThemeMode.values.where((mode) => mode.name == saved).firstOrNull ??
          ThemeMode.system;
    } catch (_) {
      // 기기 저장소가 없는 테스트 환경에서는 시스템 테마를 유지합니다.
    }
  }

  Future<void> select(ThemeMode mode) async {
    final revision = ++_revision;
    final preferences = await SharedPreferences.getInstance();
    final saved = await preferences.setString(_key, mode.name);
    if (!saved) throw StateError('화면 설정을 저장하지 못했습니다.');
    if (ref.mounted && revision == _revision) state = mode;
  }
}

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
