// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';

import 'member_style.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 전체 목업의 브랜드·연한 정보 카드·정보 행을 공유합니다.
class MemberBrand extends StatelessWidget {
  const MemberBrand({super.key, this.large = false});
  final bool large;
  @override
  Widget build(BuildContext context) => Column(
    mainAxisSize: MainAxisSize.min,
    children: [
      Container(
        width: large ? 100 : 52,
        height: large ? 100 : 52,
        decoration: BoxDecoration(
          color: MemberStyle.greenSurface,
          shape: BoxShape.circle,
          border: Border.all(color: MemberStyle.line),
        ),
        child: Icon(
          Icons.sports_soccer,
          size: large ? 68 : 34,
          color: MemberStyle.green,
        ),
      ),
      const SizedBox(height: 12),
      Text.rich(
        TextSpan(
          style: TextStyle(
            fontSize: large ? 27 : 23,
            fontWeight: FontWeight.w900,
            color: Theme.of(context).colorScheme.onSurface,
            letterSpacing: -0.7,
          ),
          children: const [
            TextSpan(text: '공 '),
            TextSpan(
              text: 'In',
              style: TextStyle(
                color: MemberStyle.blue,
                fontStyle: FontStyle.italic,
              ),
            ),
            TextSpan(text: ' 중개사'),
          ],
        ),
      ),
    ],
  );
}

class MemberPanel extends StatelessWidget {
  const MemberPanel({
    super.key,
    required this.child,
    this.color = MemberStyle.surface,
  });
  final Widget child;
  final Color color;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(bottom: 16),
    child: Material(
      color:
          Theme.of(context).brightness == Brightness.dark &&
              (color == Colors.white || color == MemberStyle.surface)
          ? Theme.of(context).colorScheme.surfaceContainerHigh
          : color,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      clipBehavior: Clip.antiAlias,
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: SizedBox(width: double.infinity, child: child),
      ),
    ),
  );
}

class MemberInfoRow extends StatelessWidget {
  const MemberInfoRow(this.label, this.value, {super.key});
  final String label;
  final Object? value;
  @override
  // 수정 일 : 2026-10-30 / 작업자 : 최현준
  // 정보 이름과 값을 크기와 대비로 구분합니다.
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 8),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 88,
          child: Text(
            label,
            style: TextStyle(
              fontSize: 13,
              height: 1.45,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
          ),
        ),
        Expanded(
          child: Text(
            '${value ?? '미등록'}',
            style: const TextStyle(
              fontSize: 14,
              height: 1.45,
              fontWeight: FontWeight.w600,
            ),
          ),
        ),
      ],
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (공통 패널 테마 대응)

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 실제 서버 상태를 짧은 라벨로 표현하며 색상만으로 상태를 구분하지 않습니다.
class MemberStatusBadge extends StatelessWidget {
  const MemberStatusBadge(
    this.label, {
    super.key,
    this.color = MemberStyle.blue,
  });
  final String label;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: color.withValues(alpha: 0.09),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      label,
      style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w700),
    ),
  );
}

class MemberMetricTile extends StatelessWidget {
  const MemberMetricTile(this.label, this.value, {super.key});
  final String label;
  final Object? value;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.all(13),
    decoration: BoxDecoration(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      borderRadius: BorderRadius.circular(10),
    ),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          label,
          style: TextStyle(
            fontSize: 12,
            color: Theme.of(context).colorScheme.onSurfaceVariant,
          ),
        ),
        const SizedBox(height: 5),
        Text(
          '${value ?? '미등록'}',
          style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700),
        ),
      ],
    ),
  );
}

class MemberSectionTitle extends StatelessWidget {
  const MemberSectionTitle(this.title, {super.key});
  final String title;
  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 12, bottom: 12),
    child: Text(
      title,
      style: TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w800,
        color: Theme.of(context).colorScheme.onSurface,
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (공통 구성요소 테마 대응)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
