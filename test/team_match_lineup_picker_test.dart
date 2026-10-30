// 작업자 : 최현준 / 최초 작업 일 : 2026-10-30
import 'package:bootcamp_project_gongin_admin_app/view/shared/team_lineup_picker.dart';
import 'package:bootcamp_project_gongin_admin_app/vm/team_match_lineup_state.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('정확히 절반을 선택해야 확인할 수 있고 나머지 팀원은 비활성화', (tester) async {
    List<String>? result;
    final container = ProviderContainer(
      overrides: [
        // 수정 일 : 2026-10-30 / 작업자 : 신현진
        // teamMatchLineupProvider가 AsyncNotifier로 바뀌어 build 결과만 바꾸는 overrideWithBuild 사용
        teamMatchLineupProvider.overrideWithBuild(
          (ref, notifier) async => {
            'required_count': 2,
            'results': [
              {'c_id_seq': 'a_01', 'c_name': '가'},
              {'c_id_seq': 'b_01', 'c_name': '나'},
              {'c_id_seq': 'c_01', 'c_name': '다'},
            ],
          },
        ),
      ],
    );
    addTearDown(container.dispose);
    await tester.pumpWidget(
      UncontrolledProviderScope(
        container: container,
        child: MaterialApp(
          home: Scaffold(
            body: Builder(
              builder: (context) => FilledButton(
                onPressed: () async => result = await selectTeamLineup(
                  context,
                  query: (memberId: 'a_01', rentalId: 1, postId: null),
                ),
                child: const Text('선택'),
              ),
            ),
          ),
        ),
      ),
    );
    await tester.tap(find.text('선택'));
    await tester.pumpAndSettle();
    var confirm = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '선택 완료'),
    );
    expect(confirm.onPressed, isNull);
    await tester.tap(find.widgetWithText(CheckboxListTile, '가'));
    await tester.tap(find.widgetWithText(CheckboxListTile, '나'));
    await tester.pumpAndSettle();
    expect(
      tester
          .widget<CheckboxListTile>(find.widgetWithText(CheckboxListTile, '다'))
          .onChanged,
      isNull,
    );
    confirm = tester.widget<FilledButton>(
      find.widgetWithText(FilledButton, '선택 완료'),
    );
    expect(confirm.onPressed, isNotNull);
    await tester.tap(find.text('선택 완료'));
    await tester.pumpAndSettle();
    expect(result, ['a_01', 'b_01']);
  });
}
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 신현진 (AsyncNotifier 변환에 맞춰 override 방식 변경)
