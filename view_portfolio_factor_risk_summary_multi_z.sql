CREATE OR REPLACE VIEW public.view_portfolio_factor_risk_summary_multi_z AS
SELECT DISTINCT
    portfolio_date,
    beta_asof_date,
    method,
    window_days,
    price_interval,
    lookback_window,
    cov_n_obs,
    portfolio_variance_total,
    portfolio_ann_vol_total,
    portfolio_ann_vol_total * 100.0 AS portfolio_ann_vol_total_pct
FROM public.view_portfolio_factor_risk_contrib_multi_z;
