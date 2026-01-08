#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ticker_factor_beta_loader.py (FULL REPLACE)

[목표]
- ticker_category_map 종목들에 대해 (yfinance) 가격 로그수익률을 만들고
- factor_returns(일간 ret)과 결합하여 멀티 OLS로 팩터 베타를 계산한 뒤
- ticker_factor_beta_long에 upsert
- beta_run_report.csv 리포트 생성

[전제/하드코딩]
- 팩터 테이블: factor_returns
- 베타 테이블: ticker_factor_beta_long
- 티커 맵 테이블: ticker_category_map
- factor_returns는 record_date(date), factor_code(text), ret(numeric), frequency(text='D') 를 사용
- ticker_factor_beta_long은 사용자가 준 컬럼 기준으로 payload 맞춤

[중요 변경점]
- "팩터가 늘수록 교집합 날짜가 급감" 문제 방지:
  - join 후 전체 dropna()를 하지 않고,
  - 팩터별 overlap(티커 수익률과 동시에 존재하는 날짜 수)을 계산해
    MIN_NOBS 이상인 팩터만 회귀에 사용(ok_factors)
- PostgREST limit(보통 1000) 이슈 방지:
  - factor_returns는 factor_code별로 개별 pagination해서 모두 가져옴

Env:
  SUPABASE_URL=...
  SUPABASE_KEY=...
  FACTOR_RET_SOURCE=raw|zscore (optional, default=raw)

실행:
  uv run python ticker_factor_beta_loader.py
