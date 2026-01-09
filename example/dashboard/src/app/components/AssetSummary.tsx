import React from 'react';

export const AssetSummary = () => {
  return (
    <div className="px-5 pt-2 pb-6 bg-white">
      {/* Total Amount Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">
          12,840,340원
        </h1>

      </div>

      {/* Details Card */}
      <div className="bg-gray-50 rounded-2xl p-5 space-y-4">
        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-500">평가손익</span>
          <span className="text-[#F04438] font-semibold">
            +840,340원 (7.00%)
          </span>
        </div>
        
        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-500">총 투자원금</span>
          <span className="text-gray-900 font-medium">
            12,000,000원
          </span>
        </div>

        <div className="flex justify-between items-center text-sm">
          <span className="text-gray-500">현금 잔액</span>
          <span className="text-gray-900 font-medium">
            153,224원
          </span>
        </div>
      </div>
    </div>
  );
};
