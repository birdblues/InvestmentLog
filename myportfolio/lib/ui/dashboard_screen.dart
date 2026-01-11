import 'package:flutter/material.dart';
import 'components/asset_summary.dart';
import 'components/portfolio_card.dart';
import 'components/valuation_chart.dart';

import '../../models/asset_summary_model.dart';
import '../../models/portfolio_item.dart';
import '../../models/valuation_item.dart';
import '../../services/portfolio_service.dart';

class DashboardScreen extends StatefulWidget {
  const DashboardScreen({super.key});

  @override
  State<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends State<DashboardScreen> {
  final _portfolioService = PortfolioService();
  
  bool _isLoading = true;
  AssetSummaryModel? _assetSummary;
  List<ValuationItem>? _valuationData;
  List<PortfolioItem>? _portfolioItems;

  @override
  void initState() {
    super.initState();
    _loadAllData();
  }

  Future<void> _loadAllData() async {
    try {
      final results = await Future.wait([
        _portfolioService.getAssetSummary(),
        _portfolioService.getValuationHistory(),
        _portfolioService.getPortfolioItems(),
      ]);

      if (mounted) {
        setState(() {
          _assetSummary = results[0] as AssetSummaryModel?;
          _valuationData = results[1] as List<ValuationItem>;
          _portfolioItems = results[2] as List<PortfolioItem>;
          _isLoading = false;
        });
      }
    } catch (e) {
      debugPrint('Error loading dashboard data: $e');
      if (mounted) {
        setState(() {
          _isLoading = false;
        });
      }
    }
  }
  
  Future<void> _onRefresh() async {
    // When refreshing, we don't necessarily need to show the full screen spinner,
    // as RefreshIndicator handles the UI. We just await the data.
    await _loadAllData();
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Scaffold(
        backgroundColor: Color(0xFFF9FAFB), // Match design background
        body: Center(child: CircularProgressIndicator()),
      );
    }

    return Scaffold(
      backgroundColor: Colors.grey[100],
      body: Center(
        child: Container(
          width: double.infinity,
          constraints: const BoxConstraints(
            maxWidth: 480,
          ), 
          color: Colors.white,
          child: Column(
            children: [
              // Header
              SafeArea(
                bottom: false,
                child: Padding(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 20,
                    vertical: 12,
                  ),
                  child: Row(
                    mainAxisAlignment: MainAxisAlignment.spaceBetween,
                    children: [
                      const Icon(Icons.menu, color: Colors.black87),
                      const Text(
                        "My Portfolio",
                        style: TextStyle(
                          fontSize: 16,
                          fontWeight: FontWeight.bold,
                        ),
                      ),
                      Container(
                        width: 32,
                        height: 32,
                        decoration: const BoxDecoration(
                          color: Colors.grey,
                          shape: BoxShape.circle,
                        ),
                        child: const Icon(
                          Icons.person,
                          color: Colors.white,
                          size: 20,
                        ),
                      ),
                    ],
                  ),
                ),
              ),

              Expanded(
                child: RefreshIndicator(
                  onRefresh: _onRefresh,
                  backgroundColor: Colors.white,
                  color: Colors.black,
                  child: ListView(
                    padding: EdgeInsets.zero,
                    children: [
                      AssetSummary(assetSummary: _assetSummary),
                      const SizedBox(height: 16),
                      // Action Buttons
                      Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 20),
                        child: Row(
                          children: [
                            Expanded(
                              child: ElevatedButton(
                                onPressed: () {},
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.black,
                                  foregroundColor: Colors.white,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 16,
                                  ),
                                ),
                                child: const Text("입금"),
                              ),
                            ),
                            const SizedBox(width: 12),
                            Expanded(
                              child: ElevatedButton(
                                onPressed: () {},
                                style: ElevatedButton.styleFrom(
                                  backgroundColor: Colors.grey[100],
                                  foregroundColor: Colors.black,
                                  elevation: 0,
                                  shape: RoundedRectangleBorder(
                                    borderRadius: BorderRadius.circular(12),
                                  ),
                                  padding: const EdgeInsets.symmetric(
                                    vertical: 16,
                                  ),
                                ),
                                child: const Text("출금"),
                              ),
                            ),
                          ],
                        ),
                      ),

                      const SizedBox(height: 24),
                      const Divider(
                        thickness: 8,
                        color: Color(0xFFF9FAFB),
                      ), 

                      ValuationChart(data: _valuationData),

                      const Divider(
                        thickness: 8,
                        color: Color(0xFFF9FAFB),
                      ), 

                      PortfolioCard(data: _portfolioItems),

                      const Divider(
                        thickness: 8,
                        color: Color(0xFFF9FAFB),
                      ),

                      // Investment Coach Card
                      Container(
                        color: Colors.white,
                        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 24),
                        child: GestureDetector(
                          onTap: () {
                            // TODO: Navigate to Investment Coach Page
                          },
                          behavior: HitTestBehavior.opaque,
                          child: Row(
                            mainAxisAlignment: MainAxisAlignment.spaceBetween,
                            children: const [
                              Text(
                                "투자 코치",
                                style: TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.bold,
                                  color: Colors.black,
                                ),
                              ),
                              Icon(
                                Icons.chevron_right,
                                color: Color(0xFF9CA3AF),
                              ),
                            ],
                          ),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

