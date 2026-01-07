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

load_dotenv(override=False)


# -----------------------------
# Hardcoded table names
# -----------------------------
TICKER_MAP_TABLE = "ticker_category_map"
FACTOR_TABLE = "factor_returns"
BETA_TABLE = "ticker_factor_beta_long"


# -----------------------------
# Runtime config (hardcoded)
# -----------------------------
PRICE_INTERVAL = "1d"
LOOKBACK_WINDOW = "2y"          # yfinance period
WINDOW_DAYS = 252               # 회귀에 사용할 최대 관측치(대략 1년 영업일)
MIN_NOBS = 60                   # 최소 관측치
UPSERT_CHUNK_SIZE = 500

REPORT_CSV_PATH = "./beta_run_report.csv"


# -----------------------------
# Factor lag policy (observation shift)
# - 한국 종목 기준: 미국장 마감/발표 팩터는 다음 영업일에 반영된다고 가정 -> +1
# - 필요하면 여기만 바꾸면 됨
# -----------------------------
FACTOR_LAG_OBS: Dict[str, int] = {
    "F_GROWTH_US_EQ": 1,
    "F_RATE_US10Y": 1,
    "F_VOL_VIX": 1,
    "F_CREDIT_US_HY_OAS": 1,
    "F_INFL_US_BE10Y": 1,
    "F_COMM_OIL_WTI": 1,
    # FX는 혼재 가능 -> 기본 0
    "F_CURR_USDKRW": 0,
    # KR factors
    "F_RATE_KR10Y": 0,
    "F_INFL_KR_CPI": 0,
}


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
def fetch_price_returns(symbol: str, end_date: dt.date) -> Optional[pd.Series]:
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
        .select("factor_code,record_date,ret,frequency")
        .eq("factor_code", factor_code)
        .eq("frequency", "D")
        .lte("record_date", end_date.isoformat())
        .order("record_date", desc=False)
    )
    if start_date is not None:
        q = q.gte("record_date", start_date.isoformat())

    rows = sb_select_all(q, page_size=page_size, max_pages=max_pages)
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce").dt.date
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")
    df = df.dropna(subset=["factor_code", "record_date", "ret"]).copy()
    return df


def fetch_factor_returns(
    sb: Client,
    factor_codes: List[str],
    end_date: dt.date,
    start_date: Optional[dt.date] = None,
) -> pd.DataFrame:
    frames: List[pd.DataFrame] = []
    for fc in factor_codes:
        dfi = fetch_factor_returns_one(sb, fc, end_date=end_date, start_date=start_date)
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

    for fc, g in out.groupby("factor_code", sort=False):
        lag = int(FACTOR_LAG_OBS.get(fc, 0))
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
        "F_INFL_KR_CPI",
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
            })
            continue

        used_symbol = ""
        ret_t: Optional[pd.Series] = None

        for sym in candidates:
            ret_t = fetch_price_returns(sym, end_date=end)
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
            })
            continue

        # join (여기서 전체 dropna() 절대 하지 않음!)
        df = pd.DataFrame({"ret_t": ret_t})
        df.index.name = "record_date"
        df = df.join(fwide, how="inner")

        # 실제 존재하는 factor만
        available_factors = [c for c in factor_codes if c in df.columns]

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

        if not ok_factors:
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "SKIP",
                "reason": f"no_factor_overlap(min_nobs={MIN_NOBS}) missing_in_db={missing_in_db}",
                "used_symbol": used_symbol,
                "asof_date": "",
                "n_obs": 0,
                "ok_factors": "",
                "skipped_factors": "|".join(skipped_factors),
            })
            continue

        # 회귀용 데이터: ret_t + ok_factors만 subset dropna
        need_cols = ["ret_t"] + ok_factors
        df2 = df[need_cols].dropna().copy()

        # window 제한 (최근 WINDOW_DAYS)
        if len(df2) > WINDOW_DAYS:
            df2 = df2.iloc[-WINDOW_DAYS:].copy()

        n_obs = int(df2.shape[0])
        if n_obs < MIN_NOBS:
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "SKIP",
                "reason": f"thin(n_obs={n_obs}) ok_factors={len(ok_factors)} skipped_factors={len(skipped_factors)}",
                "used_symbol": used_symbol,
                "asof_date": "",
                "n_obs": n_obs,
                "ok_factors": "|".join(ok_factors),
                "skipped_factors": "|".join(skipped_factors),
            })
            continue

        # 회귀
        y = df2["ret_t"].astype(float).values
        X = df2[ok_factors].astype(float).values

        try:
            beta, alpha, r2 = ols_multi(y, X)
        except Exception as e:
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "status": "FAIL",
                "reason": f"ols_exception:{e}",
                "used_symbol": used_symbol,
                "asof_date": "",
                "n_obs": n_obs,
                "ok_factors": "|".join(ok_factors),
                "skipped_factors": "|".join(skipped_factors),
            })
            continue

        # asof_date: 실제 회귀 데이터의 마지막 날짜
        asof_date = df2.index.max()
        if isinstance(asof_date, (pd.Timestamp, dt.datetime)):
            asof_date = asof_date.date()
        if not isinstance(asof_date, dt.date):
            asof_date = end

        updated_at = now_utc_iso()
        created_at = updated_at
        method = "OLS_MULTI"

        for i, fc in enumerate(ok_factors):
            upsert_rows.append({
                "asof_date": asof_date.isoformat(),
                "window_days": int(WINDOW_DAYS),
                "stock_code": stock_code,
                "factor_code": fc,

                "beta": float(beta[i]) if np.isfinite(beta[i]) else None,
                "r2": float(r2) if np.isfinite(r2) else None,
                "n_obs": int(n_obs),

                "updated_at": updated_at,
                "as_of_date": None,          # 혼동 컬럼 비움
                "yf_symbol": used_symbol,
                "alpha": float(alpha) if np.isfinite(alpha) else None,
                "method": method,
                "created_at": created_at,
                "price_interval": PRICE_INTERVAL,
                "lookback_window": LOOKBACK_WINDOW,
            })

        report_rows.append({
            "stock_code": stock_code,
            "stock_name": stock_name,
            "status": "OK",
            "reason": f"ok_factors={len(ok_factors)}, skipped_factors={len(skipped_factors)}",
            "used_symbol": used_symbol,
            "asof_date": asof_date.isoformat(),
            "n_obs": n_obs,
            "ok_factors": "|".join(ok_factors),
            "skipped_factors": "|".join(skipped_factors),
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