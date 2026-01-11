CREATE OR REPLACE VIEW public.view_portfolio_factor_exposure_multi_z AS
WITH latest_portfolio AS (
    SELECT max(record_date) AS portfolio_date
    FROM public.asset_snapshot
),
positions_holdings AS (
    SELECT
        s.record_date AS portfolio_date,
        h.stock_code,
        COALESCE(m.stock_name, max(h.stock_name)) AS stock_name,
        sum(h.eval_amt)::numeric AS eval_amt
    FROM public.asset_snapshot s
    JOIN latest_portfolio lp
        ON s.record_date = lp.portfolio_date
    JOIN public.asset_holdings h
        ON h.snapshot_id = s.id
    LEFT JOIN public.ticker_category_map m
        ON m.stock_code = h.stock_code
    GROUP BY
        s.record_date,
        h.stock_code,
        m.stock_name
),
positions_cash AS (
    SELECT
        s.record_date AS portfolio_date,
        'CASH'::text AS stock_code,
        '예수금'::text AS stock_name,
        sum(s.total_cash)::numeric AS eval_amt
    FROM public.asset_snapshot s
    JOIN latest_portfolio lp
        ON s.record_date = lp.portfolio_date
    GROUP BY
        s.record_date
),
positions AS (
    SELECT *
    FROM positions_holdings
    UNION ALL
    SELECT *
    FROM positions_cash
    WHERE eval_amt > 0
),
bparams AS (
    SELECT
        max(asof_date) AS beta_asof_date,
        252::int AS window_days,
        '1d'::text AS price_interval,
        '2y'::text AS lookback_window,
        'OLS_MULTI_Z'::text AS method
    FROM public.ticker_factor_beta_long
    WHERE method = 'OLS_MULTI_Z'
      AND window_days = 252
      AND price_interval = '1d'
      AND lookback_window = '2y'
),
betas AS (
    SELECT
        b.stock_code,
        b.factor_code,
        b.beta::numeric AS beta,
        b.r2::numeric AS r2,
        b.n_obs
    FROM public.ticker_factor_beta_long b
    JOIN bparams p
        ON b.asof_date = p.beta_asof_date
    WHERE b.method = p.method
      AND b.window_days = p.window_days
      AND b.price_interval = p.price_interval
      AND b.lookback_window = p.lookback_window
),
factors AS (
    SELECT distinct factor_code
    FROM betas
),
factor_meta AS (
    SELECT
        factor_code,
        factor_name
    FROM public.factor_metadata
),
position_factors AS (
    SELECT
        pos.portfolio_date,
        pos.stock_code,
        pos.stock_name,
        pos.eval_amt,
        f.factor_code
    FROM positions pos
    CROSS JOIN factors f
),
joined AS (
    SELECT
        pf.portfolio_date,
        pf.stock_code,
        pf.stock_name,
        pf.eval_amt,
        pf.factor_code,
        bt.beta,
        bt.r2,
        bt.n_obs
    FROM position_factors pf
    LEFT JOIN betas bt
        ON bt.stock_code = pf.stock_code
       AND bt.factor_code = pf.factor_code
)
SELECT
    j.portfolio_date,
    p.beta_asof_date,
    p.method,
    p.window_days,
    p.price_interval,
    p.lookback_window,
    j.factor_code,
    fm.factor_name,
    count(distinct j.stock_code) AS n_positions_total,
    count(distinct j.stock_code) FILTER (WHERE j.beta IS NOT NULL) AS n_positions_covered,
    sum(j.eval_amt) AS total_eval_amt,
    sum(j.eval_amt) FILTER (WHERE j.beta IS NOT NULL) AS covered_eval_amt,
    round(
        100.0 * sum(j.eval_amt) FILTER (WHERE j.beta IS NOT NULL) / nullif(sum(j.eval_amt), 0),
        2
    ) AS covered_pct,
    sum(j.eval_amt * j.beta) / nullif(sum(j.eval_amt), 0) AS beta_weighted_total,
    sum(j.eval_amt * j.beta) / nullif(sum(j.eval_amt) FILTER (WHERE j.beta IS NOT NULL), 0) AS beta_weighted_covered,
    (sum(j.eval_amt * j.beta) / nullif(sum(j.eval_amt), 0)) * sqrt(252.0) AS ann_vol_total,
    (sum(j.eval_amt * j.beta) / nullif(sum(j.eval_amt) FILTER (WHERE j.beta IS NOT NULL), 0)) * sqrt(252.0) AS ann_vol_covered,
    (sum(j.eval_amt * j.beta) / nullif(sum(j.eval_amt), 0)) * sqrt(252.0) * 100.0 AS ann_sensitivity_total,
    (sum(j.eval_amt * j.beta) / nullif(sum(j.eval_amt) FILTER (WHERE j.beta IS NOT NULL), 0)) * sqrt(252.0) * 100.0 AS ann_sensitivity_covered
FROM joined j
CROSS JOIN bparams p
LEFT JOIN factor_meta fm
    ON fm.factor_code = j.factor_code
WHERE p.beta_asof_date IS NOT NULL
GROUP BY
    j.portfolio_date,
    p.beta_asof_date,
    p.method,
    p.window_days,
    p.price_interval,
    p.lookback_window,
    j.factor_code,
    fm.factor_name
ORDER BY
    j.factor_code;
