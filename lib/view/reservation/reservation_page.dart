// 작업자 : 최현준
// 최초 작업 일 : 2026-10-24
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../vm/member_state.dart';
import '../payment/payment_page.dart';
import '../shared/ui.dart';

class ReservationPage extends ConsumerStatefulWidget {
  const ReservationPage({super.key, required this.ground});
  final Map<String, dynamic> ground;
  @override
  ConsumerState<ReservationPage> createState() => _ReservationPageState();
}

class _ReservationPageState extends ConsumerState<ReservationPage> {
  DateTime date = DateTime.now();
  late Future<Map<String, dynamic>> availability;
  String? time;
  bool busy = false;
  @override
  void initState() {
    super.initState();
    load();
  }

  void load() {
    time = null;
    availability = ref
        .read(memberApiProvider)
        .request(
          '/match/reservation/ground/${widget.ground['g_code']}',
          query: {'r_date': day(date)},
        );
  }

  Future<void> reserve() async {
    setState(() => busy = true);
    // 회원 FK와 선택 종목은 로그인 상태에서 가져와 임의 입력을 방지합니다.
    final memberId = ref.read(memberIdProvider);
    try {
      final result = await ref
          .read(memberApiProvider)
          .request(
            '/match/reservation',
            body: {
              'c_id_seq': memberId,
              'g_code': '${widget.ground['g_code']}',
              'r_date': day(date),
              'rs_time': time,
            },
          );
      if (!mounted) {
        return;
      }
      Navigator.pushReplacement(
        context,
        MaterialPageRoute<void>(
          builder: (_) => PaymentPage(
            rSeq: result['r_seq'] as int,
            memberId: memberId,
            groundName: '${widget.ground['g_name']}',
          ),
        ),
      );
    } catch (error) {
      if (mounted) {
        showMessage(context, error);
        setState(load);
      }
    } finally {
      if (mounted) {
        setState(() => busy = false);
      }
    }
  }

  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(title: const Text('구장 예약')),
    body: pageContent([
      heading('${widget.ground['g_name']}', '${widget.ground['g_address']}'),
      Text('예약 종목: ${sports[ref.watch(sportProvider)]} · 1회 2시간'),
      ListTile(
        title: Text(day(date)),
        trailing: const Icon(Icons.calendar_month),
        onTap: busy
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
                    load();
                  });
                }
              },
      ),
      FutureBuilder<Map<String, dynamic>>(
        future: availability,
        builder: (context, snapshot) {
          if (snapshot.hasError) {
            return Column(
              children: [
                Text('${snapshot.error}'),
                TextButton(
                  onPressed: () => setState(load),
                  child: const Text('다시 시도'),
                ),
              ],
            );
          }
          if (!snapshot.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          return Wrap(
            spacing: 12,
            runSpacing: 12,
            children: (snapshot.data!['slots'] as List).map((slot) {
              final start = '${slot['rs_time']}';
              final hour = int.parse(start.split(':').first);
              final expired = !DateTime(
                date.year,
                date.month,
                date.day,
                hour,
              ).isAfter(DateTime.now());
              final disabled = busy || slot['is_full'] == true || expired;
              return ChoiceChip(
                label: Text(
                  '$start ~ ${slot['re_time']}\n${expired ? '선택 불가' : '${slot['remaining_capacity']}자리 남음'}',
                ),
                selected: time == start,
                onSelected: disabled
                    ? null
                    : (_) => setState(() => time = start),
              );
            }).toList(),
          );
        },
      ),
      const SizedBox(height: 24),
      const Text(
        '예약 생성 후 결제 수단을 선택합니다. 결제를 완료하지 못한 예약은 내 예약·결제에서 이어서 진행할 수 있습니다.',
      ),
      const SizedBox(height: 16),
      FilledButton(
        onPressed: busy || time == null ? null : reserve,
        child: Text(busy ? '예약 중…' : '예약하고 결제 선택'),
      ),
    ]),
  );
}
// 최종 수정 일 : 2026-10-24
