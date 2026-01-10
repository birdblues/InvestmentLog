import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import '../../models/asset_summary_model.dart';

class AssetSummary extends StatelessWidget {
  final AssetSummaryModel? assetSummary;

  const AssetSummary({super.key, this.assetSummary});

  String _formatCurrency(double value) {
    final formatter = NumberFormat.currency(locale: 'ko_KR', symbol: '', decimalDigits: 0);
    return '${formatter.format(value)}원';
  }

  String _formatPercent(double value) {
    return '${value.toStringAsFixed(2)}%';
  }

  @override
  Widget build(BuildContext context) {
    // Default/Empty state if no data
    final totalAsset = assetSummary?.totalAsset ?? 0;
    final totalInvested = assetSummary?.totalInvested ?? 0;
    final totalCash = assetSummary?.totalCash ?? 0;
    final totalReturnPct = assetSummary?.totalReturnPct ?? 0;
    
    // Profit calculation logic (Total Asset - Total Invested)
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
