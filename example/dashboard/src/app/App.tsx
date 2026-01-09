import React from 'react';
import { Header } from './components/Header';
import { AssetSummary } from './components/AssetSummary';
import { ActionButtons } from './components/ActionButtons';
import { ValuationChart } from './components/ValuationChart';
import { PortfolioCard } from './components/PortfolioCard';

export default function App() {
  return (
    <div className="min-h-screen bg-gray-100 flex justify-center">
      <div className="w-full max-w-md bg-white min-h-screen shadow-xl overflow-hidden flex flex-col">
        <Header />
        
        <div className="flex-1 overflow-y-auto no-scrollbar">
          <AssetSummary />
          <ActionButtons />
          
          {/* Divider */}
          <div className="h-2 bg-gray-50 w-full" />
          
          <ValuationChart />

          {/* Divider */}
          <div className="h-2 bg-gray-50 w-full" />

          <PortfolioCard />
        </div>
      </div>
    </div>
  );
}
