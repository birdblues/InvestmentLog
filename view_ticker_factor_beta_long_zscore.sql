-- Z-score based betas only
CREATE OR REPLACE VIEW public.view_ticker_factor_beta_long_zscore AS
SELECT *
FROM public.ticker_factor_beta_long
WHERE method IN ('OLS_MULTI_Z', 'OLS_SINGLE_Z');
