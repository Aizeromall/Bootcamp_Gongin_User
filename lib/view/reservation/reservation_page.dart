// 최초 작업자 : 최현준 / 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../payment/payment_page.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 날짜·시간 그리드를 Riverpod 조회로 구성하고 전체 대여와 개인 예약 API를 분리합니다.
class ReservationPage extends ConsumerStatefulWidget {
  const ReservationPage({super.key, required this.ground, this.rental = false});
  final Map<String, dynamic> ground;
  final bool rental;
  @override
  ConsumerState<ReservationPage> createState() => _ReservationPageState();
}

class _ReservationPageState extends ConsumerState<ReservationPage> {
  DateTime date = DateUtils.dateOnly(DateTime.now());
  String? time;
  bool busy = false;
  ApiQuery get query => apiQuery(
    widget.rental
        ? '/ground/reservation/slots/${widget.ground['g_code']}'
        : '/match/reservation/ground/${widget.ground['g_code']}',
    {'r_date': day(date)},
  );
  Future<void> reserve() async {
    if (busy || time == null) return;
    setState(() => busy = true);
    final id = ref.read(memberIdProvider);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            widget.rental ? '/ground/reservation' : '/match/reservation',
            body: {
              'c_id_seq': id,
              'g_code': '${widget.ground['g_code']}',
              'r_date': day(date),
              'rs_time': time,
            },
          );
      if (!mounted) return;
      final price = num.tryParse('${widget.ground['g_price']}');
      final capacity = num.tryParse('${widget.ground['g_num']}');
      final estimate = price == null
          ? null
          : widget.rental
          ? price.round()
          : capacity != null && capacity > 0
          ? (price / capacity).round()
          : null;
      Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(
          builder: (_) => PaymentPage(
            rSeq: result['r_seq'] as int,
            memberId: id,
            groundName: '${widget.ground['g_name']}',
            expectedAmount: estimate,
          ),
        ),
      );
    } catch (error) {
      if (mounted) {
        showMessage(context, error);
        ref.invalidate(apiDocumentProvider(query));
        setState(() => time = null);
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: Text(widget.rental ? '구장 전체 대여' : '구장 예약')),
    bottomNavigationBar: SafeArea(
      top: false,
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: FilledButton(
          onPressed: busy || time == null ? null : reserve,
          child: Text(busy ? '예약 중…' : '예약하고 결제 선택'),
        ),
      ),
    ),
    body: ListView(
      padding: const EdgeInsets.all(18),
      children: [
        MemberPanel(
          color: Colors.white,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                '${widget.ground['g_name']}',
                style: const TextStyle(
                  fontWeight: FontWeight.w800,
                  fontSize: 19,
                ),
              ),
              const SizedBox(height: 6),
              Text(
                '${widget.ground['g_address']}',
                style: const TextStyle(fontSize: 12, color: MemberStyle.muted),
              ),
              Text(
                '${sports[ref.watch(sportProvider)]} · ${widget.rental ? '전체 대여' : '1인 자리 예약'} · 2시간',
                style: const TextStyle(fontSize: 12, color: MemberStyle.blue),
              ),
            ],
          ),
        ),
        Row(
          children: [
            Expanded(
              child: Text(
                day(date),
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w800,
                ),
              ),
            ),
            IconButton(
              tooltip: '날짜 선택',
              onPressed: busy
                  ? null
                  : () async {
                      final chosen = await showDatePicker(
                        context: context,
                        initialDate: date,
                        firstDate: DateUtils.dateOnly(DateTime.now()),
                        lastDate: DateTime.now().add(const Duration(days: 365)),
                      );
                      if (chosen != null && mounted) {
                        setState(() {
                          date = chosen;
                          time = null;
                        });
                      }
                    },
              icon: const Icon(Icons.calendar_month),
            ),
          ],
        ),
        SizedBox(
          height: 72,
          child: ListView.separated(
            scrollDirection: Axis.horizontal,
            itemCount: 7,
            separatorBuilder: (_, _) => const SizedBox(width: 7),
            itemBuilder: (context, index) {
              final option = DateUtils.dateOnly(
                DateTime.now().add(Duration(days: index)),
              );
              return ChoiceChip(
                label: Text(
                  '${['월', '화', '수', '목', '금', '토', '일'][option.weekday - 1]}\n${option.day}',
                  textAlign: TextAlign.center,
                ),
                selected: DateUtils.isSameDay(option, date),
                showCheckmark: false,
                onSelected: busy
                    ? null
                    : (_) => setState(() {
                        date = option;
                        time = null;
                      }),
              );
            },
          ),
        ),
        const SizedBox(height: 12),
        ApiContent(
          query: query,
          builder: (data) => GridView.count(
            crossAxisCount: 3,
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisSpacing: 8,
            mainAxisSpacing: 10,
            childAspectRatio: 1.45,
            children: [
              for (final raw in data['slots'] as List)
                Builder(
                  builder: (context) {
                    final slot = Map<String, dynamic>.from(raw as Map);
                    final start = '${slot['rs_time']}';
                    final parts = start.split(':');
                    final instant = DateTime(
                      date.year,
                      date.month,
                      date.day,
                      int.parse(parts.first),
                      int.parse(parts[1]),
                    );
                    final expired = !instant.isAfter(DateTime.now());
                    final disabled =
                        busy ||
                        expired ||
                        (widget.rental
                            ? slot['is_available'] != true
                            : slot['is_full'] == true);
                    final selected = time == start;
                    return Material(
                      color: disabled
                          ? MemberStyle.surface
                          : selected
                          ? const Color(0xFFEAF1FF)
                          : Colors.white,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                        side: BorderSide(
                          color: selected ? MemberStyle.blue : MemberStyle.line,
                        ),
                      ),
                      clipBehavior: Clip.antiAlias,
                      child: InkWell(
                        onTap: disabled
                            ? null
                            : () => setState(() => time = start),
                        child: Column(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: [
                            Text(
                              start,
                              style: TextStyle(
                                fontWeight: FontWeight.w700,
                                color: disabled ? Colors.grey : MemberStyle.ink,
                              ),
                            ),
                            Text(
                              expired
                                  ? '선택 불가'
                                  : disabled
                                  ? '예약 불가'
                                  : widget.rental
                                  ? '대여 가능'
                                  : '${slot['remaining_capacity']}자리',
                              style: TextStyle(
                                fontSize: 11,
                                color: selected
                                    ? MemberStyle.blue
                                    : MemberStyle.muted,
                              ),
                            ),
                          ],
                        ),
                      ),
                    );
                  },
                ),
            ],
          ),
        ),
        const SizedBox(height: 20),
        const Text(
          '예약 후 결제 내역을 저장할 수 있습니다. 결제를 미룬 예약은 내 예약에서 이어서 진행하세요.',
          style: TextStyle(fontSize: 12, color: MemberStyle.muted, height: 1.7),
        ),
      ],
    ),
  );
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
