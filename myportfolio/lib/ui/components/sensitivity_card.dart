import 'package:fl_chart/fl_chart.dart';
import 'package:myportfolio/ui/pages/sensitivity_detail_page.dart';
import 'package:flutter/material.dart';

class SensitivityCard extends StatelessWidget {
  final List<Map<String, dynamic>> data;

  const SensitivityCard({super.key, required this.data});

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(24),
      color: Colors.white,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                "민감도 분석",
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                ),
              ),
              GestureDetector(
                onTap: () {
                  Navigator.push(
                    context,
                    MaterialPageRoute(
                      builder: (context) => const SensitivityDetailPage(),
                    ),
                  );
                },
                child: Icon(Icons.chevron_right, color: Colors.grey[400], size: 20),
              ),
            ],
          ),
          const SizedBox(height: 16),
          SizedBox(
            height: 200,
            child: RadarChart(
              RadarChartData(
                radarBackgroundColor: Colors.transparent,
                borderData: FlBorderData(show: false),
                radarBorderData: const BorderSide(color: Colors.transparent),
                titlePositionPercentageOffset: 0.2,
                titleTextStyle: const TextStyle(color: Colors.grey, fontSize: 12),
                tickCount: 1,
                ticksTextStyle: const TextStyle(color: Colors.transparent, fontSize: 10),
                tickBorderData: const BorderSide(color: Colors.transparent),
                gridBorderData: BorderSide(color: Colors.grey[300]!, width: 1),
                radarShape: RadarShape.polygon,
                getTitle: (index, angle) {
                  return RadarChartTitle(
                    text: data[index]['factor'] as String,
                    angle: angle,
                  );
                },
                dataSets: [
                  RadarDataSet(
                    fillColor: const Color(0xFF5B8EFF).withValues(alpha: 0.3),
                    borderColor: const Color(0xFF5B8EFF),
                    entryRadius: 2,
                    dataEntries: data
                        .map((e) => RadarEntry(value: (e['value'] as num).toDouble()))
                        .toList(),
                    borderWidth: 2,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceAround,
            children: data.map((item) {
              return Column(
                children: [
                  Text(
                    item['factor'] as String,
                    style: TextStyle(
                      color: Colors.grey[400],
                      fontSize: 12,
                    ),
                  ),
                  const SizedBox(height: 4),
                  Text(
                    (item['value'] as num).toStringAsFixed(2),
                    style: const TextStyle(
                      fontWeight: FontWeight.w500,
                      fontSize: 14,
                    ),
                  ),
                ],
              );
            }).toList(),
          ),
        ],
      ),
    );
  }
}
