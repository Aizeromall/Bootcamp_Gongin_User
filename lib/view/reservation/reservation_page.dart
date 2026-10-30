// 최초 작업자 : 최현준 / 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../../vm/member_features.dart';
import '../payment/payment_page.dart';
import '../shared/api_content.dart';
import '../shared/member_components.dart';
import '../shared/member_style.dart';
import '../shared/ground_price.dart';
import '../shared/ui.dart';

// 수정 일 : 2026-10-28 / 작업자 : 양태건
// 날짜·시간 그리드를 Riverpod 조회로 구성하고 전체 대여와 개인 예약 API를 분리합니다.
class ReservationPage extends ConsumerStatefulWidget {
  const ReservationPage({
    super.key,
    required this.ground,
    this.rental = false,
    this.initialDate,
    this.initialTime,
  });
  final Map<String, dynamic> ground;
  final bool rental;
  final DateTime? initialDate;
  final String? initialTime;
  @override
  ConsumerState<ReservationPage> createState() => _ReservationPageState();
}

class _ReservationPageState extends ConsumerState<ReservationPage> {
  DateTime date = DateUtils.dateOnly(DateTime.now());
  String? time;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    if (widget.initialDate != null) {
      date = DateUtils.dateOnly(widget.initialDate!);
    }
    time = widget.initialTime;
  }

  ApiQuery get query => apiQuery(
    widget.rental
        ? '/ground/reservation/slots/${widget.ground['g_code']}'
        : '/match/reservation/ground/${widget.ground['g_code']}',
    {'r_date': day(date)},
  );
  Future<void> reserve() async {
    if (busy || time == null) return;
    final currentSlots = ref.read(apiDocumentProvider(query));
    if (currentSlots.isLoading ||
        currentSlots.hasError ||
        currentSlots.asData == null ||
        !canReserveTime(currentSlots.asData!.value)) {
      ref.invalidate(apiDocumentProvider(query));
      showMessage(context, '선택한 시간을 다시 확인해 주세요.');
      return;
    }
    final id = ref.read(memberIdProvider);
    setState(() => busy = true);
    try {
      final price = num.tryParse('${widget.ground['g_price']}');
      final estimate = price == null
          ? null
          : widget.rental
          ? price.round()
          : individualGroundPrice(
              widget.ground['g_price'],
              widget.ground['g_num'],
            );
      final completed = await Navigator.push<bool>(
        context,
        MaterialPageRoute<bool>(
          builder: (_) => PaymentPage(
            memberId: id,
            groundName: '${widget.ground['g_name']}',
            expectedAmount: estimate,
            reservationPath: widget.rental
                ? '/ground/reservation'
                : '/match/reservation',
            reservationBody: {
              'c_id_seq': id,
              'g_code': '${widget.ground['g_code']}',
              'r_date': day(date),
              'rs_time': time,
            },
          ),
        ),
      );
      if (mounted && completed == true) Navigator.pop(context, true);
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

  // 수정 일 : 2026-10-30 / 작업자 : 최현준
  // 전달받은 시간은 최신 슬롯 조회 결과에서도 유효할 때만 결제할 수 있습니다.
  bool canReserveTime(Map<String, dynamic> data) {
    if (time == null || data['slots'] is! List) return false;
    final parts = time!.split(':');
    final hour = int.tryParse(parts.first);
    final minute = parts.length > 1 ? int.tryParse(parts[1]) : null;
    if (hour == null ||
        minute == null ||
        hour < 0 ||
        hour > 23 ||
        minute < 0 ||
        minute > 59) {
      return false;
    }
    if (!DateTime(
      date.year,
      date.month,
      date.day,
      hour,
      minute,
    ).isAfter(DateTime.now())) {
      return false;
    }
    for (final slot in data['slots'] as List) {
      if (slot is Map && '${slot['rs_time']}' == time) {
        return widget.rental
            ? slot['is_available'] == true
            : slot['is_full'] != true;
      }
    }
    return false;
  }

  @override
  Widget build(BuildContext context) {
    final slots = ref.watch(apiDocumentProvider(query));
    final canReserve =
        !slots.isLoading &&
        !slots.hasError &&
        slots.asData != null &&
        canReserveTime(slots.asData!.value);
    return Scaffold(
      appBar: AppBar(title: Text(widget.rental ? '구장 전체 대여' : '구장 예약')),
      bottomNavigationBar: SafeArea(
        top: false,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: FilledButton(
            onPressed: busy || !canReserve ? null : reserve,
            child: Text(busy ? '결제 화면 이동 중…' : '결제 수단 선택'),
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
                // 수정 일 : 2026-10-30 / 작업자 : 최현준
                // 구장 주소와 예약 유형을 작은 화면에서도 읽기 쉽게 표시합니다.
                Text(
                  '${widget.ground['g_address']}',
                  style: TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
                Text(
                  '${sports[ref.watch(sportProvider)]} · ${widget.rental ? '전체 대여' : '1인 자리 예약'} · 2시간',
                  style: const TextStyle(
                    fontSize: 13,
                    height: 1.5,
                    color: MemberStyle.blue,
                  ),
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
                          lastDate: DateTime.now().add(
                            const Duration(days: 365),
                          ),
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
                            ? Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHighest
                            : selected
                            ? Theme.of(context).colorScheme.primaryContainer
                            : Theme.of(context)
                                  .colorScheme
                                  .surfaceContainerHigh,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                          side: BorderSide(
                            color: selected
                                ? MemberStyle.blue
                                : MemberStyle.line,
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
                                  color: disabled
                                      ? Theme.of(context).disabledColor
                                      : Theme.of(context).colorScheme.onSurface,
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
            '결제 기록을 저장하면 예약이 함께 확정됩니다. 실제 결제 승인은 진행되지 않습니다.',
            style: TextStyle(
              fontSize: 12,
              color: MemberStyle.muted,
              height: 1.7,
            ),
          ),
        ],
      ),
    );
  }
}
// 최종 수정 일 : 2026-10-28 / 작업자 : 양태건
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (대관 시간 선택 연결)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준 (예약 화면 테마 대비 적용)
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
// 최종 수정 일 : 2026-10-30 / 작업자 : 최현준
