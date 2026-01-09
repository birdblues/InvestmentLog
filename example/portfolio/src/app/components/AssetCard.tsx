interface AssetCardProps {
  code: string;
  name: string;
  percentage: string;
  shares: string;
  profitRate: string;
  profitAmount: string;
  currentPrice: string;
  totalValue: string;
}

export function AssetCard({
  code,
  name,
  percentage,
  shares,
  profitRate,
  profitAmount,
  currentPrice,
  totalValue,
}: AssetCardProps) {
  const isPositive = profitRate.startsWith('+');
  const textColor = isPositive ? 'text-red-500' : 'text-blue-500';

  return (
    <div className="bg-white p-4 mb-3 rounded-lg">
      <div className="flex justify-between items-start mb-3">
        <div>
          <div className="text-xs text-gray-400 mb-1">{code}</div>
          <div className="font-medium">{name}</div>
        </div>
        <div className="text-right">
          <div className="font-medium">{percentage}</div>
          <div className="text-xs text-gray-400">{shares}</div>
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <div className="text-gray-400 text-xs">손익률</div>
          <div className={textColor}>{profitRate}</div>
        </div>
        <div>
          <div className="text-gray-400 text-xs">평가손익</div>
          <div className={textColor}>{profitAmount}</div>
        </div>
        <div>
          <div className="text-gray-400 text-xs">평가가격</div>
          <div>{currentPrice}</div>
        </div>
        <div>
          <div className="text-gray-400 text-xs">평가금액</div>
          <div>{totalValue}</div>
        </div>
      </div>
    </div>
  );
}
