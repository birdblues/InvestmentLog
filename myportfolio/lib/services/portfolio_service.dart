import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/portfolio_item.dart';
import '../models/valuation_item.dart';
import '../models/asset_summary_model.dart';

class PortfolioService {
  Future<AssetSummaryModel?> getAssetSummary() async {
    try {
      final response = await Supabase.instance.client
          .from('view_asset_summary')
          .select()
          .limit(1)
          .maybeSingle();

      if (response != null) {
        return AssetSummaryModel.fromJson(response);
      }
    } catch (e) {
      debugPrint('Error fetching asset summary: $e');
    }
    return null;
  }

  // Mock data to match React example
  // { name: '주식형', value: 26.0, amount: 5824600, color: '#5b7ce6' },
  // { name: '채권형', value: 21.9, amount: 4905795, color: '#3abef9' },
  // { name: '대체투자', value: 17.9, amount: 4002690, color: '#e9643b' },
  // { name: '현금성 자산', value: 34.1, amount: 7640297, color: '#be52f2' },
  Future<List<PortfolioItem>> getPortfolioItems() async {
    try {
      final response = await Supabase.instance.client
          .from('view_portfolio_daily_summary')
          .select()
          .order('as_of_ts', ascending: false)
          .limit(1)
          .maybeSingle();

      if (response == null) return [];

      final data = response;
      final stockAmt = (data['주식'] as num?)?.toDouble() ?? 0.0;
      final bondAmt = (data['채권'] as num?)?.toDouble() ?? 0.0;
      final altAmt = (data['대체투자'] as num?)?.toDouble() ?? 0.0;
      final cashAmt = (data['현금성자산'] as num?)?.toDouble() ?? 0.0;

      final total = stockAmt + bondAmt + altAmt + cashAmt;
      if (total == 0) return [];

      return [
        PortfolioItem(
          name: '주식형',
          value: (stockAmt / total) * 100,
          amount: stockAmt.toInt(),
          color: const Color(0xFF5b7ce6),
        ),
        PortfolioItem(
          name: '채권형',
          value: (bondAmt / total) * 100,
          amount: bondAmt.toInt(),
          color: const Color(0xFF3abef9),
        ),
        PortfolioItem(
          name: '대체투자',
          value: (altAmt / total) * 100,
          amount: altAmt.toInt(),
          color: const Color(0xFFe9643b),
        ),
        PortfolioItem(
          name: '현금성 자산',
          value: (cashAmt / total) * 100,
          amount: cashAmt.toInt(),
          color: const Color(0xFFbe52f2),
        ),
      ];
    } catch (e) {
      debugPrint('Error fetching portfolio items: $e');
      return [];
    }
  }

  Future<List<ValuationItem>> getValuationHistory() async {
    try {
      final response = await Supabase.instance.client
          .from('view_daily_net_worth')
          .select()
          .order('record_date', ascending: true);
      
      final data = response as List<dynamic>;
      return data.map((e) => ValuationItem.fromJson(e)).toList();
    } catch (e) {
      debugPrint('Error fetching valuation history: $e');
      return [];
    }
  }
}
