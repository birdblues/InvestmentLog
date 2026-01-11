import 'package:flutter/material.dart';
import '../../services/portfolio_service.dart';

class SensitivityTopBottomPage extends StatefulWidget {
  final String factorCode;
  final String factorName;

  const SensitivityTopBottomPage({
    super.key,
    required this.factorCode,
    required this.factorName,
  });

  @override
  State<SensitivityTopBottomPage> createState() =>
      _SensitivityTopBottomPageState();
}

class _SensitivityTopBottomPageState extends State<SensitivityTopBottomPage> {
  late Future<Map<String, List<Map<String, dynamic>>>> _dataFuture;

  @override
  void initState() {
    super.initState();
    _dataFuture = PortfolioService().getFactorTopBottomList(widget.factorCode);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF9FAFB),
      appBar: AppBar(
        title: Text(
          "${widget.factorName} 상/하위 종목",
          style: const TextStyle(
            color: Colors.black,
            fontSize: 18,
            fontWeight: FontWeight.bold,
          ),
        ),
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Colors.black),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: FutureBuilder<Map<String, List<Map<String, dynamic>>>>(
        future: _dataFuture,
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return const Center(child: CircularProgressIndicator());
          }
          if (snapshot.hasError) {
            return const Center(child: Text("데이터를 불러오는데 실패했습니다."));
          }

          final data = snapshot.data ?? {'Top': [], 'Bottom': []};
          final topList = data['Top'] ?? [];
          final bottomList = data['Bottom'] ?? [];

          if (topList.isEmpty && bottomList.isEmpty) {
            return const Center(child: Text("데이터가 없습니다."));
          }

          return SingleChildScrollView(
            padding: const EdgeInsets.all(20),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                _buildSection("상위 5", topList),
                const SizedBox(height: 24),
                _buildSection("하위 5", bottomList),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _buildSection(String title, List<Map<String, dynamic>> items) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: const TextStyle(
            fontSize: 16,
            fontWeight: FontWeight.bold,
            color: Color(0xFF1F2937),
          ),
        ),
        const SizedBox(height: 12),
        if (items.isEmpty)
          const Text("데이터 없음", style: TextStyle(color: Colors.grey))
        else
          ...items.map((item) => _buildStockCard(item)),
      ],
    );
  }

  Widget _buildStockCard(Map<String, dynamic> item) {
    final name = item['stock_name'] as String;
    final code = item['stock_code'] as String;
    final sensitivity = item['ann_sensitivity'] as double;
    final r2 = item['r2'] as double;

    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        children: [
          // Row 1: Name (Left) ... Code (Right)
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Expanded(
                child: Text(
                  name,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF1F2937),
                  ),
                  overflow: TextOverflow.ellipsis,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                code,
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xFF9CA3AF),
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          // Row 2: Sensitivity (Left) ... R2 (Right)
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(
                "민감도: ${sensitivity.toStringAsFixed(2)}",
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.bold,
                  color: sensitivity >= 0
                      ? const Color(0xFFEF4444)
                      : const Color(0xFF3B82F6),
                ),
              ),
              Text(
                "R²: ${r2.toStringAsFixed(2)}",
                style: const TextStyle(
                  fontSize: 12,
                  color: Color(0xFF6B7280),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
