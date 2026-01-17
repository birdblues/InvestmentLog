#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
factor_returns_loader.py (FULL REPLACE)

[목표]
- factor_returns 테이블에 팩터 level + ret(upsert)
- ✅ 날짜는 "원본 소스 날짜" 그대로 저장 (KST 강제 변환/통일 제거)
- 일간(D)은 "KST 기준 전일(asof=오늘-1일)"까지만 수집해서 미완결(today) 방지
  (단, 저장되는 record_date/observed_date 자체는 소스 원본 날짜)

[사전 준비(권장)]
- factor_returns 테이블에 아래 컬럼이 있으면 같이 기록합니다.
  observed_date (date)           # 원본 날짜 (record_date와 동일하게 채움)
  effective_kr_date (date)       # 베타 계산 정렬 단계에서 채울 예정(여기선 None)
- source/series/frequency/ret_type/lag_policy/source_tz는 factor_metadata에 기록합니다.

필수 환경변수(.env):
- SUPABASE_URL
- SUPABASE_KEY
- FRED_API_KEY
- ECOS_API_KEY

선택:
- NASDAQ_DATALINK_API_KEY
"""

from __future__ import annotations

import os
import math
import time
import datetime as dt
import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd
import requests
import yfinance as yf
from dotenv import load_dotenv
from pykrx import stock
from supabase import create_client, Client

# ----------------------------
# .env load
# ----------------------------
load_dotenv(override=False)

# ----------------------------
# Config
# ----------------------------
FACTOR_TABLE = "factor_returns"
UPSERT_CHUNK_SIZE = 500
HTTP_TIMEOUT = 30
KST_TZ = "Asia/Seoul"

# lookback (safety buffer)
LOOKBACK_DAYS_DAILY = 14
LOOKBACK_MONTHS_MONTHLY = 2
DURATION_US10Y = 8.5
DURATION_KR10Y = 8.5
DURATION_US_HY_OAS = 4.5
DURATION_US_IG_OAS = 6.0
BACKFILL_DAYS_DAILY = 3

LAG_POLICY_BY_FACTOR = {
    "F_SECTOR_US_CONSUMER_DISCRETIONARY": "1",
    "F_SECTOR_US_INDUSTRIALS": "1",
    "F_SECTOR_US_MATERIALS": "1",
    "F_SECTOR_US_ENERGY": "1",
    "F_SECTOR_US_TECH": "1",
    "F_SECTOR_US_FINANCIALS": "1",
    "F_SECTOR_US_COMMUNICATIONS": "1",
    "F_SECTOR_US_HEALTHCARE": "1",
    "F_SECTOR_US_CONSUMER_STAPLES": "1",
    "F_SECTOR_US_UTILITIES": "1",
}


@dataclass(frozen=True)
class FactorSpec:
    factor_code: str
    factor_name: str
    source: str                 # "FRED" | "ECOS" | "NASDAQ_DATALINK" | "YFINANCE" | "PYKRX"
    source_series: str          # e.g. "DGS10" or "817Y002/D/010210000" or "KRW=X"
    frequency: str              # "D" or "M"
    ret_type: str               # "log_return" | "diff_pp" | "duration_return"
    duration_years: Optional[float] = None

    # ECOS specific
    ecos_stat_code: Optional[str] = None
    ecos_cycle: Optional[str] = None
    ecos_item_code: Optional[str] = None

    # YFINANCE specific
    yf_candidates: Optional[List[str]] = None


def env(name: str, default: Optional[str] = None) -> str:
    v = os.getenv(name, default)
    if v is None or v == "":
        raise RuntimeError(f"Missing env var: {name}")
    return v


# ----------------------------
# Date policy (only for fetch cutoff)
# ----------------------------
def today_kst_date() -> dt.date:
    return pd.Timestamp.now(tz=KST_TZ).date()


def asof_kst_date() -> dt.date:
    """
    미완결(today) 방지용 fetch cutoff.
    저장되는 날짜 자체는 원본 소스 날짜를 그대로 사용.
    """
    return today_kst_date() - dt.timedelta(days=1)


def apply_lookback(start: dt.date, frequency: str) -> dt.date:
    if frequency == "D":
        return start - dt.timedelta(days=LOOKBACK_DAYS_DAILY)
    if frequency == "M":
        return (pd.Timestamp(start) - pd.DateOffset(months=LOOKBACK_MONTHS_MONTHLY)).date()
    return start


# ----------------------------
# Helpers: normalize datetime index to "source-original" naive datetime
# ----------------------------
def _to_naive_datetime_index(idx: pd.Index) -> pd.DatetimeIndex:
    di = pd.to_datetime(idx)
    # tz-aware이면 tz 정보만 제거(벽시각 유지) => "원본에 가장 가까운" 형태
    try:
        if getattr(di, "tz", None) is not None:
            di = di.tz_localize(None)
    except Exception:
        # 일부 케이스 방어
        pass
    return pd.DatetimeIndex(di)


# ----------------------------
# Fetchers
# ----------------------------
def fred_fetch_series(fred_api_key: str, series_id: str, start: dt.date, end: dt.date) -> pd.Series:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": fred_api_key,
        "file_type": "json",
        "observation_start": start.isoformat(),
        "observation_end": end.isoformat(),
    }
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    data = r.json()
    obs = data.get("observations", [])

    rows: List[Tuple[pd.Timestamp, float]] = []
    for o in obs:
        d = o.get("date")
        v = o.get("value")
        if v is None or v == ".":
            continue
        try:
            rows.append((pd.to_datetime(d), float(v)))
        except ValueError:
            continue

    s = pd.Series({d: v for d, v in rows}).sort_index()
    s.index = _to_naive_datetime_index(s.index)
    return s


def ecos_fetch_series(
    ecos_api_key: str,
    stat_code: str,
    cycle: str,
    item_code: str,
    start: dt.date,
    end: dt.date,
    lang: str = "kr",
) -> pd.Series:
    base = f"https://ecos.bok.or.kr/api/StatisticSearch/{ecos_api_key}/json/{lang}"

    if cycle == "D":
        s_start = start.strftime("%Y%m%d")
        s_end = end.strftime("%Y%m%d")
    elif cycle == "M":
        s_start = start.strftime("%Y%m")
        s_end = end.strftime("%Y%m")
    else:
        raise ValueError(f"Unsupported ECOS cycle: {cycle}")

    all_rows: List[Tuple[pd.Timestamp, float]] = []
    start_no = 1
    page_size = 1000

    while True:
        end_no = start_no + page_size - 1
        url = f"{base}/{start_no}/{end_no}/{stat_code}/{cycle}/{s_start}/{s_end}/{item_code}"
        r = requests.get(url, timeout=HTTP_TIMEOUT)
        r.raise_for_status()
        payload = r.json()

        root = payload.get("StatisticSearch")
        if not root:
            break

        rows = root.get("row", [])
        if not rows:
            break

        for row in rows:
            t = row.get("TIME")
            v = row.get("DATA_VALUE")
            if t is None or v is None or v == "":
                continue
            try:
                if cycle == "D":
                    ts = pd.to_datetime(t, format="%Y%m%d")
                else:
                    ts = pd.to_datetime(t, format="%Y%m")
                all_rows.append((ts, float(v)))
            except ValueError:
                continue

        if len(rows) < page_size:
            break

        start_no += page_size
        time.sleep(0.12)

    s = pd.Series({d: v for d, v in all_rows}).sort_index()
    s.index = _to_naive_datetime_index(s.index)
    return s


def nasdaq_datalink_fetch_series(api_key: str, dataset_code: str, start: dt.date, end: dt.date) -> pd.Series:
    url = f"https://data.nasdaq.com/api/v3/datasets/{dataset_code}.json"
    params = {
        "api_key": api_key,
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "order": "asc",
    }
    r = requests.get(url, params=params, timeout=HTTP_TIMEOUT)
    r.raise_for_status()
    js = r.json()
    ds = js.get("dataset", {})
    data = ds.get("data", [])
    cols = ds.get("column_names", [])

    price_col_candidates = ["USD (AM)", "USD (PM)", "Value", "Settle"]
    price_idx = None
    for c in price_col_candidates:
        if c in cols:
            price_idx = cols.index(c)
            break
    if price_idx is None:
        price_idx = 1 if len(cols) > 1 else None

    rows: List[Tuple[pd.Timestamp, float]] = []
    for row in data:
        d = row[0]
        v = row[price_idx] if price_idx is not None else None
        if v is None:
            continue
        rows.append((pd.to_datetime(d), float(v)))

    s = pd.Series({d: v for d, v in rows}).sort_index()
    s.index = _to_naive_datetime_index(s.index)
    return s


def _ensure_series_close(close_obj: Union[pd.Series, pd.DataFrame]) -> pd.Series:
    if isinstance(close_obj, pd.Series):
        return close_obj
    if isinstance(close_obj, pd.DataFrame):
        if close_obj.shape[1] >= 1:
            return close_obj.iloc[:, 0]
    raise RuntimeError("Close is not a Series/DataFrame with columns")


def yfinance_fetch_close_series(
    symbols: List[str],
    start: dt.date,
    end_inclusive: dt.date,
) -> Tuple[str, pd.Series]:
    """
    ✅ 원본 날짜 유지:
    - yfinance가 준 index를 그대로 naive datetime으로만 정규화(tz 제거)
    - KST 변환/UTC 가정 변환 없음
    """
    last_err = None
    for sym in symbols:
        try:
            df = yf.download(
                sym,
                start=start.isoformat(),
                end=(end_inclusive + dt.timedelta(days=1)).isoformat(),  # inclusive
                interval="1d",
                auto_adjust=False,
                progress=False,
                threads=True,
            )
            if df is None or df.empty:
                continue
            if "Close" not in df.columns:
                continue

            close_raw = df["Close"]
            s = _ensure_series_close(close_raw).dropna()
            if s.empty or len(s) < 2:
                continue

            s.index = _to_naive_datetime_index(s.index)
            s = s.sort_index()
            return sym, s

        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(f"yfinance fetch failed for {symbols}. last_err={last_err}")


def pykrx_fetch_close_series(
    ticker: str,
    start: dt.date,
    end_inclusive: dt.date,
) -> pd.Series:
    ticker = ticker.replace("KRX:", "").lstrip("Q")
    start_str = start.strftime("%Y%m%d")
    end_str = end_inclusive.strftime("%Y%m%d")

    df = stock.get_market_ohlcv_by_date(start_str, end_str, ticker)
    if df is None or df.empty:
        raise RuntimeError(f"pykrx fetch returned empty for {ticker}")

    if "종가" not in df.columns:
        raise RuntimeError(f"pykrx missing Close column for {ticker}")

    s = df["종가"].dropna()
    if s.empty or len(s) < 2:
        raise RuntimeError(f"pykrx close series too short for {ticker}")

    s.index = _to_naive_datetime_index(s.index)
    return s.sort_index().astype(float)


# ----------------------------
# Returns
# ----------------------------
def compute_returns(level: pd.Series, ret_type: str, duration_years: Optional[float] = None) -> pd.Series:
    level = level.dropna().astype(float)

    if ret_type == "log_return":
        level = level[level > 0]
        return (level.apply(math.log) - level.shift(1).apply(math.log))
    if ret_type == "diff_pp":
        return level - level.shift(1)
    if ret_type == "duration_return":
        if duration_years is None:
            duration_years = DURATION_US10Y
        diff_pp = level - level.shift(1)
        return -float(duration_years) * (diff_pp / 100.0)

    raise ValueError(f"Unsupported ret_type: {ret_type}")


# ----------------------------
# Supabase helpers
# ----------------------------
def _meta_value(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    s = str(value).strip()
    return s if s else None


def fetch_factor_metadata_map(sb: Client, factor_codes: List[str]) -> Dict[str, Dict[str, Optional[str]]]:
    if not factor_codes:
        return {}
    resp = (
        sb.table("factor_metadata")
        .select("factor_code,factor_name,source,source_series,frequency,ret_type,lag_policy,source_tz")
        .in_("factor_code", factor_codes)
        .execute()
    )
    rows = resp.data or []
    meta: Dict[str, Dict[str, Optional[str]]] = {}
    for row in rows:
        code = _meta_value(row.get("factor_code"))
        if not code:
            continue
        frequency = _meta_value(row.get("frequency"))
        if frequency:
            frequency = frequency.upper()
        meta[code] = {
            "factor_name": _meta_value(row.get("factor_name")),
            "source": _meta_value(row.get("source")),
            "source_series": _meta_value(row.get("source_series")),
            "frequency": frequency,
            "ret_type": _meta_value(row.get("ret_type")),
            "lag_policy": _meta_value(row.get("lag_policy")),
            "source_tz": _meta_value(row.get("source_tz")),
        }
    return meta


def supabase_get_last_date(sb: Client, factor_code: str) -> Optional[dt.date]:
    resp = (
        sb.table(FACTOR_TABLE)
        .select("record_date")
        .eq("factor_code", factor_code)
        .order("record_date", desc=True)
        .limit(1)
        .execute()
    )
    data = resp.data or []
    if not data:
        return None
    return dt.date.fromisoformat(data[0]["record_date"])


def supabase_upsert_rows(sb: Client, rows: List[Dict]) -> None:
    for i in range(0, len(rows), UPSERT_CHUNK_SIZE):
        chunk = rows[i : i + UPSERT_CHUNK_SIZE]
        sb.table(FACTOR_TABLE).upsert(chunk, on_conflict="factor_code,record_date").execute()


def supabase_upsert_factor_metadata(
    sb: Client,
    spec: FactorSpec,
    source: str,
    source_series: str,
    frequency: str,
    ret_type: str,
    lag_policy: Optional[str],
    existing: Dict[str, Optional[str]],
) -> None:
    row: Dict[str, Optional[str]] = {"factor_code": spec.factor_code}
    if not _meta_value(existing.get("factor_name")):
        row["factor_name"] = spec.factor_name
    if not _meta_value(existing.get("source")):
        row["source"] = source
    if not _meta_value(existing.get("source_series")):
        row["source_series"] = source_series
    if not _meta_value(existing.get("frequency")):
        row["frequency"] = frequency
    if not _meta_value(existing.get("ret_type")):
        row["ret_type"] = ret_type
    if not _meta_value(existing.get("lag_policy")) and lag_policy is not None:
        row["lag_policy"] = lag_policy
    if not _meta_value(existing.get("source_tz")):
        row["source_tz"] = source_tz_label(source)
    if len(row) == 1:
        return
    sb.table("factor_metadata").upsert(row).execute()


def supabase_delete_factor_returns(sb: Client, factor_codes: List[str]) -> None:
    if not factor_codes:
        return
    chunk_size = 100
    for i in range(0, len(factor_codes), chunk_size):
        chunk = factor_codes[i : i + chunk_size]
        sb.table(FACTOR_TABLE).delete().in_("factor_code", chunk).execute()


# ----------------------------
# Factor specs (SSOT)
# ----------------------------
def build_factor_specs(nasdaq_enabled: bool) -> List[FactorSpec]:
    specs = [
        FactorSpec(
            factor_code="F_GROWTH_US_EQ",
            factor_name="미국주식",
            source="FRED",
            source_series="SP500",
            frequency="D",
            ret_type="log_return",
        ),
        FactorSpec(
            factor_code="F_GROWTH_EXUS_EQ",
            factor_name="글로벌주식",
            source="YFINANCE",
            source_series="VXUS",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["VXUS", "VEU"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_CONSUMER_DISCRETIONARY",
            factor_name="경기소비재",
            source="YFINANCE",
            source_series="XLY",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLY"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_INDUSTRIALS",
            factor_name="산업재",
            source="YFINANCE",
            source_series="XLI",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLI"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_MATERIALS",
            factor_name="소재",
            source="YFINANCE",
            source_series="XLB",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLB"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_ENERGY",
            factor_name="에너지",
            source="YFINANCE",
            source_series="XLE",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLE"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_TECH",
            factor_name="정보기술",
            source="YFINANCE",
            source_series="XLK",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLK"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_FINANCIALS",
            factor_name="금융",
            source="YFINANCE",
            source_series="XLF",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLF"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_COMMUNICATIONS",
            factor_name="통신서비스",
            source="YFINANCE",
            source_series="XLC",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLC"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_HEALTHCARE",
            factor_name="헬스케어",
            source="YFINANCE",
            source_series="XLV",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLV"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_CONSUMER_STAPLES",
            factor_name="필수소비재",
            source="YFINANCE",
            source_series="XLP",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLP"],
        ),
        FactorSpec(
            factor_code="F_SECTOR_US_UTILITIES",
            factor_name="유틸리티",
            source="YFINANCE",
            source_series="XLU",
            frequency="D",
            ret_type="log_return",
            yf_candidates=["XLU"],
        ),
        FactorSpec(
            factor_code="F_RATE_US10Y",
            factor_name="미국국채10년",
            source="FRED",
            source_series="DGS10",
            frequency="D",
            ret_type="duration_return",
            duration_years=DURATION_US10Y,
        ),
        FactorSpec(
            factor_code="F_RATE_US10Y_REAL",
            factor_name="미국실질금리10년",
            source="FRED",
            source_series="DFII10",
            frequency="D",
            ret_type="duration_return",
            duration_years=DURATION_US10Y,
        ),
        FactorSpec(
            factor_code="F_CURVE_US_2Y10Y",
            factor_name="미국금리커브(2-10년)",
            source="FRED",
            source_series="T10Y2Y",
            frequency="D",
            ret_type="diff_pp",
        ),
        FactorSpec(
            factor_code="F_RATE_KR10Y",
            factor_name="한국국채10년",
            source="ECOS",
            source_series="817Y002/D/010210000",
            frequency="D",
            ret_type="duration_return",
            duration_years=DURATION_KR10Y,
            ecos_stat_code="817Y002",
            ecos_cycle="D",
            ecos_item_code="010210000",
        ),
        FactorSpec(
            factor_code="F_CURR_USDKRW",
            factor_name="통화(원/달러)",
            source="PYKRX",
            source_series="456880",
            frequency="D",
            ret_type="log_return",
        ),
        FactorSpec(
            factor_code="F_VOL_VIX",
            factor_name="변동성(VIX)",
            source="FRED",
            source_series="VIXCLS",
            frequency="D",
            ret_type="log_return",
        ),
        FactorSpec(
            factor_code="F_CREDIT_US_HY_OAS",
            factor_name="하이일드채권",
            source="FRED",
            source_series="BAMLH0A0HYM2",
            frequency="D",
            ret_type="duration_return",
            duration_years=DURATION_US_HY_OAS,
        ),
        FactorSpec(
            factor_code="F_CREDIT_US_IG_OAS",
            factor_name="투자등급채권",
            source="FRED",
            source_series="BAMLC0A0CM",
            frequency="D",
            ret_type="duration_return",
            duration_years=DURATION_US_IG_OAS,
        ),
        FactorSpec(
            factor_code="F_INFL_US_BE10Y",
            factor_name="미국물가",
            source="FRED",
            source_series="T10YIE",
            frequency="D",
            ret_type="diff_pp",
        ),
        FactorSpec(
            factor_code="F_INFL_KR_CPI",
            factor_name="한국CPI",
            source="ECOS",
            source_series="901Y009/M/0",
            frequency="M",
            ret_type="log_return",
            ecos_stat_code="901Y009",
            ecos_cycle="M",
            ecos_item_code="0",
        ),
        FactorSpec(
            factor_code="F_COMM_OIL_WTI",
            factor_name="원유",
            source="FRED",
            source_series="DCOILWTICO",
            frequency="D",
            ret_type="log_return",
        ),
        FactorSpec(
            factor_code="F_COMM_GOLD_KR",
            factor_name="금현물",
            source="PYKRX",
            source_series="411060",
            frequency="D",
            ret_type="log_return",
        ),
    ]

    if nasdaq_enabled:
        specs.append(
            FactorSpec(
                factor_code="F_COMM_GOLD",
                factor_name="원자재(금, Nasdaq Data Link)",
                source="NASDAQ_DATALINK",
                source_series="LBMA/GOLD",
                frequency="D",
                ret_type="log_return",
            )
        )

    return specs


def source_tz_label(source: str) -> str:
    # date-only 관측치가 대부분이라 tz 의미는 약함. 디버깅용 라벨만 남김.
    if source in ("FRED", "ECOS", "NASDAQ_DATALINK", "PYKRX"):
        return "date-only"
    if source == "YFINANCE":
        return "yfinance-index"
    return "unknown"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load factor_returns from configured sources.")
    parser.add_argument(
        "--factor-codes",
        type=str,
        default="",
        help="Comma-separated factor codes to load (optional).",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Delete factor_returns for selected factor codes before reloading.",
    )
    return parser.parse_args()


# ----------------------------
# Main
# ----------------------------
def main():
    args = parse_args()
    target_factor_codes = [
        c.strip() for c in args.factor_codes.split(",") if c.strip()
    ]

    sb_url = env("SUPABASE_URL")
    sb_key = env("SUPABASE_KEY")
    fred_key = env("FRED_API_KEY")
    ecos_key = env("ECOS_API_KEY")

    nasdaq_key = os.getenv("NASDAQ_DATALINK_API_KEY", "").strip()
    nasdaq_enabled = len(nasdaq_key) > 0

    sb = create_client(sb_url, sb_key)

    # ✅ fetch cutoff (미완결 방지용)
    end = asof_kst_date()
    default_start = end - dt.timedelta(days=365 * 5)

    specs = build_factor_specs(nasdaq_enabled=nasdaq_enabled)
    if target_factor_codes:
        specs = [s for s in specs if s.factor_code in target_factor_codes]
        if not specs:
            print("[WARN] no matching factor_codes in specs")
            return
    elif args.full_refresh:
        print("[WARN] --full-refresh requires --factor-codes")
        return

    factor_codes = [spec.factor_code for spec in specs]
    meta_map = fetch_factor_metadata_map(sb, factor_codes)

    if args.full_refresh and target_factor_codes:
        supabase_delete_factor_returns(sb, target_factor_codes)
        print(f"[INFO] deleted factor_returns for {len(target_factor_codes)} factor(s)")

    total_rows = 0
    print(f"[INFO] KST today={today_kst_date()} / fetch_asof(end)={end}")

    for spec in specs:
        meta = meta_map.get(spec.factor_code, {})
        source = meta.get("source") or spec.source
        source_series = meta.get("source_series") or spec.source_series
        frequency = (meta.get("frequency") or spec.frequency).strip().upper()
        ret_type = meta.get("ret_type") or spec.ret_type
        lag_policy = meta.get("lag_policy") or LAG_POLICY_BY_FACTOR.get(spec.factor_code)
        last_date = supabase_get_last_date(sb, spec.factor_code)

        # 월간은 기존대로 최신이면 스킵, 일간은 최근 N일 백필
        if last_date is not None and frequency != "D" and last_date >= end:
            print(f"[SKIP] {spec.factor_code}: up-to-date (last_date={last_date} >= asof={end})")
            continue

        if last_date:
            if frequency == "D":
                anchor = min(last_date, end)
                start_store = anchor - dt.timedelta(days=BACKFILL_DAYS_DAILY - 1)
                if start_store < default_start:
                    start_store = default_start
            else:
                start_store = last_date + dt.timedelta(days=1)
            start_fetch = apply_lookback(start_store, frequency)
        else:
            start_store = default_start
            start_fetch = apply_lookback(default_start, frequency)

        if start_store > end:
            print(f"[SKIP] {spec.factor_code}: no new window (store_from={start_store} > asof={end})")
            continue

        print(f"[FETCH] {spec.factor_code} ({source} {source_series}) fetch {start_fetch} -> {end} / store from {start_store}")

        used_source_series = source_series

        # 1) fetch "level"
        try:
            if source == "FRED":
                level = fred_fetch_series(fred_key, source_series, start_fetch, end)

            elif source == "ECOS":
                assert spec.ecos_stat_code and spec.ecos_cycle and spec.ecos_item_code
                level = ecos_fetch_series(
                    ecos_api_key=ecos_key,
                    stat_code=spec.ecos_stat_code,
                    cycle=spec.ecos_cycle,
                    item_code=spec.ecos_item_code,
                    start=start_fetch,
                    end=end,
                )

            elif source == "NASDAQ_DATALINK":
                if not nasdaq_enabled:
                    print(f"[SKIP] {spec.factor_code}: NASDAQ_DATALINK_API_KEY not set")
                    continue
                level = nasdaq_datalink_fetch_series(nasdaq_key, source_series, start_fetch, end)

            elif source == "PYKRX":
                level = pykrx_fetch_close_series(source_series, start_fetch, end)

            elif source == "YFINANCE":
                cands = spec.yf_candidates or [source_series]
                used_source_series, level = yfinance_fetch_close_series(cands, start_fetch, end)

            else:
                raise ValueError(f"Unknown source: {source}")

        except Exception as e:
            print(f"[FAIL] {spec.factor_code}: fetch error: {e}")
            continue

        # 2) compute returns & build rows
        try:
            level = level.dropna()
            if level.empty or len(level) < 2:
                print(f"[INFO] {spec.factor_code}: series empty/too short")
                continue

            ret = compute_returns(level, ret_type, spec.duration_years)
            df = pd.DataFrame({"level": level, "ret": ret})
            df = df.sort_index()

            # store_from 필터 (원본 날짜 기준)
            df = df[df.index.date >= start_store]
            if df.empty:
                max_date = level.index.date.max() if len(level) else None
                print(f"[INFO] {spec.factor_code}: no new rows after store_from (max_date_in_source={max_date}, store_from={start_store})")
                continue

            rows: List[Dict] = []
            try:
                supabase_upsert_factor_metadata(
                    sb,
                    spec,
                    source=source,
                    source_series=used_source_series,
                    frequency=frequency,
                    ret_type=ret_type,
                    lag_policy=lag_policy,
                    existing=meta,
                )
            except Exception as e:
                print(f"[WARN] {spec.factor_code}: factor_metadata upsert failed: {e}")

            for ts, rrow in df.iterrows():
                record_date = ts.date()  # ✅ 원본 index의 date 그대로
                row = {
                    "factor_code": spec.factor_code,
                    "record_date": record_date.isoformat(),      # 기존 컬럼(= 원본 날짜로 사용)
                    "level": float(rrow["level"]) if pd.notna(rrow["level"]) else None,
                    "ret": float(rrow["ret"]) if pd.notna(rrow["ret"]) else None,

                    # ✅ 새 컬럼(있다면 같이 저장; 없으면 Supabase가 에러 낼 수 있음)
                    "observed_date": record_date.isoformat(),
                    "effective_kr_date": None,
                }
                rows.append(row)

            supabase_upsert_rows(sb, rows)
            total_rows += len(rows)
            print(f"[OK] {spec.factor_code}: upserted {len(rows)} rows (used_series={used_source_series})")

        except Exception as e:
            print(f"[FAIL] {spec.factor_code}: transform/upsert error: {e}")

    print(f"\n[DONE] total upserted rows: {total_rows}")


if __name__ == "__main__":
    main()
