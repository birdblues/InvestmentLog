class ValuationItem {
  final String date;
  final double value;
  final double principal;

  ValuationItem({
    required this.date,
    required this.value,
    required this.principal,
  });

  factory ValuationItem.fromJson(Map<String, dynamic> json) {
    return ValuationItem(
      date: json['record_date'] as String,
      value: (json['total_asset'] as num).toDouble(),
      principal: (json['total_invested'] as num).toDouble(),
    );
  }
}
