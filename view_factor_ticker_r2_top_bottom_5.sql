CREATE OR REPLACE VIEW public.view_factor_ticker_r2_top_bottom_5 AS
WITH latest_factor AS (
    SELECT
        v.factor_code,
        max(v.asof_date) AS asof_date
    FROM public.view_ticker_factor_beta_long_zscore v
    WHERE v.method = 'OLS_SINGLE_Z'
    GROUP BY v.factor_code
),
base AS (
    SELECT
        v.asof_date,
        v.factor_code,
        md.factor_name,
        md.category,
        md.description,
        md.source,
        md.tags,
        v.stock_code,
        m.stock_name,
        v.beta,
        v.r2,
        v.method,
        v.window_days,
        v.price_interval,
        v.lookback_window,
        (v.beta * sqrt(252.0) * 100.0) AS ann_sensitivity
    FROM public.view_ticker_factor_beta_long_zscore v
    JOIN latest_factor lf
      ON v.factor_code = lf.factor_code
     AND v.asof_date = lf.asof_date
    LEFT JOIN public.factor_metadata md
      ON md.factor_code = v.factor_code
    JOIN public.ticker_category_map m
      ON m.stock_code = v.stock_code
    WHERE v.method = 'OLS_SINGLE_Z'
),
ranked AS (
    SELECT
        base.*,
        row_number() OVER (
            PARTITION BY base.factor_code
            ORDER BY base.r2 DESC NULLS LAST
        ) AS rn_top,
        row_number() OVER (
            PARTITION BY base.factor_code
            ORDER BY base.r2 ASC NULLS LAST
        ) AS rn_bottom
    FROM base
)
SELECT
    factor_code,
    factor_name,
    category,
    description,
    source,
    tags,
    asof_date,
    stock_code,
    stock_name,
    beta,
    r2,
    ann_sensitivity,
    method,
    window_days,
    price_interval,
    lookback_window,
    CASE
        WHEN rn_top <= 5 THEN 'top'
        WHEN rn_bottom <= 5 THEN 'bottom'
        ELSE NULL
    END AS bucket,
    CASE
        WHEN rn_top <= 5 THEN rn_top
        WHEN rn_bottom <= 5 THEN rn_bottom
        ELSE NULL
    END AS rank
FROM ranked
WHERE rn_top <= 5 OR rn_bottom <= 5
ORDER BY
    factor_code,
    CASE WHEN rn_top <= 5 THEN 1 ELSE 2 END,
    CASE WHEN rn_top <= 5 THEN rn_top ELSE rn_bottom END;
