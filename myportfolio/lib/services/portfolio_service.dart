import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import '../models/portfolio_item.dart';
import '../models/valuation_item.dart';
import '../models/asset_summary_model.dart';
import 'package:intl/intl.dart';

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
  Future<List<Map<String, dynamic>>> getFactorSensitivity() async {
    try {
      // 1. Get the latest portfolio_date
      final dateResponse = await Supabase.instance.client
          .from('view_portfolio_factor_exposure_multi_z')
          .select('portfolio_date')
          .order('portfolio_date', ascending: false)
          .limit(1)
          .maybeSingle();

      if (dateResponse == null) return [];
      final latestDate = dateResponse['portfolio_date'];

      // 2. Fetch data for that date
      final response = await Supabase.instance.client
          .from('view_portfolio_factor_exposure_multi_z')
          .select()
          .eq('portfolio_date', latestDate);

      final data = response as List<dynamic>;

      // 3. Map factor codes to display names
      // 금리 F_RATE_US10Y
      // 환율 F_CURR_USDKRW
      // 원자재 F_COMM_GOLD_KR
      // 신용 F_CREDIT_US_IG_OAS
      // 경기 F_GROWTH_US_EQ
      final Map<String, String> factorMap = {
        'F_RATE_US10Y': '금리',
        'F_CURR_USDKRW': '환율',
        'F_COMM_GOLD_KR': '원자재',
        'F_CREDIT_US_IG_OAS': '신용',
        'F_GROWTH_US_EQ': '경기',
      };

      final List<Map<String, dynamic>> results = [];

      for (var item in data) {
        final code = item['factor_code'] as String;
        if (factorMap.containsKey(code)) {
          final sensitivity = (item['ann_sensitivity_total'] as num).toDouble();
          results.add({
            'factor': factorMap[code],
            'value': sensitivity, 
          });
        }
      }

      // Sort consistently if needed, or predefined order
      final order = ['금리', '환율', '경기', '신용', '원자재'];
      results.sort((a, b) {
        return order.indexOf(a['factor']).compareTo(order.indexOf(b['factor']));
      });

      return results;
    } catch (e) {
      debugPrint('Error fetching factor sensitivity: $e');
      return [];
    }
  }

  Future<Map<String, List<Map<String, String>>>> getPortfolioDetails() async {
    try {
      // 1. Get the latest record_date
      final dateResponse = await Supabase.instance.client
          .from('view_portfolio_summary')
          .select('record_date')
          .order('record_date', ascending: false)
          .limit(1)
          .maybeSingle();

      if (dateResponse == null) return {};
      final latestDate = dateResponse['record_date'];

      // 2. Fetch data for that date
      final response = await Supabase.instance.client
          .from('view_portfolio_summary')
          .select()
          .eq('record_date', latestDate);

      final data = response as List<dynamic>;
      
      final Map<String, List<Map<String, String>>> result = {
        'stock': [],
        'bond': [],
        'alternative': [],
        'cash': [],
      };

      final formatter = NumberFormat.currency(locale: 'ko_KR', symbol: '', decimalDigits: 0);

      for (var item in data) {
        final assetType = item['asset_type'] as String? ?? '기타';
        String sectionKey;
        if (assetType.contains('주식')) {
          sectionKey = 'stock';
        } else if (assetType.contains('채권')) {
          sectionKey = 'bond';
        } else if (assetType.contains('대체')) {
          sectionKey = 'alternative';
        } else if (assetType.contains('현금')) {
          sectionKey = 'cash';
        } else {
          sectionKey = 'alternative'; // Default or handle otherwise
        }

        final code = item['stock_code']?.toString() ?? '';
        final name = item['stock_name']?.toString() ?? '';
        final shares = item['total_qty']?.toString() ?? '0';
        
        final profitRateVal = (item['earning_rate'] as num?)?.toDouble() ?? 0.0;
        final profitRate = "${profitRateVal > 0 ? '+' : ''}${profitRateVal.toStringAsFixed(2)}%";
        
        final profitAmountVal = (item['earning_amt'] as num?)?.toInt() ?? 0;
        final profitAmount = "${profitAmountVal > 0 ? '+' : ''}${formatter.format(profitAmountVal)}원";

        final currentPriceVal = (item['cur_price'] as num?)?.toInt() ?? 0;
        final currentPrice = formatter.format(currentPriceVal);

        final totalValueVal = (item['total_eval_amt'] as num?)?.toInt() ?? 0;
        final totalValue = formatter.format(totalValueVal);

        // Calculate percentage within the section is not trivial without section total, 
        // but user prompt says "weight_percent" is available in the view.
        // Let's assume weight_percent is the portfolio weight.
        final weightVal = (item['weight_percent'] as num?)?.toDouble() ?? 0.0;
        final percentage = "${weightVal.toStringAsFixed(2)}%";

        result[sectionKey]?.add({
          'code': code,
          'name': name,
          'shares': "$shares주", 
          'profitRate': profitRate,
          'profitAmount': profitAmount,
          'currentPrice': currentPrice,
          'totalValue': totalValue,
          'percentage': percentage,
        });
      }

      return result;

    } catch (e) {
      debugPrint('Error fetching portfolio details: $e');
      return {};
    }
  }
  Future<List<Map<String, dynamic>>> getFactorSensitivityDetail() async {
    try {
      // 1. Get the latest portfolio_date
      final dateResponse = await Supabase.instance.client
          .from('view_portfolio_factor_exposure_single_z_summary')
          .select('portfolio_date')
          .order('portfolio_date', ascending: false)
          .limit(1)
          .maybeSingle();

      if (dateResponse == null) return [];
      final latestDate = dateResponse['portfolio_date'];

      // 2. Fetch data for that date
      final response = await Supabase.instance.client
          .from('view_portfolio_factor_exposure_single_z_summary')
          .select()
          .eq('portfolio_date', latestDate)
          .order('ann_sensitivity_total', ascending: false);

      final data = response as List<dynamic>;

      return data.map((item) {
        final totalFn = (item['ann_sensitivity_total'] as num?)?.toDouble() ?? 0.0;
        return {
          'factor_code': item['factor_code'] as String? ?? '',
          'factor_name': item['factor_name'] as String? ?? '',
          'value': totalFn,
        };
      }).toList();

    } catch (e) {
      debugPrint('Error fetching factor sensitivity detail: $e');
      return [];
    }
  }

  Future<Map<String, List<Map<String, dynamic>>>> getFactorTopBottomList(String factorCode) async {
    try {
      final safeFactorCode = factorCode.trim();
      // 1. Get latest date
      final dateResponse = await Supabase.instance.client
          .from('view_factor_ticker_sensitivity_top_bottom_5')
          .select('asof_date')
          .eq('factor_code', safeFactorCode)
          .order('asof_date', ascending: false)
          .limit(1)
          .maybeSingle();

      if (dateResponse == null) {
        debugPrint('TopBottom: No latest date found for $safeFactorCode');
        return {'Top': [], 'Bottom': []};
      }
      final latestDate = dateResponse['asof_date'];
      debugPrint('TopBottom: Latest date for $safeFactorCode is $latestDate');

      // 2. Fetch data
      final response = await Supabase.instance.client
          .from('view_factor_ticker_sensitivity_top_bottom_5')
          .select()
          .eq('factor_code', safeFactorCode)
          .eq('asof_date', latestDate)
          .order('rank', ascending: true); // rank 1 is top/bottom 1

      final data = response as List<dynamic>;
      debugPrint('TopBottom: Fetched ${data.length} items');

      final topList = <Map<String, dynamic>>[];
      final bottomList = <Map<String, dynamic>>[];

      for (var item in data) {
        debugPrint('TopBottom: Processing item: ${item['stock_name']} bucket=${item['bucket']}');
        final bucket = (item['bucket'] as String).trim().toLowerCase(); 
        final mappedItem = {
          'stock_code': item['stock_code'],
          'stock_name': item['stock_name'],
          'ann_sensitivity': (item['ann_sensitivity'] as num?)?.toDouble() ?? 0.0,
          'r2': (item['r2'] as num?)?.toDouble() ?? 0.0,
          'rank': item['rank'],
        };

        if (bucket == 'top') {
          topList.add(mappedItem);
        } else if (bucket == 'bottom') {
          bottomList.add(mappedItem);
        }
      }

      return {
        'Top': topList,
        'Bottom': bottomList,
      };

    } catch (e) {
      debugPrint('Error fetching factor top/bottom list: $e');
      return {'Top': [], 'Bottom': []};
    }
  }

  Future<List<PortfolioItem>> getCurrencyExposure() async {
    try {
      final response = await Supabase.instance.client
          .from('view_currency_exposure_summary')
          .select()
          .order('record_timestamp', ascending: false)
          .limit(1)
          .maybeSingle();

      if (response == null) return [];

      final weightMap = response['weight_percent_map'];
      if (weightMap == null) return [];

      final Map<String, dynamic> weights = weightMap is Map ? Map<String, dynamic>.from(weightMap) : {};
      
      final List<PortfolioItem> items = [];
      
      weights.forEach((key, value) {
        final double val = (value as num).toDouble();
        if (val > 0) {
          Color color;
          switch (key.toUpperCase()) {
            case 'KRW': color = const Color(0xFF3B82F6); break; // Blue
            case 'USD': color = const Color(0xFF10B981); break; // Green
            case 'JPY': color = const Color(0xFF8B5CF6); break; // Purple
            case 'CNY': color = const Color(0xFFEF4444); break; // Red
            case 'EUR': color = const Color(0xFFF59E0B); break; // Amber
            default: color = const Color(0xFF9CA3AF); break; // Gray
          }
          
          items.add(PortfolioItem(
            name: key,
            value: val,
            amount: 0, // Not needed for this chart
            color: color,
          ));
        }
      });

      // Sort by value desc
      items.sort((a, b) => b.value.compareTo(a.value));

      return items;
    } catch (e) {
      debugPrint('Error fetching currency exposure: $e');
      return [];
    }
  }
  Future<Map<String, String>> getFactorMetadata(String factorCode) async {
    try {
      final safeFactorCode = factorCode.trim();
      final response = await Supabase.instance.client
          .from('factor_metadata')
          .select('description, source_series')
          .eq('factor_code', safeFactorCode)
          .maybeSingle();

      if (response == null) {
        return {
          'description': '설명이 없습니다.',
          'source_series': '',
        };
      }

      return {
        'description': response['description'] as String? ?? '설명이 없습니다.',
        'source_series': response['source_series'] as String? ?? '',
      };
    } catch (e) {
      debugPrint('Error fetching factor metadata: $e');
      return {
        'description': '정보를 불러올 수 없습니다.',
        'source_series': '',
      };
    }
  }
  Future<List<Map<String, dynamic>>> getFactorReturnsHistory(String factorCode) async {
    try {
      final safeFactorCode = factorCode.trim();
      final startDate = DateTime.now().subtract(const Duration(days: 180));
      
      final response = await Supabase.instance.client
          .from('factor_returns')
          .select('record_date, ret')
          .eq('factor_code', safeFactorCode)
          .gte('record_date', startDate.toIso8601String())
          .order('record_date', ascending: true);

      final rawData = response as List<dynamic>;
      final List<Map<String, dynamic>> result = [];
      double cumulative = 1.0;

      for (var item in rawData) {
        final double dailyRet = (item['ret'] as num).toDouble();
        cumulative *= (1 + dailyRet);
        
        result.add({
          'date': DateTime.parse(item['record_date']),
          'value': cumulative - 1.0,
        });
      }

      return result;
    } catch (e) {
      debugPrint('Error fetching factor returns history: $e');
      return [];
    }
  }
}
