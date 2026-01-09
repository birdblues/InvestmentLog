import React, { useState } from 'react';
import { Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis, ReferenceDot } from 'recharts';

const data = [
  { date: '2026-01-01', value: 12100000, principal: 11500000 },
  { date: '2026-01-02', value: 12050000, principal: 11500000 },
  { date: '2026-01-03', value: 12300000, principal: 11500000 },
  { date: '2026-01-04', value: 12250000, principal: 11500000 },
  { date: '2026-01-05', value: 12350000, principal: 11500000 },
  { date: '2026-01-06', value: 12400000, principal: 11500000 },
  { date: '2026-01-07', value: 12550000, principal: 11500000 }, // Peak 1
  { date: '2026-01-08', value: 12450000, principal: 11500000 },
  { date: '2026-01-09', value: 12400000, principal: 11500000 },
  { date: '2026-01-10', value: 12300000, principal: 11500000 }, // Dip
  { date: '2026-01-11', value: 12450000, principal: 12000000 }, // Principal increase
  { date: '2026-01-12', value: 12500000, principal: 12000000 },
  { date: '2026-01-13', value: 12650000, principal: 12000000 },
  { date: '2026-01-14', value: 12932100, principal: 12000000 }, // Peak highlighted
  { date: '2026-01-15', value: 12750000, principal: 12000000 },
  { date: '2026-01-16', value: 12800000, principal: 12000000 },
  { date: '2026-01-17', value: 12650000, principal: 12000000 },
  { date: '2026-01-18', value: 12550000, principal: 12000000 },
  { date: '2026-01-19', value: 12840340, principal: 12000000 }, // Current
];

const CustomTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    return (
      <div className="bg-red-500 text-white text-xs px-2 py-1 rounded mb-2">
        {payload[0].value.toLocaleString()}원
      </div>
    );
  }
  return null;
};

const CustomTick = (props: any) => {
  const { x, y, payload } = props;
  const date = payload.value;
  
  let textAnchor = 'middle';
  if (date === data[0].date) textAnchor = 'start';
  if (date === data[data.length - 1].date) textAnchor = 'end';

  return (
    <g transform={`translate(${x},${y})`}>
      <text x={0} y={0} dy={10} textAnchor={textAnchor as any} fill="#9CA3AF" fontSize={12}>
        {date.slice(5).replace('-', '.')}
      </text>
    </g>
  );
};

export const ValuationChart = () => {
  const [viewMode, setViewMode] = useState<'won' | 'percent'>('won');

  return (
    <div className="bg-white pt-6 pb-10">
      <div className="px-5 flex items-center justify-between mb-8">
        <h2 className="text-lg font-bold text-gray-900">평가금액</h2>
        
        <div className="flex bg-gray-100 rounded-full p-1">
          <button 
            className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
              viewMode === 'won' ? 'bg-slate-500 text-white shadow-sm' : 'text-gray-400'
            }`}
            onClick={() => setViewMode('won')}
          >
            ₩
          </button>
          <button 
            className={`px-3 py-1 rounded-full text-sm font-medium transition-all ${
              viewMode === 'percent' ? 'bg-slate-500 text-white shadow-sm' : 'text-gray-400'
            }`}
            onClick={() => setViewMode('percent')}
          >
            %
          </button>
        </div>
      </div>

      <div className="h-64 w-full relative">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 10, right: 10, left: 10, bottom: 20 }}>
            <defs>
              <linearGradient id="colorValue" x1="0" y1="0" x2="0" y2="1">
                <stop offset="5%" stopColor="#1B2B4B" stopOpacity={0.1}/>
                <stop offset="95%" stopColor="#1B2B4B" stopOpacity={0}/>
              </linearGradient>
            </defs>
            <XAxis 
              dataKey="date" 
              axisLine={false}
              tickLine={false}
              tick={<CustomTick />}
              interval={5}
            />
            <YAxis hide domain={['dataMin - 1000000', 'dataMax + 1000000']} />
            <Area 
              type="monotone" 
              dataKey="value" 
              stroke="#1B2B4B" 
              strokeWidth={2}
              fillOpacity={1} 
              fill="url(#colorValue)" 
            />
            <Line
              type="step"
              dataKey="principal"
              stroke="#6B7280"
              strokeWidth={2}
              strokeDasharray="4 4"
              dot={false}
              activeDot={false}
            />
            <ReferenceDot
              x="2026-01-14"
              y={12932100}
              r={4}
              fill="#F04438"
              stroke="#fff"
              strokeWidth={2}
              isFront={true}
              label={{ 
                value: '12,932,100원', 
                position: 'top', 
                fill: '#F04438', 
                fontSize: 12, 
                fontWeight: 600,
                offset: 10
              }}
            />
          </ComposedChart>
        </ResponsiveContainer>
        
        {/* Helper text for the dashed line if needed, or legend. 
            For now, just keeping the visual separator below. */}
        <div className="absolute bottom-10 left-0 right-0 border-b border-dashed border-gray-200 pointer-events-none opacity-0"></div>
      </div>

      <div className="px-5 mt-4">
        <button className="w-full bg-gray-100 text-gray-600 font-semibold py-3.5 rounded-xl text-sm hover:bg-gray-200 transition-colors">
          자세히 보기
        </button>
      </div>
    </div>
  );
};
