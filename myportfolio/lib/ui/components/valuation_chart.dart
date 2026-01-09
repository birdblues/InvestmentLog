import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../../models/valuation_item.dart';
import '../../services/portfolio_service.dart';

class ValuationChart extends StatefulWidget {
  const ValuationChart({super.key});

  @override
  State<ValuationChart> createState() => _ValuationChartState();
}

class _ValuationChartState extends State<ValuationChart> {
  late Future<List<ValuationItem>> _valuationFuture;
  String _viewMode = 'won'; // 'won' or 'percent'

  @override
  void initState() {
    super.initState();
    _valuationFuture = PortfolioService().getValuationHistory();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<ValuationItem>>(
      future: _valuationFuture,
      builder: (context, snapshot) {
        if (!snapshot.hasData) {
          return const SizedBox(
            height: 300,
            child: Center(child: CircularProgressIndicator()),
          );
        }

        final data = snapshot.data!;
        if (data.isEmpty) return const SizedBox.shrink();

        // Calculate min/max for Y axis including Principal
        double minY = double.infinity;
        double maxY = double.negativeInfinity;

        for (var item in data) {
          if (item.value < minY) minY = item.value;
          if (item.principal < minY) minY = item.principal;
          if (item.value > maxY) maxY = item.value;
          if (item.principal > maxY) maxY = item.principal;
        }

        double padding = (maxY - minY) * 0.2;

        return Container(
          color: Colors.white,
          padding: const EdgeInsets.only(top: 24, bottom: 40),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    const Text(
                      "평가금액",
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.black,
                      ),
                    ),
                    Container(
                      decoration: BoxDecoration(
                        color: Colors.grey[100],
                        borderRadius: BorderRadius.circular(20),
                      ),
                      padding: const EdgeInsets.all(4),
                      child: Row(
                        children: [
                          _buildModeButton('₩', 'won'),
                          _buildModeButton('%', 'percent'),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 32),

              // Chart
              SizedBox(
                height: 256,
                child: Padding(
                  padding: const EdgeInsets.symmetric(horizontal: 20),
                  child: LineChart(
                    LineChartData(
                      gridData: FlGridData(show: false),
                      titlesData: FlTitlesData(
                        show: true,
                        rightTitles: AxisTitles(
                          sideTitles: SideTitles(showTitles: false),
                        ),
                        topTitles: AxisTitles(
                          sideTitles: SideTitles(showTitles: false),
                        ),
                        leftTitles: AxisTitles(
                          sideTitles: SideTitles(showTitles: false),
                        ),
                        bottomTitles: AxisTitles(
                          sideTitles: SideTitles(
                            showTitles: true,
                            interval: 1, // Check every index
                            getTitlesWidget: (value, meta) {
                              int index = value.toInt();
                              if (index < 0 || index >= data.length)
                                return const SizedBox.shrink();

                              // Show only first and last
                              if (index == 0 || index == data.length - 1) {
                                final dateStr = data[index].date
                                    .substring(5)
                                    .replaceAll('-', '.');

                                // To align text technically within the chart's bounds for the axis,
                                // FlChart's SideTitleWidget can be used, or we just return text.
                                // For strictly keeping inside bounds, we rely on the parent padding
                                // and text alignment.
                                // Since we added padding to the chart container, left alignment for first
                                // and right alignment for last should generally work well.

                                return SideTitleWidget(
                                  meta: meta,
                                  space: 8.0, // Top margin
                                  fitInside:
                                      SideTitleFitInsideData.fromTitleMeta(
                                        meta,
                                        distanceFromEdge: 0,
                                      ),
                                  child: Text(
                                    dateStr,
                                    style: const TextStyle(
                                      color: Color(0xFF9CA3AF),
                                      fontSize: 12,
                                    ),
                                    textAlign: index == 0
                                        ? TextAlign.left
                                        : TextAlign.right,
                                  ),
                                );
                              }
                              return const SizedBox.shrink();
                            },
                          ),
                        ),
                      ),
                      borderData: FlBorderData(show: false),
                      minX: 0,
                      maxX: (data.length - 1).toDouble(),
                      minY: minY - padding,
                      maxY: maxY + padding,
                      lineBarsData: [
                        // Principal Step Line (Dashed)
                        LineChartBarData(
                          spots: data.asMap().entries.map((e) {
                            return FlSpot(e.key.toDouble(), e.value.principal);
                          }).toList(),
                          isCurved: false,
                          color: const Color(0xFF6B7280),
                          barWidth: 2,
                          isStrokeCapRound: true,
                          dotData: FlDotData(show: false),
                          dashArray: [4, 4], // Dashed line
                          belowBarData: BarAreaData(show: false),
                        ),

                        // Value Line (Area)
                        LineChartBarData(
                          spots: data.asMap().entries.map((e) {
                            return FlSpot(e.key.toDouble(), e.value.value);
                          }).toList(),
                          isCurved: true,
                          color: const Color(0xFF1B2B4B),
                          barWidth: 2,
                          isStrokeCapRound: true,
                          dotData: FlDotData(show: false),
                          belowBarData: BarAreaData(
                            show: true,
                            gradient: LinearGradient(
                              begin: Alignment.topCenter,
                              end: Alignment.bottomCenter,
                              colors: [
                                const Color(0xFF1B2B4B).withValues(alpha: 0.1),
                                const Color(0xFF1B2B4B).withValues(alpha: 0.0),
                              ],
                            ),
                          ),
                        ),
                      ],
                      lineTouchData: LineTouchData(
                        touchTooltipData: LineTouchTooltipData(
                          getTooltipItems: (touchedSpots) {
                            return touchedSpots.map((touchedSpot) {
                              // Only show tooltip for the value line (index 1)
                              if (touchedSpot.barIndex != 1) return null;

                              final val = touchedSpot.y;
                              return LineTooltipItem(
                                "${_formatCurrency(val.toInt())}원",
                                const TextStyle(
                                  color: Colors.white,
                                  fontWeight: FontWeight.bold,
                                ),
                              );
                            }).toList();
                          },
                          // Default styling is close enough: darkness
                        ),
                      ),
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 16),

              // Detail Button
              Padding(
                padding: const EdgeInsets.symmetric(
                  horizontal: 20,
                  vertical: 16,
                ),
                child: SizedBox(
                  width: double.infinity,
                  child: ElevatedButton(
                    onPressed: () {},
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.grey[100],
                      foregroundColor: const Color(0xFF4B5563),
                      elevation: 0,
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      textStyle: const TextStyle(fontWeight: FontWeight.w600),
                    ),
                    child: const Text("자세히 보기"),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _buildModeButton(String text, String mode) {
    bool isSelected = _viewMode == mode;
    return GestureDetector(
      onTap: () {
        setState(() {
          _viewMode = mode;
        });
      },
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        decoration: BoxDecoration(
          color: isSelected
              ? const Color(0xFF64748B)
              : Colors.transparent, // Slate-500 ish
          borderRadius: BorderRadius.circular(16),
          boxShadow: isSelected
              ? [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.1),
                    blurRadius: 2,
                    offset: const Offset(0, 1),
                  ),
                ]
              : null,
        ),
        child: Text(
          text,
          style: TextStyle(
            color: isSelected ? Colors.white : const Color(0xFF9CA3AF),
            fontSize: 14,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  String _formatCurrency(int amount) {
    return amount.toString().replaceAllMapped(
      RegExp(r'(\d{1,3})(?=(\d{3})+(?!\d))'),
      (Match m) => '${m[1]},',
    );
  }
}
