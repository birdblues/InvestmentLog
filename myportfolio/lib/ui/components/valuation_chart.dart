import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import '../../models/valuation_item.dart';

class ValuationChart extends StatefulWidget {
  final List<ValuationItem>? data;
  const ValuationChart({super.key, this.data});

  @override
  State<ValuationChart> createState() => _ValuationChartState();
}

class _ValuationChartState extends State<ValuationChart> {
  String _viewMode = 'won'; // 'won' or 'percent'

  @override
  Widget build(BuildContext context) {
    if (widget.data == null || widget.data!.isEmpty) {
      return const SizedBox.shrink(); // Or a placeholder
    }
    final data = widget.data!;

    // Calculate min/max for Y axis scale
    double minY = double.infinity;
    double maxY = double.negativeInfinity;

    // For indicators (Value line only)
    int minIndex = 0;
    int maxIndex = 0;
    double minVal = double.infinity;
    double maxVal = double.negativeInfinity;

    for (int i = 0; i < data.length; i++) {
      final item = data[i];

      // Y-Axis Scaling (All lines)
      if (item.value < minY) minY = item.value;
      if (item.principal < minY) minY = item.principal;
      if (item.value > maxY) maxY = item.value;
      if (item.principal > maxY) maxY = item.principal;

      // Indicators (Value line only)
      if (item.value < minVal) {
        minVal = item.value;
        minIndex = i;
      }
      if (item.value > maxVal) {
        maxVal = item.value;
        maxIndex = i;
      }
    }

    final principalBarData = LineChartBarData(
      spots: data.asMap().entries.map((e) {
        return FlSpot(e.key.toDouble(), e.value.principal);
      }).toList(),
      isCurved: false,
      isStepLineChart: true,
      color: const Color(0xFF6B7280),
      barWidth: 2,
      isStrokeCapRound: true,
      dotData: FlDotData(show: false),
      dashArray: [4, 4],
      belowBarData: BarAreaData(show: false),
    );

    final valueBarData = LineChartBarData(
      spots: data.asMap().entries.map((e) {
        return FlSpot(e.key.toDouble(), e.value.value);
      }).toList(),
      isCurved: true,
      color: const Color(0xFF1B2B4B),
      barWidth: 2,
      isStrokeCapRound: true,
      dotData: FlDotData(show: false), // Default hidden, overridden in Stack
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
    );

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
            child: LayoutBuilder(
              builder: (context, constraints) {
                final width = constraints.maxWidth;
                final totalHeight = constraints.maxHeight;
                // Reserve space for bottom titles strictly
                const double titleHeight = 22.0; 
                final chartHeight = totalHeight - titleHeight;
                
                // Increase padding to make space for labels above/below
                double padding = (maxY - minY) * 0.5;
                
                // Chart data range
                final rangeY = (maxY + padding) - (minY - padding);
                final scaleMinY = minY - padding;

                double getPixelY(double val) {
                  if (rangeY == 0) return titleHeight + chartHeight / 2;
                  final normalized = (val - scaleMinY) / rangeY;
                  return titleHeight + (normalized * chartHeight);
                }

                final xStep = data.length > 1 ? width / (data.length - 1) : 0.0;

                // Value Bar Data with specific dots enabled
                final valueBarDataWithDots = valueBarData.copyWith(
                  dotData: FlDotData(
                    show: true,
                    checkToShowDot: (spot, barData) {
                      return spot.x == minIndex || spot.x == maxIndex;
                    },
                    getDotPainter: (spot, percent, barData, index) {
                      if (spot.x == maxIndex) {
                         return FlDotCirclePainter(
                          radius: 4,
                          color: Colors.red,
                          strokeColor: Colors.white,
                          strokeWidth: 2,
                        );
                      } else {
                         return FlDotCirclePainter(
                          radius: 4,
                          color: Colors.blue,
                          strokeColor: Colors.white,
                          strokeWidth: 2,
                        );
                      }
                    },
                  ),
                );

                // Helper for label X position (Clamped to screen)
                double getClampedLabelLeft(double xPosInPixels) {
                  double desiredLeft = 20 + xPosInPixels - 50;
                  if (desiredLeft < 0) desiredLeft = 0;
                  if (desiredLeft + 100 > width) desiredLeft = width - 100;
                  return desiredLeft;
                }

                final maxItem = data[maxIndex];
                final maxPxX = maxIndex * xStep;
                final maxPxY = getPixelY(maxItem.value);

                final minItem = data[minIndex];
                final minPxX = minIndex * xStep;
                final minPxY = getPixelY(minItem.value);

                return Stack(
                  clipBehavior: Clip.none,
                  children: [
                    // 1. The Chart
                    Padding(
                       padding: const EdgeInsets.symmetric(horizontal: 20),
                       child: LineChart(
                        LineChartData(
                          gridData: FlGridData(show: false),
                          showingTooltipIndicators: [], 
                          titlesData: FlTitlesData(
                            show: true,
                            rightTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                            topTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                            leftTitles: AxisTitles(sideTitles: SideTitles(showTitles: false)),
                            bottomTitles: AxisTitles(
                              sideTitles: SideTitles(
                                showTitles: true,
                                reservedSize: titleHeight,
                                interval: 1,
                                getTitlesWidget: (value, meta) {
                                  int index = value.toInt();
                                  if (index < 0 || index >= data.length) return const SizedBox.shrink();

                                  if (index == 0 || index == data.length - 1) {
                                    final dateStr = data[index].date.substring(5).replaceAll('-', '.');
                                    return SideTitleWidget(
                                      meta: meta,
                                      space: 8.0,
                                      fitInside: SideTitleFitInsideData.fromTitleMeta(meta, distanceFromEdge: 0),
                                      child: Text(
                                        dateStr,
                                        style: const TextStyle(color: Color(0xFF9CA3AF), fontSize: 12),
                                        textAlign: index == 0 ? TextAlign.left : TextAlign.right,
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
                          minY: scaleMinY,
                          maxY: maxY + padding,
                          lineBarsData: [
                            principalBarData,
                            valueBarDataWithDots,
                          ],
                          lineTouchData: LineTouchData(enabled: false),
                        ),
                      ),
                    ),
                    
                    // 2. Max Label (Red) - Above
                    Positioned(
                      left: getClampedLabelLeft(maxPxX),
                      bottom: maxPxY + 10,
                      width: 100,
                      child: Text(
                        "${_formatCurrency(maxItem.value.toInt())}원",
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.red, 
                          fontWeight: FontWeight.bold, 
                          fontSize: 12
                        ),
                      ),
                    ),

                    // 3. Min Label (Blue) - Below
                    Positioned(
                      left: getClampedLabelLeft(minPxX),
                      bottom: minPxY - 24, // below dot
                      width: 100,
                      child: Text(
                        "${_formatCurrency(minItem.value.toInt())}원",
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: Colors.blue, 
                          fontWeight: FontWeight.bold, 
                          fontSize: 12
                        ),
                      ),
                    ),
                  ],
                );
              },
            ),
          ),
          
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