"""

from __future__ import annotations

import os
import re
import datetime as dt
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv
from supabase import create_client, Client
try:
    from pykrx import stock as krx_stock
except Exception:  # optional dependency
    krx_stock = None

load_dotenv(override=False)


# -----------------------------
# Hardcoded table names
# -----------------------------
TICKER_MAP_TABLE = "ticker_category_map"
BETA_TABLE = "ticker_factor_beta_long"

FACTOR_RET_SOURCE = os.getenv("FACTOR_RET_SOURCE", "raw").strip().lower()
if FACTOR_RET_SOURCE not in ("raw", "zscore"):
    raise RuntimeError(f"Invalid FACTOR_RET_SOURCE: {FACTOR_RET_SOURCE}")

if FACTOR_RET_SOURCE == "zscore":
    FACTOR_TABLE = "view_factor_returns_zscore"
    FACTOR_RET_COLUMN = "ret_z"
    METHOD_MULTI = "OLS_MULTI_Z"
    METHOD_SINGLE = "OLS_SINGLE_Z"
else:
    FACTOR_TABLE = "factor_returns"
    FACTOR_RET_COLUMN = "ret"
    METHOD_MULTI = "OLS_MULTI"
    METHOD_SINGLE = "OLS_SINGLE"

# -----------------------------
# Runtime config (hardcoded)
# -----------------------------
PRICE_INTERVAL = "1d"
LOOKBACK_WINDOW = "2y"          # yfinance period
WINDOW_DAYS = 252               # 회귀에 사용할 최대 관측치(대략 1년 영업일)
MIN_NOBS = 60                   # 최소 관측치
UPSERT_CHUNK_SIZE = 500

REPORT_CSV_PATH = "./beta_run_report.csv"


LAG_POLICY_DEFAULT = 0


# -----------------------------
# Utilities
# -----------------------------
def env_required(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v


def now_utc_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _ensure_series(x) -> pd.Series:
    """
    yfinance 결과에서 df[col]이 DataFrame으로 나오는 케이스 방어.
    """
    if isinstance(x, pd.Series):
        return x
    if isinstance(x, pd.DataFrame):
        if x.shape[1] >= 1:
            return x.iloc[:, 0]
    raise TypeError("Expected 1-d Series-like object for price column")


def log_returns_from_price(px: pd.Series) -> pd.Series:
    px = px.dropna().astype(float)
    px = px[px > 0]
    r = (np.log(px) - np.log(px.shift(1))).dropna()
    return r


def lookback_window_to_days(window: str) -> int:
    w = (window or "").strip().lower()
    m = re.fullmatch(r"(\d+)\s*(d|day|days|mo|m|mon|month|months|y|yr|year|years)", w)
    if not m:
        return 730
    n = int(m.group(1))
    unit = m.group(2)
    if unit in ("d", "day", "days"):
        return n
    if unit in ("mo", "m", "mon", "month", "months"):
        return n * 30
    if unit in ("y", "yr", "year", "years"):
        return n * 365
    return 730


# -----------------------------
# Supabase helpers
# -----------------------------
def sb_client() -> Client:
    url = env_required("SUPABASE_URL")
    key = env_required("SUPABASE_KEY")
    return create_client(url, key)


def sb_select_all(base_query, page_size: int = 1000, max_pages: int = 500) -> List[Dict]:
    """
    PostgREST range pagination
    """
    all_rows: List[Dict] = []
    for page in range(max_pages):
        frm = page * page_size
        to = frm + page_size - 1
        resp = base_query.range(frm, to).execute()
        rows = resp.data or []
        if not rows:
            break
        all_rows.extend(rows)
        if len(rows) < page_size:
            break
    return all_rows


def parse_lag_policy(policy: Optional[str]) -> int:
    if not policy:
        return LAG_POLICY_DEFAULT
    match = re.search(r"[-+]?\d+", str(policy))
    if not match:
        return LAG_POLICY_DEFAULT
    try:
        return int(match.group())
    except ValueError:
        return LAG_POLICY_DEFAULT


# -----------------------------
# Fetch ticker universe
# -----------------------------
def fetch_all_tickers(sb: Client) -> pd.DataFrame:
    cols = "stock_code,stock_name,yf_symbol,yf_status"
    q = sb.table(TICKER_MAP_TABLE).select(cols).order("stock_code", desc=False)
    rows = sb_select_all(q, page_size=1000, max_pages=200)

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["stock_code"] = df["stock_code"].astype(str).str.strip()
    df["stock_name"] = df.get("stock_name", "").fillna("").astype(str).str.strip()
    df["yf_symbol"] = df.get("yf_symbol", "").fillna("").astype(str).str.strip()
    df["yf_status"] = df.get("yf_status", "").fillna("").astype(str).str.strip()
    return df


# -----------------------------
# Yahoo symbol candidates
# -----------------------------
def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def is_krx_6digits(code: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", code))


def is_krx_6alnum(code: str) -> bool:
    # 0005D0 같은 6자리 영숫자 (Yahoo에서 .KS로 잡히는 케이스)
    return bool(re.fullmatch(r"[0-9A-Z]{6}", code)) and (not is_krx_6digits(code))


def pad_krx_code(code: str) -> Optional[str]:
    if re.fullmatch(r"\d{5}", code):
        return "0" + code
    return None


def to_pykrx_code(stock_code: str) -> Optional[str]:
    code = normalize_code(stock_code)
    if re.fullmatch(r"Q(\d{6})", code):
        return code[1:]
    if is_krx_6digits(code):
        return code
    padded = pad_krx_code(code)
    if padded:
        return padded
    return None


def generate_candidates(stock_code: str, yf_symbol: str = "") -> Tuple[List[str], str]:
    code = normalize_code(stock_code)

    if code == "CASH":
        return [], "skip:cash"

    if yf_symbol:
        sym = yf_symbol.strip()
        if sym:
            return [sym], "prefer:yf_symbol"

    if code.endswith(".KS") or code.endswith(".KQ"):
        return [code], "given:suffixed"

    cands: List[str] = []
    notes: List[str] = []

    if is_krx_6digits(code):
        cands += [f"{code}.KS", f"{code}.KQ"]
        notes.append("rule:6digits->KS/KQ")

    padded = pad_krx_code(code)
    if padded:
        cands += [f"{padded}.KS", f"{padded}.KQ"]
        notes.append("rule:5digits->0pad->KS/KQ")

    m = re.fullmatch(r"Q(\d{6})", code)
    if m:
        core = m.group(1)
        cands += [f"{core}.KS", f"{core}.KQ", f"{code}.KS", f"{code}.KQ"]
        notes.append("rule:Q+6digits->stripQ + original")

    if is_krx_6alnum(code):
        cands += [f"{code}.KS", f"{code}.KQ"]
        notes.append("rule:6alnum->KS/KQ")

    m2 = re.search(r"(\d{6})", code)
    if m2 and not is_krx_6digits(code):
        core = m2.group(1)
        cands += [f"{core}.KS", f"{core}.KQ"]
        notes.append("rule:extract_6digits->KS/KQ")

    # dedup
    out: List[str] = []
    seen = set()
    for s in cands:
        if s not in seen:
            seen.add(s)
            out.append(s)

    if not out:
        notes.append("no_candidates")

    return out, ";".join(notes)


# -----------------------------
# Price returns (yfinance)
# -----------------------------
def fetch_price_returns_yf(symbol: str, end_date: dt.date) -> Optional[pd.Series]:
    """
    - Adj Close 우선, 없으면 Close
    - index -> date로 정규화
    """
    try:
        df = yf.download(
            symbol,
            period=LOOKBACK_WINDOW,
            interval=PRICE_INTERVAL,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception:
        return None

    if df is None or df.empty:
        return None

    col = "Adj Close" if "Adj Close" in df.columns else ("Close" if "Close" in df.columns else None)
    if col is None:
        return None

    px = _ensure_series(df[col])
    px = pd.to_numeric(px, errors="coerce").dropna()
    if px.empty or len(px) < (MIN_NOBS + 5):
        return None

    idx = pd.to_datetime(px.index, errors="coerce")
    px.index = idx
    px = px.sort_index()
    px = px[px.index.notna()]

    px = px[px.index.date <= end_date]
    if px.empty or len(px) < (MIN_NOBS + 5):
        return None

    ret = log_returns_from_price(px)
    ret.index = pd.to_datetime(ret.index).date
    ret = ret.sort_index()
    return ret


def fetch_price_returns_krx(stock_code: str, end_date: dt.date) -> Optional[pd.Series]:
    if krx_stock is None:
        return None
    code = to_pykrx_code(stock_code)
    if not code:
        return None

    lookback_days = lookback_window_to_days(LOOKBACK_WINDOW)
    start_date = end_date - dt.timedelta(days=lookback_days + 7)
    start_s = start_date.strftime("%Y%m%d")
    end_s = end_date.strftime("%Y%m%d")

    try:
        df = krx_stock.get_market_ohlcv_by_date(start_s, end_s, code)
    except Exception:
        return None
    if df is None or df.empty:
        return None

    col = "종가" if "종가" in df.columns else ("Close" if "Close" in df.columns else None)
    if col is None:
        col = df.columns[0]

    px = pd.to_numeric(df[col], errors="coerce").dropna()
    if px.empty or len(px) < (MIN_NOBS + 5):
        return None

    idx = pd.to_datetime(px.index, errors="coerce")
    px.index = idx
    px = px.sort_index()
    px = px[px.index.notna()]
    px = px[px.index.date <= end_date]
    if px.empty or len(px) < (MIN_NOBS + 5):
        return None

    ret = log_returns_from_price(px)
    ret.index = pd.to_datetime(ret.index).date
    ret = ret.sort_index()
    return ret


# -----------------------------
# Factor returns (Supabase) - factor별 pagination (핵심)
# -----------------------------
def fetch_factor_returns_one(
    sb: Client,
    factor_code: str,
    end_date: dt.date,
    start_date: Optional[dt.date] = None,
    page_size: int = 1000,
    max_pages: int = 500,
) -> pd.DataFrame:
    q = (
        sb.table(FACTOR_TABLE)
        .select(f"factor_code,record_date,{FACTOR_RET_COLUMN},frequency,lag_policy")
        .eq("factor_code", factor_code)
        .lte("record_date", end_date.isoformat())
        .order("record_date", desc=False)
    )
    if start_date is not None:
        q = q.gte("record_date", start_date.isoformat())

    rows = sb_select_all(q, page_size=page_size, max_pages=max_pages)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if FACTOR_RET_COLUMN != "ret" and FACTOR_RET_COLUMN in df.columns:
        df = df.rename(columns={FACTOR_RET_COLUMN: "ret"})

    df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce").dt.date
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")
    df = df.dropna(subset=["factor_code", "record_date", "ret"]).copy()
    return df


def expand_monthly_to_daily_ret(
    df: pd.DataFrame,
    end_date: dt.date,
    start_date: Optional[dt.date] = None,
    release_lag_months: int = 1,
) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["factor_code", "record_date", "ret", "frequency", "lag_policy"])

    df = df.copy()
    df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce")
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")
    df = df.dropna(subset=["record_date", "ret"]).copy()
    if df.empty:
        return pd.DataFrame(columns=["factor_code", "record_date", "ret", "frequency", "lag_policy"])

    release_dates = (df["record_date"] + pd.DateOffset(months=release_lag_months)).dt.date
    ret_map = {
        d: float(r)
        for d, r in zip(release_dates, df["ret"])
        if pd.notna(r)
    }
    if not ret_map:
        return pd.DataFrame(columns=["factor_code", "record_date", "ret", "frequency", "lag_policy"])

    start = start_date or min(ret_map.keys())
    start = max(start, min(ret_map.keys()))
    if start > end_date:
        return pd.DataFrame(columns=["factor_code", "record_date", "ret", "frequency", "lag_policy"])

    idx = pd.date_range(start=start, end=end_date, freq="D")
    ret_series = pd.Series(0.0, index=idx.date)
    for d, r in ret_map.items():
        if d in ret_series.index:
            ret_series.loc[d] = r

    factor_code = df["factor_code"].iloc[0]
    lag_policy = None
    if "lag_policy" in df.columns:
        non_null = df["lag_policy"].dropna()
        if not non_null.empty:
            lag_policy = non_null.iloc[0]
    return pd.DataFrame({
        "factor_code": factor_code,
        "record_date": ret_series.index,
        "ret": ret_series.values,
        "frequency": "D",
        "lag_policy": lag_policy,
    })


def fetch_factor_returns(
    sb: Client,
    factor_codes: List[str],
    end_date: dt.date,
    start_date: Optional[dt.date] = None,
) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for fc in factor_codes:
        dfi = fetch_factor_returns_one(sb, fc, end_date=end_date, start_date=start_date)
        if fc == "F_INFL_KR_CPI":
            dfi = expand_monthly_to_daily_ret(dfi, end_date=end_date, start_date=start_date)
        else:
            dfi = dfi[dfi["frequency"] == "D"].copy()
        if not dfi.empty:
            frames.append(dfi)
    if not frames:
        return pd.DataFrame(columns=["factor_code", "record_date", "ret", "frequency"])
    return pd.concat(frames, ignore_index=True)


def apply_factor_lags(fdf: pd.DataFrame) -> pd.DataFrame:
    """
    factor_code별로 lag를 적용해서 aligned_ret 생성
    - lag=1이면 factor의 t일 값이 ticker의 t+1일에 대응하도록 shift(1)
    """
    if fdf.empty:
        return fdf

    out = fdf.copy()
    out = out.sort_values(["factor_code", "record_date"])
    out["aligned_ret"] = np.nan

    has_lag_policy = "lag_policy" in out.columns
    for fc, g in out.groupby("factor_code", sort=False):
        lag_policy = None
        if has_lag_policy:
            non_null = g["lag_policy"].dropna()
            if not non_null.empty:
                lag_policy = non_null.iloc[0]
        lag = parse_lag_policy(lag_policy)
        s = g["ret"].astype(float)
        out.loc[g.index, "aligned_ret"] = s.shift(lag).values

    out = out.dropna(subset=["aligned_ret"]).copy()
    return out


# -----------------------------
# Regression (multi OLS)
# -----------------------------
def ols_multi(y: np.ndarray, X: np.ndarray) -> Tuple[np.ndarray, float, float]:
    n = y.shape[0]
    X1 = np.column_stack([np.ones(n), X])
    coef, *_ = np.linalg.lstsq(X1, y, rcond=None)

    alpha = float(coef[0])
    beta = coef[1:].astype(float)

    y_hat = X1 @ coef
    ss_res = float(np.sum((y - y_hat) ** 2))
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return beta, alpha, r2


# -----------------------------
# Upsert betas
# -----------------------------
def upsert_beta_rows(sb: Client, rows: List[Dict]) -> None:
    if not rows:
        return
    for i in range(0, len(rows), UPSERT_CHUNK_SIZE):
        chunk = rows[i : i + UPSERT_CHUNK_SIZE]
        sb.table(BETA_TABLE).upsert(
            chunk,
            on_conflict="asof_date,window_days,stock_code,factor_code,method,price_interval,lookback_window",
        ).execute()


# -----------------------------
# Main
# -----------------------------
def main():
    sb = sb_client()

    print(f"[INFO] factor_returns source={FACTOR_RET_SOURCE} table={FACTOR_TABLE} ret_col={FACTOR_RET_COLUMN}")

    # 베타 asof: "마감된 마지막 날짜" (단순히 로컬 -1)
    today = dt.date.today()
    end = today - dt.timedelta(days=1)

    tickers = fetch_all_tickers(sb)
    if tickers.empty:
        raise RuntimeError("ticker_category_map is empty")

    # ✅ 기본 팩터 목록 (원하면 여기에 더 추가/삭제)
    factor_codes = [
        "F_GROWTH_US_EQ",
        "F_RATE_US10Y",
        "F_RATE_KR10Y",
        "F_CURR_USDKRW",
        "F_VOL_VIX",
        "F_CREDIT_US_HY_OAS",
        "F_INFL_US_BE10Y",
        "F_COMM_OIL_WTI",
        # "F_INFL_KR_CPI",  # 월간 CPI는 일단 베타 계산에서 제외
    ]

    # factor는 최근 구간만 필요: 2y + buffer
    start_date = end - dt.timedelta(days=365 * 2 + 120)

    fdf_raw = fetch_factor_returns(sb, factor_codes=factor_codes, end_date=end, start_date=start_date)
    present = sorted(fdf_raw["factor_code"].unique().tolist()) if not fdf_raw.empty else []
    missing_in_db = [c for c in factor_codes if c not in present]

    fdf = apply_factor_lags(fdf_raw)

    # 날짜 x factor wide (aligned_ret)
    if not fdf.empty:
        fwide = (
            fdf.pivot_table(index="record_date", columns="factor_code", values="aligned_ret", aggfunc="last")
            .sort_index()
        )
    else:
        fwide = pd.DataFrame()

    report_rows: List[Dict] = []
    upsert_rows: List[Dict] = []

    for _, r in tickers.iterrows():
        stock_code = str(r.get("stock_code", "")).strip()
        stock_name = str(r.get("stock_name", "")).strip()
        yf_symbol = str(r.get("yf_symbol", "")).strip()

        if stock_code.upper() == "CASH":
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "SKIP",
                "reason": "cash",
                "used_symbol": "",
                "asof_date": "",
                "n_obs": 0,
                "ok_factors": "",
                "skipped_factors": "",
                "single_ok_factors": "",
                "single_skipped_factors": "",
                "single_failed_factors": "",
                "single_status_map": "",
                "single_n_obs_map": "",
            })
            continue

        candidates, note = generate_candidates(stock_code, yf_symbol=yf_symbol)
        if not candidates:
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "SKIP",
                "reason": f"no_yf_candidates({note})",
                "used_symbol": "",
                "asof_date": "",
                "n_obs": 0,
                "ok_factors": "",
                "skipped_factors": "",
                "single_ok_factors": "",
                "single_skipped_factors": "",
                "single_failed_factors": "",
                "single_status_map": "",
                "single_n_obs_map": "",
            })
            continue

        used_symbol = ""
        ret_t: Optional[pd.Series] = None

        ret_t = fetch_price_returns_krx(stock_code, end_date=end)
        if ret_t is not None and not ret_t.empty:
            used_symbol = f"KRX:{to_pykrx_code(stock_code)}"

        if ret_t is None or ret_t.empty:
            for sym in candidates:
                ret_t = fetch_price_returns_yf(sym, end_date=end)
                if ret_t is not None and not ret_t.empty:
                    used_symbol = sym
                    break

        if ret_t is None or ret_t.empty:
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "SKIP",
                "reason": "price_empty",
                "used_symbol": candidates[0] if candidates else "",
                "asof_date": "",
                "n_obs": 0,
                "ok_factors": "",
                "skipped_factors": "",
                "single_ok_factors": "",
                "single_skipped_factors": "",
                "single_failed_factors": "",
                "single_status_map": "",
                "single_n_obs_map": "",
            })
            continue

        if fwide.empty:
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "SKIP",
                "reason": "no_factors_in_db",
                "used_symbol": used_symbol,
                "asof_date": "",
                "n_obs": 0,
                "ok_factors": "",
                "skipped_factors": "",
                "single_ok_factors": "",
                "single_skipped_factors": "",
                "single_failed_factors": "",
                "single_status_map": "",
                "single_n_obs_map": "",
            })
            continue

        # join (여기서 전체 dropna() 절대 하지 않음!)
        df = pd.DataFrame({"ret_t": ret_t})
        df.index.name = "record_date"
        df = df.join(fwide, how="inner")

        # 실제 존재하는 factor만
        available_factors = [c for c in factor_codes if c in df.columns]

        # -----------------------------
        # Single-factor regressions
        # -----------------------------
        single_status_parts: List[str] = []
        single_n_obs_parts: List[str] = []
        single_ok_factors: List[str] = []
        single_skipped_factors: List[str] = []
        single_failed_factors: List[str] = []

        updated_at = now_utc_iso()
        created_at = updated_at

        for fc in available_factors:
            df_single = df[["ret_t", fc]].dropna()

            if len(df_single) > WINDOW_DAYS:
                df_single = df_single.iloc[-WINDOW_DAYS:].copy()

            n_obs_single = int(df_single.shape[0])
            single_n_obs_parts.append(f"{fc}:{n_obs_single}")

            if n_obs_single < MIN_NOBS:
                single_skipped_factors.append(fc)
                single_status_parts.append(f"{fc}:THIN")
                continue

            y_single = df_single["ret_t"].astype(float).values
            X_single = df_single[[fc]].astype(float).values

            try:
                beta_single, alpha_single, r2_single = ols_multi(y_single, X_single)
            except Exception:
                single_failed_factors.append(fc)
                single_status_parts.append(f"{fc}:FAIL")
                continue

            asof_date_single = df_single.index.max()
            if isinstance(asof_date_single, (pd.Timestamp, dt.datetime)):
                asof_date_single = asof_date_single.date()
            if not isinstance(asof_date_single, dt.date):
                asof_date_single = end

            upsert_rows.append({
                "asof_date": asof_date_single.isoformat(),
                "window_days": int(WINDOW_DAYS),
                "stock_code": stock_code,
                "factor_code": fc,

                "beta": float(beta_single[0]) if np.isfinite(beta_single[0]) else None,
                "r2": float(r2_single) if np.isfinite(r2_single) else None,
                "n_obs": int(n_obs_single),

                "updated_at": updated_at,
                "as_of_date": None,          # 혼동 컬럼 비움
                "yf_symbol": used_symbol,
                "alpha": float(alpha_single) if np.isfinite(alpha_single) else None,
                "method": METHOD_SINGLE,
                "created_at": created_at,
                "price_interval": PRICE_INTERVAL,
                "lookback_window": LOOKBACK_WINDOW,
            })

            single_ok_factors.append(fc)
            single_status_parts.append(f"{fc}:OK")

        # ✅ 팩터별 overlap(티커 수익률과 동시에 존재하는 날짜 수) 계산
        ok_factors: List[str] = []
        overlap_map: Dict[str, int] = {}
        for fc in available_factors:
            tmp = df[["ret_t", fc]].dropna()
            overlap = int(tmp.shape[0])
            overlap_map[fc] = overlap
            if overlap >= MIN_NOBS:
                ok_factors.append(fc)

        skipped_factors = [fc for fc in factor_codes if fc not in ok_factors]

        multi_status = "SKIP"
        multi_reason = f"no_factor_overlap(min_nobs={MIN_NOBS}) missing_in_db={missing_in_db}"
        multi_asof_date = ""
        multi_n_obs = 0

        if ok_factors:
            # 회귀용 데이터: ret_t + ok_factors만 subset dropna
            need_cols = ["ret_t"] + ok_factors
            df2 = df[need_cols].dropna().copy()

            # window 제한 (최근 WINDOW_DAYS)
            if len(df2) > WINDOW_DAYS:
                df2 = df2.iloc[-WINDOW_DAYS:].copy()

            multi_n_obs = int(df2.shape[0])
            if multi_n_obs < MIN_NOBS:
                multi_reason = (
                    f"thin(n_obs={multi_n_obs}) "
                    f"ok_factors={len(ok_factors)} skipped_factors={len(skipped_factors)}"
                )
            else:
                # 회귀
                y = df2["ret_t"].astype(float).values
                X = df2[ok_factors].astype(float).values

                try:
                    beta, alpha, r2 = ols_multi(y, X)
                except Exception as e:
                    multi_status = "FAIL"
                    multi_reason = f"ols_exception:{e}"
                else:
                    multi_status = "OK"
                    multi_reason = f"ok_factors={len(ok_factors)}, skipped_factors={len(skipped_factors)}"

                    # asof_date: 실제 회귀 데이터의 마지막 날짜
                    asof_date = df2.index.max()
                    if isinstance(asof_date, (pd.Timestamp, dt.datetime)):
                        asof_date = asof_date.date()
                    if not isinstance(asof_date, dt.date):
                        asof_date = end

                    multi_asof_date = asof_date.isoformat()

                    for i, fc in enumerate(ok_factors):
                        upsert_rows.append({
                            "asof_date": asof_date.isoformat(),
                            "window_days": int(WINDOW_DAYS),
                            "stock_code": stock_code,
                            "factor_code": fc,

                            "beta": float(beta[i]) if np.isfinite(beta[i]) else None,
                            "r2": float(r2) if np.isfinite(r2) else None,
                            "n_obs": int(multi_n_obs),

                            "updated_at": updated_at,
                            "as_of_date": None,          # 혼동 컬럼 비움
                            "yf_symbol": used_symbol,
                            "alpha": float(alpha) if np.isfinite(alpha) else None,
                            "method": METHOD_MULTI,
                            "created_at": created_at,
                            "price_interval": PRICE_INTERVAL,
                            "lookback_window": LOOKBACK_WINDOW,
                        })

        report_rows.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "status": multi_status,
            "reason": multi_reason,
            "used_symbol": used_symbol,
            "asof_date": multi_asof_date,
            "n_obs": multi_n_obs,
            "ok_factors": "|".join(ok_factors),
            "skipped_factors": "|".join(skipped_factors),
            "single_ok_factors": "|".join(single_ok_factors),
            "single_skipped_factors": "|".join(single_skipped_factors),
            "single_failed_factors": "|".join(single_failed_factors),
            "single_status_map": "|".join(single_status_parts),
            "single_n_obs_map": "|".join(single_n_obs_parts),
        })

    # DB upsert
    try:
        upsert_beta_rows(sb, upsert_rows)
    except Exception as e:
        print(f"[ERROR] beta upsert failed: {e}")
        raise

    # Report CSV
    rep = pd.DataFrame(report_rows)
    rep.to_csv(REPORT_CSV_PATH, index=False, encoding="utf-8-sig")

    counts = rep["status"].value_counts().to_dict() if not rep.empty else {}
    print(f"[DONE] ok={int(counts.get('OK', 0))}, skip={int(counts.get('SKIP', 0))}, fail={int(counts.get('FAIL', 0))}")
    print(f"[DONE] total_upserted_rows={len(upsert_rows)}")
    print(f"[REPORT] {REPORT_CSV_PATH}")
    if missing_in_db:
        print(f"[WARN] missing factors in factor_returns (continued with available): {missing_in_db}")


if __name__ == "__main__":
    main()
