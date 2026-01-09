class AssetSummaryModel {
  final DateTime asOfTs;
  final double totalAsset;
  final double totalCash;
  final double totalInvested;
  final double totalReturnPct;

  AssetSummaryModel({
    required this.asOfTs,
    required this.totalAsset,
    required this.totalCash,
    required this.totalInvested,
    required this.totalReturnPct,
  });

  factory AssetSummaryModel.fromJson(Map<String, dynamic> json) {
    return AssetSummaryModel(
      asOfTs: DateTime.parse(json['as_of_ts']),
      totalAsset: (json['total_asset'] as num).toDouble(),
      totalCash: (json['total_cash'] as num).toDouble(),
      totalInvested: (json['total_invested'] as num).toDouble(),
      totalReturnPct: (json['total_return_pct'] as num).toDouble(),
    );
  }
}
