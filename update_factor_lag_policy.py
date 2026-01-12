#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import re
import datetime as dt
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from pykrx import stock as krx_stock
from supabase import create_client, Client

load_dotenv()

FACTOR_TABLE = "factor_returns"
META_TABLE = "factor_metadata"

DEFAULT_LAG_MIN = -3
DEFAULT_LAG_MAX = 3
DEFAULT_MIN_NOBS = 60


def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def sb_client() -> Client:
    return create_client(env_required("SUPABASE_URL"), env_required("SUPABASE_KEY"))


def sb_select_all(
    base_query,
    page_size: int = 1000,
    max_pages: int = 500,
    max_retries: int = 3,
    retry_sleep_sec: float = 2.0,
) -> List[Dict]:
    all_rows: List[Dict] = []
    for page in range(max_pages):
        frm = page * page_size
        to = frm + page_size - 1
        for attempt in range(1, max_retries + 1):
            try:
                resp = base_query.range(frm, to).execute()
                break
            except Exception as e:
                if attempt >= max_retries:
                    raise
                print(f"[WARN] supabase fetch retry {attempt}/{max_retries}: {e}")
                import time
                time.sleep(retry_sleep_sec)
        rows = resp.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
    return all_rows


def fetch_factor_metadata(sb: Client) -> pd.DataFrame:
    cols = "factor_code,lag_policy_stock_code,frequency"
    rows = sb_select_all(sb.table(META_TABLE).select(cols))
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["factor_code"] = df["factor_code"].astype(str).str.strip()
    df["lag_policy_stock_code"] = df.get("lag_policy_stock_code", "").fillna("").astype(str).str.strip()
    df["frequency"] = df.get("frequency", "").fillna("").astype(str).str.strip().str.upper()
    return df


def fetch_factor_returns(sb: Client, factor_code: str) -> pd.Series:
    q = (
        sb.table(FACTOR_TABLE)
        .select("record_date,ret")
        .eq("factor_code", factor_code)
        .order("record_date", desc=False)
    )
    rows = sb_select_all(q)
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series(dtype=float)
    df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce").dt.date
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")
    df = df.dropna(subset=["record_date", "ret"]).copy()
    if df.empty:
        return pd.Series(dtype=float)
    s = df.set_index("record_date")["ret"].astype(float).sort_index()
    return s


def to_pykrx_code(stock_code: str) -> Optional[str]:
    code = str(stock_code or "").strip().upper()
    if not code:
        return None
    if re.fullmatch(r"Q\d{6}", code):
        return code[1:]
    if re.fullmatch(r"\d{6}", code):
        return code
    if re.fullmatch(r"\d{5}", code):
        return "0" + code
    m = re.search(r"(\d{6})", code)
    if m:
        return m.group(1)
    return None


def log_returns_from_price(px: pd.Series) -> pd.Series:
    px = pd.to_numeric(px, errors="coerce").dropna()
    if px.empty:
        return pd.Series(dtype=float)
    return np.log(px).diff().dropna()


def fetch_ticker_returns_pykrx(
    stock_code: str,
    start_date: dt.date,
    end_date: dt.date,
) -> pd.Series:
    code = to_pykrx_code(stock_code)
    if not code:
        return pd.Series(dtype=float)

    start_s = start_date.strftime("%Y%m%d")
    end_s = end_date.strftime("%Y%m%d")
    try:
        df = krx_stock.get_market_ohlcv_by_date(start_s, end_s, code)
    except Exception:
        return pd.Series(dtype=float)

    if df is None or df.empty:
        return pd.Series(dtype=float)

    col = "종가" if "종가" in df.columns else ("Close" if "Close" in df.columns else None)
    if col is None:
        col = df.columns[0]

    px = pd.to_numeric(df[col], errors="coerce").dropna()
    if px.empty:
        return pd.Series(dtype=float)

    idx = pd.to_datetime(px.index, errors="coerce")
    px.index = idx
    px = px.sort_index()
    px = px[px.index.notna()]
    ret = log_returns_from_price(px)
    ret.index = pd.to_datetime(ret.index).date
    return ret.sort_index()


def ols_beta_r2(y: np.ndarray, x: np.ndarray) -> Tuple[float, float]:
    n = y.shape[0]
    X1 = np.column_stack([np.ones(n), x])
    coef, *_ = np.linalg.lstsq(X1, y, rcond=None)
    beta = float(coef[1])
    y_hat = X1 @ coef
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return beta, r2


