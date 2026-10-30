// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:bootcamp_project_gongin_admin_app/view/account/settings_page.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/theme_state.dart';
import 'package:bootcamp_project_gongin_admin_app/view/shared/member_components.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  testWidgets('다크 테마에서 공통 패널과 제목이 어두운 바탕에서 표시', (tester) async {
    await tester.pumpWidget(
      MaterialApp(
        theme: ThemeData.dark(),
        home: const Scaffold(
          body: MemberPanel(
            color: Colors.white,
            child: MemberSectionTitle('테스트 제목'),
          ),
        ),
      ),
    );
    final material = tester
        .widgetList<Material>(find.byType(Material))
        .where(
          (widget) =>
              widget.color == ThemeData.dark().colorScheme.surfaceContainerHigh,
        );
    expect(material, isNotEmpty);
    final title = tester.widget<Text>(find.text('테스트 제목'));
    expect(title.style?.color, ThemeData.dark().colorScheme.onSurface);
  });
  testWidgets('화면 모드를 선택하고 재생성해도 저장된 값을 사용', (tester) async {
    SharedPreferences.setMockInitialValues({});
    final container = ProviderContainer();
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: const MaterialApp(home: SettingsPage()),
      ),
    );
    await tester.pumpAndSettle();
    await tester.tap(find.text('다크 모드'));
    await tester.pumpAndSettle();
    expect(container.read(themeModeProvider), ThemeMode.dark);
    await tester.pumpWidget(const SizedBox());
    container.dispose();
    final restored = ProviderContainer();
    addTearDown(restored.dispose);
    restored.read(themeModeProvider);
    await tester.pumpAndSettle();
    expect(restored.read(themeModeProvider), ThemeMode.dark);
  });
}

// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
