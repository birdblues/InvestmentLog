import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/portfolio_item.dart';
import '../../services/portfolio_service.dart';

class PortfolioCard extends StatefulWidget {
  const PortfolioCard({super.key});

  @override
  State<PortfolioCard> createState() => _PortfolioCardState();
}

class _PortfolioCardState extends State<PortfolioCard> {
  late Future<List<PortfolioItem>> _portfolioFuture;

  @override
  void initState() {
    super.initState();
    _portfolioFuture = PortfolioService().getPortfolioItems();
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<List<PortfolioItem>>(
      future: _portfolioFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Center(child: CircularProgressIndicator());
        } else if (snapshot.hasError) {
          return const Center(child: Text("Error loading portfolio"));
        } else if (!snapshot.hasData || snapshot.data!.isEmpty) {
          return const Center(child: Text("No data"));
        }

        final items = snapshot.data!;

        return Container(
          color: Colors.white,
          padding: const EdgeInsets.symmetric(vertical: 24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // Header
              const Padding(
                padding: EdgeInsets.symmetric(horizontal: 20),
                child: Text(
                  "포트폴리오",
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.bold,
                    color: Colors.black,
                  ),
                ),
              ),
              const SizedBox(height: 24),

              // Pie Chart
              SizedBox(
                height: 200,
                child: PieChart(
                  PieChartData(
                    sectionsSpace: 0,
                    centerSpaceRadius: 50,
                    startDegreeOffset: 90, // Match React startAngle
                    sections: items.map((item) {
                      return PieChartSectionData(
                        color: item.color,
                        value: item.value,
                        title: '', // Hide title on chart
                        radius: 40,
                        showTitle: false,
                      );
                    }).toList(),
                  ),
                ),
              ),

              const SizedBox(height: 32),

              // Legend
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  children: items
                      .map((item) => _buildLegendItem(item))
                      .toList(),
                ),
              ),

              const SizedBox(height: 32),

              // Button
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 20),
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

  Widget _buildLegendItem(PortfolioItem item) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Row(
            children: [
              Container(
                width: 12,
                height: 12,
                decoration: BoxDecoration(
                  color: item.color,
                  borderRadius: BorderRadius.circular(4),
                ),
              ),
              const SizedBox(width: 8),
              Text(
                item.name,
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w500,
                  color: Colors.black,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                "${item.value.toStringAsFixed(1)}%",
                style: const TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w300,
                  color: Color(0xFF9CA3AF),
                ),
              ),
            ],
          ),
          Text(
            "${_formatCurrency(item.amount)}원",
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.bold,
              color: Colors.black,
            ),
          ),
        ],
      ),
    );
  }

  String _formatCurrency(int amount) {
    final formatter = NumberFormat.currency(locale: 'ko_KR', symbol: '', decimalDigits: 0);
    return formatter.format(amount);
  }
}
