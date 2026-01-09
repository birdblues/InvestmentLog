CREATE OR REPLACE VIEW public.view_portfolio_factor_exposure_single_raw AS
WITH holdings AS (
    SELECT
        view_daily_portfolio_final.record_date,
        view_daily_portfolio_final.asset_type,
        view_daily_portfolio_final.tags,
        view_daily_portfolio_final.tag_array,
        view_daily_portfolio_final.country,
        view_daily_portfolio_final.currency_exposure,
        view_daily_portfolio_final.stock_name,
        view_daily_portfolio_final.stock_code,
        view_daily_portfolio_final.total_eval_amt,
        view_daily_portfolio_final.weight_percent,
        view_daily_portfolio_final.total_qty,
        view_daily_portfolio_final.earning_rate
    FROM view_daily_portfolio_final
    WHERE view_daily_portfolio_final.record_date = (
        SELECT max(view_daily_portfolio_final_1.record_date) AS max
        FROM view_daily_portfolio_final view_daily_portfolio_final_1
    )
),
total AS (
    SELECT sum(holdings.total_eval_amt) AS total_eval
    FROM holdings
),
factors AS (
    SELECT
        ticker_factor_beta_long.factor_code,
        max(ticker_factor_beta_long.asof_date) AS asof_date
    FROM ticker_factor_beta_long
    WHERE ticker_factor_beta_long.method = 'OLS_SINGLE'::text
    GROUP BY ticker_factor_beta_long.factor_code
),
factor_meta AS (
    SELECT
        factor_code,
        max(factor_name) AS factor_name
    FROM public.factor_returns
    GROUP BY factor_code
),
beta AS (
    SELECT
        t.asof_date,
        t.window_days,
        t.stock_code,
        t.factor_code,
        t.beta,
        t.r2,
        t.n_obs,
        t.updated_at,
        t.as_of_date,
        t.yf_symbol,
        t.alpha,
        t.method,
        t.created_at,
        t.price_interval,
        t.lookback_window
    FROM ticker_factor_beta_long t
    JOIN factors f_1
        ON t.factor_code = f_1.factor_code
       AND t.asof_date = f_1.asof_date
    WHERE t.method = 'OLS_SINGLE'::text
)
SELECT
    f.factor_code,
    fm.factor_name,
    f.asof_date,
    (SELECT max(holdings.record_date) AS max
     FROM holdings) AS portfolio_date,
    total.total_eval,
    sum(
        CASE
            WHEN b.beta IS NOT NULL THEN h.total_eval_amt
            ELSE 0::numeric
        END
    ) AS covered_eval,
    (sum((COALESCE(b.beta, 0::numeric) * h.total_eval_amt))
        / NULLIF(total.total_eval, 0::numeric)) AS beta_weighted,
    CASE
        WHEN sum(
            CASE
                WHEN b.beta IS NOT NULL THEN h.total_eval_amt
                ELSE 0::numeric
            END
        ) = 0::numeric THEN NULL::numeric
        ELSE (sum((COALESCE(b.beta, 0::numeric) * h.total_eval_amt))
            / sum(
                CASE
                    WHEN b.beta IS NOT NULL THEN h.total_eval_amt
                    ELSE 0::numeric
                END
            ))
    END AS beta_weighted_covered,
    ((sum((COALESCE(b.beta, 0::numeric) * h.total_eval_amt))
        / NULLIF(total.total_eval, 0::numeric)) * sqrt(252.0)) AS ann_vol_total,
    CASE
        WHEN sum(
            CASE
                WHEN b.beta IS NOT NULL THEN h.total_eval_amt
                ELSE 0::numeric
            END
        ) = 0::numeric THEN NULL::numeric
        ELSE ((sum((COALESCE(b.beta, 0::numeric) * h.total_eval_amt))
            / sum(
                CASE
                    WHEN b.beta IS NOT NULL THEN h.total_eval_amt
                    ELSE 0::numeric
                END
            )) * sqrt(252.0))
    END AS ann_vol_covered,
    ((sum((COALESCE(b.beta, 0::numeric) * h.total_eval_amt))
        / NULLIF(total.total_eval, 0::numeric)) * sqrt(252.0) * 100.0) AS ann_sensitivity_total,
    CASE
        WHEN sum(
            CASE
                WHEN b.beta IS NOT NULL THEN h.total_eval_amt
                ELSE 0::numeric
            END
        ) = 0::numeric THEN NULL::numeric
        ELSE ((sum((COALESCE(b.beta, 0::numeric) * h.total_eval_amt))
            / sum(
                CASE
                    WHEN b.beta IS NOT NULL THEN h.total_eval_amt
                    ELSE 0::numeric
                END
            )) * sqrt(252.0) * 100.0)
    END AS ann_sensitivity_covered
FROM factors f
LEFT JOIN factor_meta fm
    ON fm.factor_code = f.factor_code
CROSS JOIN holdings h
LEFT JOIN beta b
    ON b.factor_code = f.factor_code
   AND b.stock_code = h.stock_code
CROSS JOIN total
GROUP BY
    f.factor_code,
    fm.factor_name,
    f.asof_date,
    total.total_eval;
