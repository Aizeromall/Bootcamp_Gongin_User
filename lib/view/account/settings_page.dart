// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/theme_state.dart';
import '../shared/ui.dart';

class SettingsPage extends ConsumerStatefulWidget {
  const SettingsPage({super.key});

  @override
  ConsumerState<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends ConsumerState<SettingsPage> {
  bool busy = false;

  Future<void> select(ThemeMode mode) async {
    if (busy) return;
    setState(() => busy = true);
    try {
      await ref.read(themeModeProvider.notifier).select(mode);
    } catch (_) {
      if (mounted) showMessage(context, '설정을 저장하지 못했습니다. 다시 시도해 주세요.');
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final current = ref.watch(themeModeProvider);
    return Scaffold(
      appBar: AppBar(title: const Text('설정')),
      body: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Text('화면 모드', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          for (final entry in {
            ThemeMode.system: '시스템 설정 따르기',
            ThemeMode.light: '라이트 모드',
            ThemeMode.dark: '다크 모드',
          }.entries)
            ListTile(
              title: Text(entry.value),
              selected: current == entry.key,
              trailing: current == entry.key ? const Icon(Icons.check) : null,
              onTap: busy ? null : () => select(entry.key),
            ),
        ],
      ),
    );
  }
}

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
