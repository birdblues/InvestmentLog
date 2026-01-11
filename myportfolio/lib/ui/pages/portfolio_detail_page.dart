import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';
import '../../models/portfolio_item.dart';
import '../../services/portfolio_service.dart';
import '../components/asset_card.dart';
import '../components/sensitivity_card.dart';

class PortfolioDetailPage extends StatefulWidget {
  const PortfolioDetailPage({super.key});

  @override
  State<PortfolioDetailPage> createState() => _PortfolioDetailPageState();
}

class _PortfolioDetailPageState extends State<PortfolioDetailPage> {
  late Future<List<PortfolioItem>> _portfolioFuture;
  late Future<List<Map<String, dynamic>>> _sensitivityFuture;
  late Future<Map<String, List<Map<String, String>>>> _detailsFuture;
  late Future<List<PortfolioItem>> _currencyFuture;
  
  @override
  void initState() {
    super.initState();
    _portfolioFuture = PortfolioService().getPortfolioItems();
    _sensitivityFuture = PortfolioService().getFactorSensitivity();
    _detailsFuture = PortfolioService().getPortfolioDetails();
    _currencyFuture = PortfolioService().getCurrencyExposure();
  }

  String _formatCurrency(int amount) {
    final formatter = NumberFormat.currency(locale: 'ko_KR', symbol: '', decimalDigits: 0);
    return "${formatter.format(amount)}원";
  }

