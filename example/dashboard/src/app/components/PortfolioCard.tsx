import React from 'react';
import { Cell, Pie, PieChart, ResponsiveContainer } from 'recharts';
import { ChevronRight } from 'lucide-react';

const data = [
  { name: '주식형', value: 26.0, amount: 5824600, color: '#5b7ce6' },
  { name: '채권형', value: 21.9, amount: 4905795, color: '#3abef9' },
  { name: '대체투자', value: 17.9, amount: 4002690, color: '#e9643b' },
  { name: '현금성 자산', value: 34.1, amount: 7640297, color: '#be52f2' },
];

export const PortfolioCard = () => {
  return (
    <div className="bg-white py-6">
      {/* Header */}
      <div className="px-5 flex items-center justify-between mb-6">
        <h2 className="text-lg font-bold text-gray-900">포트폴리오</h2>

      </div>

      {/* Donut Chart */}
      <div className="h-64 w-full flex justify-center items-center mb-6">
        <div className="w-48 h-48 relative">
            <ResponsiveContainer width="100%" height="100%">
            <PieChart>
                <Pie
                data={data}
                cx="50%"
                cy="50%"
                innerRadius={50}
                outerRadius={90}
                startAngle={90}
                endAngle={-270}
                paddingAngle={0}
                dataKey="value"
                stroke="none"
                >
                {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
                </Pie>
            </PieChart>
            </ResponsiveContainer>
            {/* Inner White Circle hole is handled by innerRadius, but Recharts doesn't fill the center by default if we want a ring. 
                The innerRadius creates a hole.
            */}
        </div>
      </div>

      {/* Legend List */}
      <div className="px-5 space-y-4 mb-8">
        {data.map((item, index) => (
          <div key={index} className="flex items-center justify-between">
            <div className="flex items-center space-x-2">
              <div 
                className="w-3 h-3 rounded-md" 
                style={{ backgroundColor: item.color }}
              />
              <span className="text-gray-900 font-medium text-sm">{item.name}</span>
              <span className="text-gray-400 text-sm font-light">{item.value.toFixed(1)}%</span>
            </div>
            <div className="text-gray-900 font-bold text-sm">
              {item.amount.toLocaleString()}원
            </div>
          </div>
        ))}
      </div>

      {/* View Details Button */}
      <div className="px-5 mb-8">
        <button className="w-full bg-gray-100 text-gray-600 font-semibold py-3.5 rounded-xl text-sm hover:bg-gray-200 transition-colors">
          자세히 보기
        </button>
      </div>


    </div>
  );
};
