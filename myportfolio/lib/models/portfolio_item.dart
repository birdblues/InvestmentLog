import 'package:flutter/material.dart';

class PortfolioItem {
  final String name;
  final double value;
  final int amount;
  final Color color;

  PortfolioItem({
    required this.name,
    required this.value,
    required this.amount,
    required this.color,
  });

  // Factory to create from Supabase/JSON later if needed
  factory PortfolioItem.fromJson(Map<String, dynamic> json) {
    return PortfolioItem(
      name: json['name'],
      value: (json['value'] as num).toDouble(),
      amount: json['amount'],
      color: Color(int.parse(json['color'].replaceFirst('#', '0xFF'))),
    );
  }
}
