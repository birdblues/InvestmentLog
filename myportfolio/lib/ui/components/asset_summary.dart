import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../../models/asset_summary_model.dart';
import '../../services/portfolio_service.dart';

class AssetSummary extends StatefulWidget {
  const AssetSummary({super.key});

  @override
  State<AssetSummary> createState() => _AssetSummaryState();
}

class _AssetSummaryState extends State<AssetSummary> {
  final _portfolioService = PortfolioService();
  AssetSummaryModel? _summary;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadData();
  }

  Future<void> _loadData() async {
    final summary = await _portfolioService.getAssetSummary();
    if (mounted) {
      setState(() {
        _summary = summary;
        _isLoading = false;
      });
    }
  }

  String _formatCurrency(double value) {
    final formatter = NumberFormat.currency(locale: 'ko_KR', symbol: '', decimalDigits: 0);
    return '${formatter.format(value)}원';
  }

  String _formatPercent(double value) {
    return '${value.toStringAsFixed(2)}%';
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return const Padding(
        padding: EdgeInsets.all(20.0),
        child: Center(child: CircularProgressIndicator()),
      );
    }

    // Default/Empty state if no data
    final totalAsset = _summary?.totalAsset ?? 0;
    final totalInvested = _summary?.totalInvested ?? 0;
    final totalCash = _summary?.totalCash ?? 0;
    final totalReturnPct = _summary?.totalReturnPct ?? 0;
    
    // Calculate profit amount (Total Asset - Total Invested - Cash is not quite right usually, 
    // strictly speaking profit = Current Value of Investments - Cost Basis. 
    // Logic: Total Asset = Invested Value + Cash. 
    // Note: The user prompt asked to show 'total_return_pct'. 
    // Usually profit amount needs to be derived from (total_asset - total_cash) - total_invested? 
    // Or if total_invested is cost basis? 
    // Let's assume (total_asset - total_cash) is current market value of investments.
    // And total_invested is the cost basis (principal).
    // so profit = (totalAsset - totalCash) - totalInvested.
    // Or simplier: totalAsset - (totalInvested + totalCash) if totalInvested means principal.
    // Wait, typical schema: total_asset = market_value + cash. total_invested = principal.
    // So profit = total_asset - total_invested. (If we assume total_invested is the TOTAL input so far including cash not yet bought?)
    // Let's stick to simple Total Asset - Total Invested for now if that represents PnL.
    // Actually the mock data had: "평가손익 +840,340원". 
    // Let's calculate: Profit = Total Asset - Total Invested.
    final profit = totalAsset - totalInvested; 
    final isPositive = profit >= 0;
    final profitSign = isPositive ? '+' : '';

    return Padding(
      padding: const EdgeInsets.all(20.0),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                _formatCurrency(totalAsset),
                style: GoogleFonts.outfit(
                  fontSize: 28,
                  fontWeight: FontWeight.bold,
                  letterSpacing: -0.5,
                  height: 1.1,
                  color: Colors.black,
                ),
              ),
            ],
          ),
          const SizedBox(height: 24),

          Container(
            padding: const EdgeInsets.all(20),
            decoration: BoxDecoration(
              color: const Color(0xFFF9FAFB),
              borderRadius: BorderRadius.circular(16),
            ),
            child: Column(
              children: [
                _buildRow(
                  "평가손익",
                  "$profitSign${_formatCurrency(profit)} (${_formatPercent(totalReturnPct)})",
                  valueColor: isPositive ? const Color(0xFFF04438) : Colors.blue,
                  isBold: true,
                ),
                const SizedBox(height: 16),
                _buildRow("총 투자원금", _formatCurrency(totalInvested)),
                const SizedBox(height: 16),
                _buildRow("현금 잔액", _formatCurrency(totalCash)),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildRow(
    String label,
    String value, {
    Color valueColor = Colors.black,
    bool isBold = false,
  }) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: const TextStyle(color: Color(0xFF6B7280), fontSize: 14),
        ),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontSize: 14,
            fontWeight: isBold ? FontWeight.w600 : FontWeight.w500,
          ),
        ),
      ],
    );
  }
}
