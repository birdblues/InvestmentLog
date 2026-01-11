import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

class AssetCard extends StatelessWidget {
  final String code;
  final String name;
  final String percentage;
  final String shares;
  final String profitRate;
  final String profitAmount;
  final String currentPrice;
  final String totalValue;

  const AssetCard({
    super.key,
    required this.code,
    required this.name,
    required this.percentage,
    required this.shares,
    required this.profitRate,
    required this.profitAmount,
    required this.currentPrice,
    required this.totalValue,
  });

  @override
  Widget build(BuildContext context) {
    final isPositive = profitRate.startsWith('+');
    final profitColor = isPositive ? const Color(0xFFD32F2F) : const Color(0xFF1976D2);

    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 20),
      decoration: const BoxDecoration(
        color: Colors.white,
        border: Border(
           bottom: BorderSide(color: Color(0xFFF5F5F5), width: 1),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Header Row 1: Code + Icon ..... Percentage
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              GestureDetector(
                onTap: () {
                  Clipboard.setData(ClipboardData(text: code));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text("종목코드가 복사되었습니다.")),
                  );
                },
                child: Row(
                  children: [
                    Text(
                      code,
                      style: TextStyle(fontSize: 12, color: Colors.grey[400]),
                    ),
                    const SizedBox(width: 4),
                    Icon(Icons.copy, size: 12, color: Colors.grey[400]),
                  ],
                ),
              ),
              Text(
                percentage,
                style: TextStyle(fontSize: 14, color: Colors.grey[600]),
              ),
            ],
          ),
          const SizedBox(height: 4),
          
          // Header Row 2: Name ..... Shares
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  name,
                  style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                  overflow: TextOverflow.ellipsis,
                  maxLines: 2, 
                ),
              ),
              const SizedBox(width: 8),
              Row(
                children: [
                  Container(
                    width: 1,
                    height: 12,
                    color: Colors.grey[300],
                    margin: const EdgeInsets.only(right: 8),
                  ),
                  Text(
                    shares,
                    style: const TextStyle(color: Colors.black, fontSize: 14),
                  ),
                ],
              ),
            ],
          ),
          const SizedBox(height: 24),

          // Data Grid
          Row(
            children: [
              Expanded(
                child: _buildDataRow('손익률', profitRate, profitColor),
              ),
              const SizedBox(width: 24),
              Expanded(
                child: _buildDataRow('평가손익', profitAmount, profitColor),
              ),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              Expanded(
                child: _buildDataRow('평균가격', currentPrice, Colors.black87),
              ),
              const SizedBox(width: 24),
              Expanded(
                child: _buildDataRow('평가금액', totalValue, Colors.black87),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _buildDataRow(String label, String value, Color valueColor) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(
          label,
          style: TextStyle(
            color: Colors.grey[500],
            fontSize: 13,
          ),
        ),
        Text(
          value,
          style: TextStyle(
            color: valueColor,
            fontWeight: FontWeight.w600,
            fontSize: 14,
          ),
        ),
      ],
    );
  }
}
