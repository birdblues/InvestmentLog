CREATE OR REPLACE VIEW public.view_portfolio_factor_risk_contrib_multi_raw AS
WITH latest AS (
    SELECT max(portfolio_date) AS portfolio_date
    FROM public.view_portfolio_factor_exposure_multi_raw
),
exposures AS (
    SELECT *
    FROM public.view_portfolio_factor_exposure_multi_raw
    WHERE portfolio_date = (SELECT portfolio_date FROM latest)
),
params AS (
    SELECT
        max(beta_asof_date) AS beta_asof_date,
        max(method) AS method,
        max(window_days) AS window_days,
        max(price_interval) AS price_interval,
        max(lookback_window) AS lookback_window
    FROM exposures
),
factor_count AS (
    SELECT count(*) AS n_factors
    FROM exposures
),
dates_raw AS (
    SELECT fr.record_date
    FROM public.factor_returns fr
    JOIN exposures e
        ON e.factor_code = fr.factor_code
    CROSS JOIN params p
    WHERE fr.record_date <= p.beta_asof_date
    GROUP BY fr.record_date
    HAVING count(distinct fr.factor_code) = (SELECT n_factors FROM factor_count)
    ORDER BY fr.record_date DESC
),
dates AS (
    SELECT record_date
    FROM dates_raw
    LIMIT 252
),
n_obs AS (
    SELECT count(*) AS n_obs
    FROM dates
),
returns AS (
    SELECT
        fr.record_date,
        fr.factor_code,
        fr.ret
    FROM public.factor_returns fr
    JOIN dates d
        ON d.record_date = fr.record_date
    JOIN exposures e
        ON e.factor_code = fr.factor_code
),
means AS (
    SELECT
        factor_code,
        avg(ret) AS mean_ret
    FROM returns
    GROUP BY factor_code
),
cov AS (
    SELECT
        r1.factor_code AS factor_i,
        r2.factor_code AS factor_j,
        sum((r1.ret - m1.mean_ret) * (r2.ret - m2.mean_ret))
            / nullif(n_obs.n_obs - 1, 0) AS cov
    FROM returns r1
    JOIN returns r2
        ON r1.record_date = r2.record_date
    JOIN means m1
        ON m1.factor_code = r1.factor_code
    JOIN means m2
        ON m2.factor_code = r2.factor_code
    CROSS JOIN n_obs
    GROUP BY r1.factor_code, r2.factor_code, n_obs.n_obs
),
b AS (
    SELECT
        factor_code,
        coalesce(beta_weighted_total, 0) AS beta_weighted_total
    FROM exposures
),
mrc AS (
    SELECT
        c.factor_i AS factor_code,
        sum(c.cov * b.beta_weighted_total) AS mrc
    FROM cov c
    JOIN b
        ON b.factor_code = c.factor_j
    GROUP BY c.factor_i
),
var_total AS (
    SELECT sum(b.beta_weighted_total * m.mrc) AS var_total
    FROM b
    JOIN mrc m
        ON m.factor_code = b.factor_code
)
SELECT
    e.portfolio_date,
    e.beta_asof_date,
    e.method,
    e.window_days,
    e.price_interval,
    e.lookback_window,
    e.factor_code,
    e.factor_name,
    e.n_positions_total,
    e.n_positions_covered,
    e.total_eval_amt,
    e.covered_eval_amt,
    e.covered_pct,
    e.beta_weighted_total,
    b.beta_weighted_total AS beta_weighted_total_used,
    e.beta_weighted_covered,
    e.ann_vol_total,
    e.ann_vol_covered,
    e.ann_sensitivity_total,
    e.ann_sensitivity_covered,
    n_obs.n_obs AS cov_n_obs,
    vt.var_total AS portfolio_variance_total,
    sqrt(vt.var_total * 252.0) AS portfolio_ann_vol_total,
    m.mrc AS marginal_var_contrib,
    (b.beta_weighted_total * m.mrc) AS var_contrib,
    100.0 * (b.beta_weighted_total * m.mrc) / nullif(vt.var_total, 0) AS var_contrib_pct
FROM exposures e
JOIN b
    ON b.factor_code = e.factor_code
JOIN mrc m
    ON m.factor_code = e.factor_code
CROSS JOIN n_obs
CROSS JOIN var_total vt
ORDER BY
    e.factor_code;