def compute_best_lag(
    factor_ret: pd.Series,
    ticker_ret: pd.Series,
    lags: List[int],
    min_nobs: int,
) -> Tuple[Optional[Dict], List[Dict]]:
    results: List[Dict] = []
    for lag in lags:
        aligned = factor_ret.shift(lag)
        df = pd.concat([aligned.rename("x"), ticker_ret.rename("y")], axis=1).dropna()
        n_obs = len(df)
        if n_obs < min_nobs:
            continue
        beta, r2 = ols_beta_r2(df["y"].values.astype(float), df["x"].values.astype(float))
        if not np.isfinite(beta) or not np.isfinite(r2):
            continue
        results.append({
            "lag": lag,
            "beta": beta,
            "r2": r2,
            "n_obs": n_obs,
        })

    if not results:
        return None, results

    best = sorted(results, key=lambda r: (r["r2"], abs(r["beta"])), reverse=True)[0]
    return best, results


def update_lag_policy(sb: Client, factor_code: str, lag: int) -> None:
    sb.table(META_TABLE).update({"lag_policy": str(lag)}).eq("factor_code", factor_code).execute()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Select best lag_policy per factor using a reference ticker and update factor_metadata."
    )
    parser.add_argument("--lag-min", type=int, default=DEFAULT_LAG_MIN)
    parser.add_argument("--lag-max", type=int, default=DEFAULT_LAG_MAX)
    parser.add_argument("--min-nobs", type=int, default=DEFAULT_MIN_NOBS)
    parser.add_argument("--factor-codes", type=str, default="")
    parser.add_argument("--dry-run", action="store_true", help="Print results without updating factor_metadata.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    lag_min = args.lag_min
    lag_max = args.lag_max
    lags = list(range(lag_min, lag_max + 1))
    min_nobs = args.min_nobs
    dry_run = args.dry_run

    target_factor_codes = [
        c.strip() for c in args.factor_codes.split(",") if c.strip()
    ]

    sb = sb_client()
    meta = fetch_factor_metadata(sb)
    if meta.empty:
        print("[WARN] factor_metadata is empty")
        return

    if target_factor_codes:
        meta = meta[meta["factor_code"].isin(target_factor_codes)].copy()
        if meta.empty:
            print("[WARN] no matching factor_codes in factor_metadata")
            return

    meta = meta[meta["lag_policy_stock_code"].astype(str).str.strip() != ""].copy()
    if meta.empty:
        print("[WARN] no factors have lag_policy_stock_code set")
        return

    ticker_cache: Dict[str, Tuple[pd.Series, Optional[dt.date], Optional[dt.date]]] = {}

    for _, row in meta.iterrows():
        factor_code = row["factor_code"]
        stock_code = row["lag_policy_stock_code"]
        frequency = row.get("frequency", "")

        if frequency == "M":
            print(f"[SKIP] {factor_code} frequency=M")
            continue

        factor_ret = fetch_factor_returns(sb, factor_code)

        if factor_ret.empty:
            print(f"[WARN] {factor_code} factor_returns empty")
            continue

        start_date = min(factor_ret.index)
        end_date = max(factor_ret.index)
        cached = ticker_cache.get(stock_code)
        if cached:
            cached_series, cached_start, cached_end = cached
            if cached_start and cached_end and cached_start <= start_date and cached_end >= end_date:
                ticker_ret = cached_series.loc[start_date:end_date].copy()
            else:
                fetch_start = min(filter(None, [cached_start, start_date]))
                fetch_end = max(filter(None, [cached_end, end_date]))
                fetched = fetch_ticker_returns_pykrx(stock_code, fetch_start, fetch_end)
                ticker_cache[stock_code] = (fetched, fetch_start, fetch_end)
                ticker_ret = fetched.loc[start_date:end_date].copy()
        else:
            fetched = fetch_ticker_returns_pykrx(stock_code, start_date, end_date)
            ticker_cache[stock_code] = (fetched, start_date, end_date)
            ticker_ret = fetched

        if ticker_ret.empty:
            print(f"[WARN] {factor_code} ticker_returns empty (pykrx:{stock_code})")
            continue

        best, results = compute_best_lag(
            factor_ret=factor_ret,
            ticker_ret=ticker_ret,
            lags=lags,
            min_nobs=min_nobs,
        )
        if not best:
            print(f"[WARN] {factor_code} no valid lag (min_nobs={min_nobs})")
            continue

        print(
            f"[INFO] {factor_code} stock={stock_code} best_lag={best['lag']} "
            f"r2={best['r2']:.4f} beta={best['beta']:.4f} n_obs={best['n_obs']}"
        )
        if not dry_run:
            update_lag_policy(sb, factor_code, best["lag"])


if __name__ == "__main__":
    main()
