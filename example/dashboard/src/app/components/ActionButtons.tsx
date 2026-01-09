import React from 'react';

export const ActionButtons = () => {
  return (
    <div className="flex gap-3 px-5 pb-8 bg-white">
      <button className="flex-1 py-3.5 bg-blue-50 text-blue-900 font-medium rounded-xl hover:bg-blue-100 transition-colors">
        거래 내역
      </button>
      <button className="flex-1 py-3.5 bg-[#1B2B4B] text-white font-medium rounded-xl hover:bg-[#2a3f6b] transition-colors">
        추가 입금
      </button>
    </div>
  );
};
