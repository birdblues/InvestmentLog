import { ChevronLeft, Battery, Wifi, Signal, ChevronDown } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer } from 'recharts';
import { AssetCard } from './components/AssetCard';
import { SensitivityCard } from './components/SensitivityCard';
import { useState } from 'react';

export default function App() {
  const [expandedSections, setExpandedSections] = useState({
    stock: true,
    bond: true,
    alternative: true,
    cash: true,
  });

  const toggleSection = (section: keyof typeof expandedSections) => {
    setExpandedSections(prev => ({
      ...prev,
      [section]: !prev[section],
    }));
  };

  const portfolioData = [
    { name: '주식형', value: 26.3, color: '#5B8EFF' },
    { name: '채권형', value: 21.7, color: '#4FC3F7' },
    { name: '대체투자', value: 17.9, color: '#FF7043' },
    { name: '현금성 자산', value: 34.1, color: '#BA68C8' },
  ];

  const stockAssets = [
    {
      code: '241180',
      name: 'TIGER 일본니케이225',
      percentage: '1.40%',
      shares: '11주',
      profitRate: '+35.44%',
      profitAmount: '+83,084원',
      currentPrice: '21,312',
      totalValue: '317,515',
    },
    {
      code: '294400',
      name: 'KIWOOM 200TR',
      percentage: '2.70%',
      shares: '7주',
      profitRate: '+83.30%',
      profitAmount: '+278,599원',
      currentPrice: '47,780',
      totalValue: '613,060',
    },
    {
      code: '379810',
      name: 'KODEX 미국나스닥100',
      percentage: '8.20%',
      shares: '75주',
      profitRate: '+16.87%',
      profitAmount: '+268,053원',
      currentPrice: '21,181',
      totalValue: '1,856,625',
    },
    {
      code: '283580',
      name: 'KODEX 차이나CSI300',
      percentage: '4.30%',
      shares: '61주',
      profitRate: '+32.95%',
      profitAmount: '+241,958원',
      currentPrice: '21,312',
      totalValue: '976,305',
    },
  ];

  const bondAssets = [
    {
      code: '148070',
      name: 'KOSEF 국고채10년',
      percentage: '5.10%',
      shares: '24주',
      profitRate: '+2.15%',
      profitAmount: '+12,450원',
      currentPrice: '102,350',
      totalValue: '578,400',
    },
    {
      code: '114260',
      name: 'KODEX 단기채권',
      percentage: '3.80%',
      shares: '18주',
      profitRate: '+1.82%',
      profitAmount: '+8,720원',
      currentPrice: '98,220',
      totalValue: '487,890',
    },
  ];

  const alternativeAssets = [
    {
      code: '411060',
      name: 'ACE 골드선물 H',
      percentage: '6.50%',
      shares: '42주',
      profitRate: '+12.34%',
      profitAmount: '+98,560원',
      currentPrice: '23,450',
      totalValue: '798,900',
    },
    {
      code: '130730',
      name: 'KOSEF 부동산인프라',
      percentage: '4.20%',
      shares: '29주',
      profitRate: '+8.91%',
      profitAmount: '+45,230원',
      currentPrice: '18,760',
      totalValue: '544,040',
    },
  ];

  const cashAssets = [
    {
      code: 'MMF001',
      name: '삼성MMF',
      percentage: '15.30%',
      shares: '-',
      profitRate: '+3.12%',
      profitAmount: '+58,450원',
      currentPrice: '-',
      totalValue: '1,932,100',
    },
    {
      code: 'CMA002',
      name: 'KB CMA',
      percentage: '10.50%',
      shares: '-',
      profitRate: '+2.85%',
      profitAmount: '+36,890원',
      currentPrice: '-',
      totalValue: '1,329,800',
    },
  ];

  const stockSensitivity = [
    { factor: '금리', value: 65 },
    { factor: '환율', value: 80 },
    { factor: '경기', value: 90 },
    { factor: '신용', value: 45 },
    { factor: '원자재', value: 55 },
  ];

  const bondSensitivity = [
    { factor: '금리', value: 95 },
    { factor: '환율', value: 40 },
    { factor: '경기', value: 50 },
    { factor: '신용', value: 75 },
    { factor: '원자재', value: 20 },
  ];

  const alternativeSensitivity = [
    { factor: '금리', value: 55 },
    { factor: '환율', value: 70 },
    { factor: '경기', value: 60 },
    { factor: '신용', value: 50 },
    { factor: '원자재', value: 85 },
  ];

  const cashSensitivity = [
    { factor: '금리', value: 30 },
    { factor: '환율', value: 20 },
    { factor: '경기', value: 15 },
    { factor: '신용', value: 25 },
    { factor: '원자재', value: 10 },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 상단 상태바 */}
      <div className="bg-white px-4 py-2 flex justify-between items-center text-sm">
        <div className="flex items-center gap-1">
          <span>5:59</span>
          <span className="ml-1">🔒</span>
        </div>
        <div className="flex items-center gap-1">
          <Signal size={16} />
          <span className="text-xs">LTE</span>
          <Wifi size={16} />
          <div className="relative">
            <Battery size={20} className="fill-current" />
            <span className="absolute -right-3 top-0 text-xs">15</span>
          </div>
        </div>
      </div>

      {/* 헤더 */}
      <div className="bg-white px-4 py-4 flex items-center justify-between border-b">
        <ChevronLeft size={24} />
        <h1 className="text-lg font-medium">포트폴리오</h1>
        <div className="w-6" /> {/* 공간 유지를 위한 빈 요소 */}
      </div>

      {/* 차트 섹션 */}
      <div className="bg-white p-6 mb-2">
        <div className="flex items-center justify-between">
          <div className="w-32 h-32">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={portfolioData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={60}
                  dataKey="value"
                  startAngle={90}
                  endAngle={450}
                >
                  {portfolioData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
              </PieChart>
            </ResponsiveContainer>
          </div>
          <div className="flex-1 ml-8">
            {portfolioData.map((item, index) => (
              <div key={index} className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <div
                    className="w-3 h-3 rounded-sm"
                    style={{ backgroundColor: item.color }}
                  />
                  <span className="text-sm">{item.name}</span>
                </div>
                <span className="text-sm font-medium">{item.value}%</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* 민감도 카드 */}
      <div className="mb-2">
        <SensitivityCard data={stockSensitivity} />
      </div>

      {/* 주식형 섹션 */}
      <div className="px-4 py-4">
        <div className="flex items-baseline gap-2 mb-4">
          <h2 className="text-lg">
            주식형 <span className="text-blue-600">26.4%</span>
          </h2>
          <span className="text-lg font-medium ml-auto">5,974,160원</span>
          <ChevronDown
            size={24}
            className={`transition-transform ${
              expandedSections.stock ? 'rotate-0' : 'rotate-180'
            }`}
            onClick={() => toggleSection('stock')}
          />
        </div>
        {expandedSections.stock &&
          stockAssets.map((asset, index) => (
            <AssetCard key={index} {...asset} />
          ))}
        <SensitivityCard data={stockSensitivity} />
      </div>

      {/* 채권형 섹션 */}
      <div className="px-4 py-4">
        <div className="flex items-baseline gap-2 mb-4">
          <h2 className="text-lg">
            채권형 <span className="text-blue-600">21.7%</span>
          </h2>
          <span className="text-lg font-medium ml-auto">1,066,290원</span>
          <ChevronDown
            size={24}
            className={`transition-transform ${
              expandedSections.bond ? 'rotate-0' : 'rotate-180'
            }`}
            onClick={() => toggleSection('bond')}
          />
        </div>
        {expandedSections.bond &&
          bondAssets.map((asset, index) => (
            <AssetCard key={index} {...asset} />
          ))}
      </div>

      {/* 대체투자 섹션 */}
      <div className="px-4 py-4">
        <div className="flex items-baseline gap-2 mb-4">
          <h2 className="text-lg">
            대체투자 <span className="text-orange-600">17.9%</span>
          </h2>
          <span className="text-lg font-medium ml-auto">1,342,940원</span>
          <ChevronDown
            size={24}
            className={`transition-transform ${
              expandedSections.alternative ? 'rotate-0' : 'rotate-180'
            }`}
            onClick={() => toggleSection('alternative')}
          />
        </div>
        {expandedSections.alternative &&
          alternativeAssets.map((asset, index) => (
            <AssetCard key={index} {...asset} />
          ))}
      </div>

      {/* 현금성 자산 섹션 */}
      <div className="px-4 py-4 pb-8">
        <div className="flex items-baseline gap-2 mb-4">
          <h2 className="text-lg">
            현금성 자산 <span className="text-purple-600">34.1%</span>
          </h2>
          <span className="text-lg font-medium ml-auto">3,261,900원</span>
          <ChevronDown
            size={24}
            className={`transition-transform ${
              expandedSections.cash ? 'rotate-0' : 'rotate-180'
            }`}
            onClick={() => toggleSection('cash')}
          />
        </div>
        {expandedSections.cash &&
          cashAssets.map((asset, index) => (
            <AssetCard key={index} {...asset} />
          ))}
      </div>
    </div>
  );
}