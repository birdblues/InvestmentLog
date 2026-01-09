CREATE OR REPLACE VIEW public.view_portfolio_factor_exposure_single_z_summary AS
SELECT
    factor_code,
    factor_name,
    asof_date,
    portfolio_date,
    ann_sensitivity_total,
    ann_sensitivity_covered
FROM public.view_portfolio_factor_exposure_single_z;
