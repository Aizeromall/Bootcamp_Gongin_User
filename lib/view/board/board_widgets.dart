// 2026-10-28
// 작업자 : 양태건
import 'package:flutter/material.dart';

import '../shared/member_style.dart';

const boardCategories = ['전체', '팀원모집', '매칭신청', '후기', '자유'];
const boardEmoji = {1: '⚽', 4: '🏐', 2: '🏀', 3: '⚾'};
String boardDateLabel(Object? value) {
  final date = DateTime.tryParse('$value');
  if (date == null) return value?.toString() ?? '';
  String two(int value) => value.toString().padLeft(2, '0');
  return '${two(date.month)}/${two(date.day)} ${two(date.hour)}:${two(date.minute)}';
}

class BoardCategoryBadge extends StatelessWidget {
  const BoardCategoryBadge(this.category, {super.key});
  final String category;
  @override
  Widget build(BuildContext context) {
    final color = switch (category) {
      '팀원모집' => MemberStyle.blue,
      '매칭신청' => const Color(0xFFD83222),
      '후기' => MemberStyle.green,
      _ => MemberStyle.muted,
    };
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.10),
        borderRadius: BorderRadius.circular(5),
      ),
      child: Text(
        category,
        style: TextStyle(
          fontSize: 11,
          fontWeight: FontWeight.w800,
          color: color,
        ),
      ),
    );
  }
}

class BoardAvatar extends StatelessWidget {
  const BoardAvatar(this.name, {super.key, this.author = false});
  final String name;
  final bool author;
  @override
  Widget build(BuildContext context) => Container(
    width: author ? 43 : 28,
    height: author ? 43 : 28,
    alignment: Alignment.center,
    decoration: BoxDecoration(
      color: author ? const Color(0xFF416AFF) : const Color(0xFFD9DEE8),
      borderRadius: BorderRadius.circular(author ? 12 : 8),
    ),
    child: Text(
      name.isEmpty ? '회원' : String.fromCharCodes(name.runes.take(2)),
      style: TextStyle(
        fontSize: author ? 14 : 10,
        fontWeight: FontWeight.w800,
        color: author ? Colors.white : MemberStyle.muted,
      ),
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