  PortfolioItem? _findItem(List<PortfolioItem> items, String name) {
    try {
      return items.firstWhere((element) => element.name == name);
    } catch (_) {
      return null;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF9FAFB),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.chevron_left, color: Colors.black, size: 28),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          "포트폴리오",
          style: TextStyle(
            color: Colors.black,
            fontSize: 18,
            fontWeight: FontWeight.w500,
          ),
        ),
        centerTitle: true,
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(1.0),
          child: Container(
            color: Colors.grey[200],
            height: 1.0,
          ),
        ),
      ),
      body: FutureBuilder<List<dynamic>>(
        future: Future.wait([_portfolioFuture, _sensitivityFuture, _detailsFuture, _currencyFuture]),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          } else if (snapshot.hasError) {
            return const Center(child: Text("Error loading portfolio"));
          } else if (!snapshot.hasData || (snapshot.data![0] as List).isEmpty) {
            return const Center(child: Text("No data"));
          }

          final items = snapshot.data![0] as List<PortfolioItem>;
          final sensitivityData = snapshot.data![1] as List<Map<String, dynamic>>;
          final details = snapshot.data![2] as Map<String, List<Map<String, String>>>;
          final currencyItems = snapshot.data![3] as List<PortfolioItem>;

          // Find specific items for sections
          final stockItem = _findItem(items, '주식형');
          final bondItem = _findItem(items, '채권형');
          final altItem = _findItem(items, '대체투자');
          final cashItem = _findItem(items, '현금성 자산');

          return SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // --- Chart Section (Allocation) ---
                Container(
                  margin: const EdgeInsets.only(bottom: 8),
                  padding: const EdgeInsets.all(24),
                  color: Colors.white,
                  child: Row(
                    children: [
                      SizedBox(
                        width: 130,
                        height: 130,
                        child: PieChart(
                          PieChartData(
                            sectionsSpace: 0,
                            centerSpaceRadius: 40,
                            startDegreeOffset: -90, 
                            sections: items.map((item) {
                              return PieChartSectionData(
                                color: item.color,
                                value: item.value,
                                title: '',
                                radius: 20,
                                showTitle: false,
                              );
                            }).toList(),
                          ),
                        ),
                      ),
                      const SizedBox(width: 32),
                      Expanded(
                        child: Column(
                          children: items.map((item) {
                            return Padding(
                              padding: const EdgeInsets.only(bottom: 8),
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
                                          borderRadius: BorderRadius.circular(2),
                                        ),
                                      ),
                                      const SizedBox(width: 8),
                                      Text(
                                        item.name,
                                        style: const TextStyle(fontSize: 14),
                                      ),
                                    ],
                                  ),
                                  Text(
                                    "${item.value.toStringAsFixed(1)}%",
                                    style: const TextStyle(
                                      fontSize: 14,
                                      fontWeight: FontWeight.w500,
                                    ),
                                  ),
                                ],
                              ),
                            );
                          }).toList(),
                        ),
                      ),
                    ],
                  ),
                ),

                // --- Currency Exposure Section ---
                if (currencyItems.isNotEmpty) ...[
                  const Padding(
                    padding: EdgeInsets.symmetric(horizontal: 24, vertical: 12),
                    child: Text(
                      "통화 노출",
                      style: TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.bold,
                        color: Colors.black,
                      ),
                    ),
                  ),
                  Container(
                    margin: const EdgeInsets.only(bottom: 16),
                    padding: const EdgeInsets.all(24),
                    color: Colors.white,
                    child: Row(
                      children: [
                        SizedBox(
                          width: 130,
                          height: 130,
                          child: PieChart(
                            PieChartData(
                              sectionsSpace: 0,
                              centerSpaceRadius: 40,
                              startDegreeOffset: -90, 
                              sections: currencyItems.map((item) {
                                return PieChartSectionData(
                                  color: item.color,
                                  value: item.value,
                                  title: '',
                                  radius: 20,
                                  showTitle: false,
                                );
                              }).toList(),
                            ),
                          ),
                        ),
                        const SizedBox(width: 32),
                        Expanded(
                          child: Column(
                            children: currencyItems.map((item) {
                              return Padding(
                                padding: const EdgeInsets.only(bottom: 8),
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
                                            borderRadius: BorderRadius.circular(2),
                                          ),
                                        ),
                                        const SizedBox(width: 8),
                                        Text(
                                          item.name,
                                          style: const TextStyle(fontSize: 14),
                                        ),
                                      ],
                                    ),
                                    Text(
                                      "${item.value.toStringAsFixed(1)}%",
                                      style: const TextStyle(
                                        fontSize: 14,
                                        fontWeight: FontWeight.w500,
                                      ),
                                    ),
                                  ],
                                ),
                              );
                            }).toList(),
                          ),
                        ),
                      ],
                    ),
                  ),
                ],

                // --- Sensitivity Card (Top) ---
                if (sensitivityData.isNotEmpty)
                  SensitivityCard(data: sensitivityData),
                const SizedBox(height: 16),
                const SizedBox(height: 16),

                // --- Sections ---

                // 1. Stock

                if (stockItem != null)
                  _buildSection(
                    id: 'stock',
                    title: stockItem.name,
                    percentage: "${stockItem.value.toStringAsFixed(1)}%",
                    percentageColor: Colors.blue,
                    amount: _formatCurrency(stockItem.amount),
                    assets: details['stock'] ?? [],
                  ),

                // 2. Bond
                if (bondItem != null)
                  _buildSection(
                    id: 'bond',
                    title: bondItem.name,
                    percentage: "${bondItem.value.toStringAsFixed(1)}%",
                    percentageColor: Colors.blue,
                    amount: _formatCurrency(bondItem.amount),
                    assets: details['bond'] ?? [],
                  ),

                // 3. Alternative
                if (altItem != null)
                  _buildSection(
                    id: 'alternative',
                    title: altItem.name,
                    percentage: "${altItem.value.toStringAsFixed(1)}%",
                    percentageColor: Colors.orange,
                    amount: _formatCurrency(altItem.amount),
                    assets: details['alternative'] ?? [],
                  ),

                // 4. Cash
                if (cashItem != null)
                  _buildSection(
                    id: 'cash',
                    title: cashItem.name,
                    percentage: "${cashItem.value.toStringAsFixed(1)}%",
                    percentageColor: Colors.purple,
                    amount: _formatCurrency(cashItem.amount),
                    assets: details['cash'] ?? [],
                    isLast: true,
                  ),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSection({
    required String id,
    required String title,
    required String percentage,
    required Color percentageColor,
    required String amount,
    required List<Map<String, String>> assets,
    List<Map<String, dynamic>>? sensitivityData,
    bool isLast = false,
  }) {
    return Column(
      children: [
        Container(
          color: Colors.white,
          margin: const EdgeInsets.only(bottom: 2),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.baseline,
              textBaseline: TextBaseline.alphabetic,
              children: [
                Text(
                  title,
                  style: const TextStyle(fontSize: 18),
                ),
                const SizedBox(width: 8),
                Text(
                  percentage,
                  style: TextStyle(
                    fontSize: 18,
                    color: percentageColor,
                  ),
                ),
                const Spacer(),
                Text(
                  amount,
                  style: const TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ),
        Padding(
          padding: EdgeInsets.fromLTRB(16, 4, 16, isLast ? 32 : 16),
          child: Column(
            children: [
              ...assets.map((asset) => AssetCard(
                    code: asset['code']!,
                    name: asset['name']!,
                    percentage: asset['percentage']!,
                    shares: asset['shares']!,
                    profitRate: asset['profitRate']!,
                    profitAmount: asset['profitAmount']!,
                    currentPrice: asset['currentPrice']!,
                    totalValue: asset['totalValue']!,
                  )),
              if (sensitivityData != null)
                SensitivityCard(data: sensitivityData),
            ],
          ),
        ),
      ],
    );
  }
}
