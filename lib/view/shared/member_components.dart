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
            color: MemberStyle.ink,
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
      color: color,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: const BorderSide(color: MemberStyle.line),
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
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 7),
    child: Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        SizedBox(
          width: 88,
          child: Text(
            label,
            style: const TextStyle(fontSize: 12, color: MemberStyle.muted),
          ),
        ),
        Expanded(
          child: Text(
            '${value ?? '미등록'}',
            style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
          ),
        ),
      ],
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
