import 'package:flutter/material.dart';
import '../models/portfolio_item.dart';
import '../models/valuation_item.dart';

class PortfolioService {
  // Mock data to match React example
  // { name: '주식형', value: 26.0, amount: 5824600, color: '#5b7ce6' },
  // { name: '채권형', value: 21.9, amount: 4905795, color: '#3abef9' },
  // { name: '대체투자', value: 17.9, amount: 4002690, color: '#e9643b' },
  // { name: '현금성 자산', value: 34.1, amount: 7640297, color: '#be52f2' },
  Future<List<PortfolioItem>> getPortfolioItems() async {
    // Simulate network delay
    await Future.delayed(const Duration(milliseconds: 500));

    return [
      PortfolioItem(
        name: '주식형',
        value: 26.0,
        amount: 5824600,
        color: const Color(0xFF5b7ce6),
      ),
      PortfolioItem(
        name: '채권형',
        value: 21.9,
        amount: 4905795,
        color: const Color(0xFF3abef9),
      ),
      PortfolioItem(
        name: '대체투자',
        value: 17.9,
        amount: 4002690,
        color: const Color(0xFFe9643b),
      ),
      PortfolioItem(
        name: '현금성 자산',
        value: 34.1,
        amount: 7640297,
        color: const Color(0xFFbe52f2),
      ),
    ];
  }

  Future<List<ValuationItem>> getValuationHistory() async {
    await Future.delayed(const Duration(milliseconds: 500));

    // Mock data from ValuationChart.tsx
    // { date: '2026-01-01', value: 12100000, principal: 11500000 }, ...
    return [
      ValuationItem(date: '2026-01-01', value: 12100000, principal: 11500000),
      ValuationItem(date: '2026-01-02', value: 12050000, principal: 11500000),
      ValuationItem(date: '2026-01-03', value: 12300000, principal: 11500000),
      ValuationItem(date: '2026-01-04', value: 12250000, principal: 11500000),
      ValuationItem(date: '2026-01-05', value: 12350000, principal: 11500000),
      ValuationItem(date: '2026-01-06', value: 12400000, principal: 11500000),
      ValuationItem(date: '2026-01-07', value: 12550000, principal: 11500000),
      ValuationItem(date: '2026-01-08', value: 12450000, principal: 11500000),
      ValuationItem(date: '2026-01-09', value: 12400000, principal: 11500000),
      ValuationItem(date: '2026-01-10', value: 12300000, principal: 11500000),
      ValuationItem(date: '2026-01-11', value: 12450000, principal: 12000000),
      ValuationItem(date: '2026-01-12', value: 12500000, principal: 12000000),
      ValuationItem(date: '2026-01-13', value: 12650000, principal: 12000000),
      ValuationItem(date: '2026-01-14', value: 12932100, principal: 12000000),
      ValuationItem(date: '2026-01-15', value: 12750000, principal: 12000000),
      ValuationItem(date: '2026-01-16', value: 12800000, principal: 12000000),
      ValuationItem(date: '2026-01-17', value: 12650000, principal: 12000000),
      ValuationItem(date: '2026-01-18', value: 12550000, principal: 12000000),
      ValuationItem(date: '2026-01-19', value: 12840340, principal: 12000000),
    ];
  }
}
