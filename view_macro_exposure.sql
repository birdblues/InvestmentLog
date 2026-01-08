DROP VIEW IF EXISTS view_macro_exposure_v2;

CREATE OR REPLACE VIEW view_macro_exposure_v2 AS
WITH daily_summary AS (
    SELECT 
        record_date, 
        SUM(total_asset) as grand_total, 
        SUM(total_cash) as total_cash_sum
    FROM asset_snapshot
    GROUP BY record_date
),
asset_data AS (
    SELECT 
        s.record_date, 
        h.eval_amt, 
        m.tags,
        m.currency
    FROM asset_holdings h
    JOIN asset_snapshot s ON h.snapshot_id = s.id
    LEFT JOIN ticker_category_map m ON h.stock_code = m.stock_code
    
    UNION ALL
    
    SELECT 
        record_date, 
        total_cash_sum, 
        '#현금 #유동성 #금리상승방어 #경기방어 #달러중립 #현금성자산',
        'KRW'
    FROM daily_summary
    WHERE total_cash_sum > 0
)
SELECT 
    a.record_date,
    
    -- =========================================================
    -- [A] 매크로 성향
    -- =========================================================
    -- 1. 경기 민감 (Growth/Cyclical) - 나스닥/성장주 포함
    round(sum(CASE 
        WHEN a.tags LIKE '%#경기민감%' OR a.tags LIKE '%#나스닥%' OR a.tags LIKE '%#성장주%' 
        THEN a.eval_amt ELSE 0 
    END)::numeric / max(t.grand_total) * 100, 2) as macro_cyclical_pct,
    
    -- 2. 경기 방어 (Defensive)
    round(sum(CASE 
        WHEN a.tags LIKE '%#경기방어%' 
        THEN a.eval_amt ELSE 0 
    END)::numeric / max(t.grand_total) * 100, 2) as macro_defensive_pct,
    
    -- 3. 금리 (Rates)
    round(sum(CASE WHEN a.tags LIKE '%#금리인하수혜%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as rate_cut_benefit_pct,
    round(sum(CASE WHEN a.tags LIKE '%#금리상승수혜%' OR a.tags LIKE '%#금리상승방어%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as rate_hike_benefit_pct,

    -- 4. 물가 (Inflation)
    round(sum(CASE 
        WHEN a.tags LIKE '%#인플레방어%' OR a.tags LIKE '%#금%' OR a.tags LIKE '%#에너지%' OR a.tags LIKE '%#원자재%' 
          OR a.tags LIKE '%#부동산%' OR a.tags LIKE '%#리츠%'
          OR a.tags LIKE '%#필수소비재%' OR a.tags LIKE '%#산업재%'
          OR a.tags LIKE '%#가치주%' OR a.tags LIKE '%#배당%'
        THEN a.eval_amt ELSE 0 
    END)::numeric / max(t.grand_total) * 100, 2) as exposure_inflation_pct,

    -- =========================================================
    -- [B] 섹터별 노출도 (나스닥 로직 수정됨 ✅)
    -- =========================================================
    -- IT/테크: 기존(#IT, #테크) + 추가(#나스닥, #기술주, #성장주)
    round(sum(CASE 
        WHEN a.tags LIKE '%#IT%' OR a.tags LIKE '%#테크%' OR a.tags LIKE '%#나스닥%' OR a.tags LIKE '%#기술주%' OR a.tags LIKE '%#반도체%'
        THEN a.eval_amt ELSE 0 
    END)::numeric / max(t.grand_total) * 100, 2) as sector_tech_pct,

    round(sum(CASE WHEN a.tags LIKE '%#금융%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_financial_pct,
    round(sum(CASE WHEN a.tags LIKE '%#헬스케어%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_healthcare_pct,
    round(sum(CASE WHEN a.tags LIKE '%#에너지%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_energy_pct,
    round(sum(CASE WHEN a.tags LIKE '%#소비재%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_consumer_pct,
    round(sum(CASE WHEN a.tags LIKE '%#산업재%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_industrial_pct,
    round(sum(CASE WHEN a.tags LIKE '%#유틸리티%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_utility_pct,
    round(sum(CASE WHEN a.tags LIKE '%#부동산%' OR a.tags LIKE '%#리츠%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as sector_realestate_pct,

    -- =========================================================
    -- [C] 사이즈 팩터
    -- =========================================================
    round(sum(CASE WHEN a.tags LIKE '%#대형주%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as size_large_cap_pct,
    round(sum(CASE WHEN a.tags LIKE '%#소형주%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as size_small_cap_pct,

    -- =========================================================
    -- [D] 통화 및 리스크
    -- =========================================================
    round(sum(CASE WHEN a.currency = 'USD' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as curr_usd_pct,
    round(sum(CASE WHEN a.currency = 'JPY' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as curr_jpy_pct,
    round(sum(CASE WHEN a.currency = 'EUR' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as curr_eur_pct,
    round(sum(CASE WHEN a.tags LIKE '%#엔캐리청산수혜%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as risk_yen_carry_hedge_pct,

    -- =========================================================
    -- [E] 지리적 배분
    -- =========================================================
    round(sum(CASE WHEN a.tags LIKE '%#미국주식%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as geo_us_stock_pct,
    round(sum(CASE WHEN a.tags LIKE '%#국내주식%' OR a.tags LIKE '%#해외주식%' THEN a.eval_amt ELSE 0 END)::numeric / max(t.grand_total) * 100, 2) as geo_ex_us_stock_pct,

    max(t.grand_total) as total_asset_value

FROM asset_data a
JOIN daily_summary t ON a.record_date = t.record_date
GROUP BY a.record_date
ORDER BY a.record_date DESC;