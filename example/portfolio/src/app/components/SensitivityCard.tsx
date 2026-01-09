import { RadarChart, Radar, PolarGrid, PolarAngleAxis, ResponsiveContainer } from 'recharts';

interface SensitivityCardProps {
  data: {
    factor: string;
    value: number;
  }[];
}

export function SensitivityCard({ data }: SensitivityCardProps) {
  return (
    <div className="bg-white p-4 mb-3 rounded-lg">
      <h3 className="text-sm font-medium mb-3">민감도 분석</h3>
      <div className="h-48">
        <ResponsiveContainer width="100%" height="100%">
          <RadarChart data={data}>
            <PolarGrid stroke="#e5e7eb" />
            <PolarAngleAxis 
              dataKey="factor" 
              tick={{ fill: '#6b7280', fontSize: 12 }}
            />
            <Radar
              dataKey="value"
              stroke="#5B8EFF"
              fill="#5B8EFF"
              fillOpacity={0.3}
            />
          </RadarChart>
        </ResponsiveContainer>
      </div>
      <div className="grid grid-cols-5 gap-2 mt-3 text-xs text-center">
        {data.map((item, index) => (
          <div key={index}>
            <div className="text-gray-400">{item.factor}</div>
            <div className="font-medium">{item.value}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
