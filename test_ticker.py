#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
[목표]
- ticker_category_map 전체 종목을 대상으로 yfinance 심볼 가용성 점검
- FAIL/MANUAL + THIN(데이터 부족)까지 리포트 생성
- ✅ 기본 동작: ticker_category_map에 yf_symbol / yf_status / yf_n_rows / ... 결과를 "항상" write-back
  (원하면 WRITE_BACK=false 로 끌 수 있음)

Install:
  pip install supabase yfinance pandas python-dotenv

Env:
  SUPABASE_URL=...
  SUPABASE_KEY=...

Optional (override):
  YF_PROBE_PERIOD=3mo
  YF_PROBE_INTERVAL=1d
  YF_MIN_ROWS=40
  OUT_CSV=./yf_symbol_report.csv

  WRITE_BACK=true|false          # 기본 true
  CLEAR_SYMBOL_ON_FAIL=false     # true면 FAIL일 때 yf_symbol도 None으로 지움
"""

import os
import sys
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import yfinance as yf
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()


# ---------------------------
# Config (defaults)
# ---------------------------
TABLE = "ticker_category_map"

DEFAULT_PROBE_PERIOD = "3mo"
DEFAULT_PROBE_INTERVAL = "1d"
DEFAULT_MIN_ROWS = 40

DEFAULT_WRITE_BACK = True
DEFAULT_CLEAR_SYMBOL_ON_FAIL = False


# ---------------------------
# Supabase
# ---------------------------
def sb_client() -> Client:
    url = os.environ.get("SUPABASE_URL")
    key = os.environ.get("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("Missing SUPABASE_URL / SUPABASE_KEY")
    return create_client(url, key)


def fetch_all_tickers(sb: Client) -> pd.DataFrame:
    """
    ✅ ticker_category_map 실제 컬럼에 맞춰서만 select
    """
    res = sb.table(TABLE).select(
        "stock_code,stock_name,asset_type,country,currency,tags,"
        "yf_symbol,yf_status,yf_n_rows,yf_first_date,yf_last_date,"
        "yf_probe_interval,yf_probe_period,yf_reason,yf_checked_at"
    ).execute()

    rows = res.data or []
    if not rows:
        return pd.DataFrame(columns=[
            "stock_code","stock_name","asset_type","country","currency","tags",
            "yf_symbol","yf_status","yf_n_rows","yf_first_date","yf_last_date",
            "yf_probe_interval","yf_probe_period","yf_reason","yf_checked_at"
        ])
    return pd.DataFrame(rows)


def write_back_probe_result(sb: Client, stock_code: str, payload: Dict) -> None:
    sb.table(TABLE).update(payload).eq("stock_code", stock_code).execute()


# ---------------------------
# yfinance probing
# ---------------------------
def probe_symbol(symbol: str, period: str = "3mo", interval: str = "1d") -> Tuple[bool, int, Optional[str], Optional[str], str]:
    """
    returns:
      ok, n_rows, first_date_iso, last_date_iso, reason
    """
    try:
        df = yf.download(
            symbol,
            period=period,
            interval=interval,
            auto_adjust=False,
            progress=False,
            threads=False,
        )
    except Exception as e:
        return False, 0, None, None, f"exception:{e}"

    if df is None or df.empty:
        return False, 0, None, None, "empty"

    idx = pd.to_datetime(df.index)
    first_date = idx.min().date().isoformat() if len(idx) else None
    last_date = idx.max().date().isoformat() if len(idx) else None
    return True, int(df.shape[0]), first_date, last_date, "ok"


# ---------------------------
# Symbol candidates
# ---------------------------
def normalize_code(code: str) -> str:
    return (code or "").strip().upper()


def is_krx_6digits(code: str) -> bool:
    return bool(re.fullmatch(r"\d{6}", code))


def pad_krx_code(code: str) -> Optional[str]:
    if re.fullmatch(r"\d{5}", code):
        return "0" + code
    return None


def is_alnum6(code: str) -> bool:
    """
    ✅ 6자리 영숫자(예: 0005D0, 0089C0, 0046A0 같은 케이스)
    """
    return bool(re.fullmatch(r"[0-9A-Z]{6}", code)) and (not is_krx_6digits(code))


def generate_candidates(stock_code: str) -> Tuple[List[str], str]:
    """
    후보 심볼 생성 규칙:
      - 이미 .KS/.KQ가 붙어있으면 그대로
      - 6자리 숫자면 XXXXXX.KS / XXXXXX.KQ
      - 5자리 숫자면 0패딩 후 .KS/.KQ
      - Q+6자리(ETN 등)면 접두어 제거한 6자리 + 원본(Q포함) 둘다 시도
      - ✅ 6자리 영숫자면 그대로 {CODE}.KS / {CODE}.KQ 도 시도  (0005D0 같은 케이스)
      - 문자열에서 6자리 숫자 substring 있으면 그것도 .KS/.KQ
    """
    code = normalize_code(stock_code)

    if code in ("CASH",):
        return [], "skip:cash"

    # 이미 심볼 형태면 그대로
    if code.endswith(".KS") or code.endswith(".KQ"):
        return [code], "given:yf_symbol"

    cands: List[str] = []
    notes: List[str] = []

    # 6자리 숫자
    if is_krx_6digits(code):
        cands += [f"{code}.KS", f"{code}.KQ"]
        notes.append("rule:6digits->KS/KQ")

    # 5자리 숫자 -> 0패딩
    padded = pad_krx_code(code)
    if padded:
        cands += [f"{padded}.KS", f"{padded}.KQ"]
        notes.append("rule:5digits->0pad->KS/KQ")

    # Q + 6digits
    m = re.fullmatch(r"Q(\d{6})", code)
    if m:
        core = m.group(1)
        cands += [f"{core}.KS", f"{core}.KQ", f"{code}.KS", f"{code}.KQ"]
        notes.append("rule:Q+6digits->stripQ + original")

    # ✅ 6자리 영숫자(letters 포함)
    if is_alnum6(code):
        cands += [f"{code}.KS", f"{code}.KQ"]
        notes.append("rule:alnum6->KS/KQ")

    # 문자열 안에 6자리 숫자가 섞여 있으면 추출
    m2 = re.search(r"(\d{6})", code)
    if m2 and not is_krx_6digits(code):
        core = m2.group(1)
        cands += [f"{core}.KS", f"{core}.KQ"]
        notes.append("rule:extract_6digits->KS/KQ")

    # dedup
    seen = set()
    cands2: List[str] = []
    for s in cands:
        if s not in seen:
            seen.add(s)
            cands2.append(s)

    if not cands2:
        notes.append("need_manual_mapping")

    return cands2, ";".join(notes)


def recommend_manual_mapping_hint(stock_code: str, stock_name: str) -> str:
    code = normalize_code(stock_code)
    name = (stock_name or "").strip()

    if code == "CASH":
        return "현금은 심볼 불필요"
    if re.fullmatch(r"Q\d{6}", code):
        return "KRX ETN/파생코드일 수 있음: 접두어 Q 제거한 6자리로 시도(예: Q530130 -> 530130.KS)"
    if is_alnum6(code):
        return "6자리 영숫자 코드: Yahoo Finance에서 그대로 검색 후 (CODE.KS / CODE.KQ) 확인"
    if re.search(r"[A-Z]", code) and not code.endswith((".KS", ".KQ")):
        return "코드가 6자리 숫자가 아님: 실제 KRX 6자리 종목코드 확인 후 (XXXXXX.KS or XXXXXX.KQ)로 매핑 필요"
    if name:
        return f"Yahoo Finance에서 '{name}' 또는 KRX 6자리 코드로 검색 후 .KS/.KQ 확정"
    return "Yahoo Finance에서 KRX 6자리 코드로 검색 후 .KS/.KQ 확정"


# ---------------------------
# Main
# ---------------------------
def main():
    period = os.environ.get("YF_PROBE_PERIOD", DEFAULT_PROBE_PERIOD)
    interval = os.environ.get("YF_PROBE_INTERVAL", DEFAULT_PROBE_INTERVAL)
    min_rows = int(os.environ.get("YF_MIN_ROWS", str(DEFAULT_MIN_ROWS)))
    out_csv = os.environ.get("OUT_CSV") or f"./yf_symbol_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    write_back = os.environ.get("WRITE_BACK")
    if write_back is None:
        write_back_flag = DEFAULT_WRITE_BACK
    else:
        write_back_flag = write_back.strip().lower() == "true"

    clear_on_fail = os.environ.get("CLEAR_SYMBOL_ON_FAIL")
    if clear_on_fail is None:
        clear_on_fail_flag = DEFAULT_CLEAR_SYMBOL_ON_FAIL
    else:
        clear_on_fail_flag = clear_on_fail.strip().lower() == "true"

    sb = sb_client()
    tickers = fetch_all_tickers(sb)
    if tickers.empty:
        raise RuntimeError("ticker_category_map is empty.")

    report_rows: List[Dict] = []
    cnt = {"OK": 0, "THIN": 0, "FAIL": 0, "MANUAL": 0, "SKIP": 0}

    for _, row in tickers.iterrows():
        stock_code = str(row.get("stock_code", "")).strip()
        stock_name = row.get("stock_name", "") or ""
        asset_type = row.get("asset_type", "") or ""
        country = row.get("country", "") or ""
        currency = row.get("currency", "") or ""
        tags = row.get("tags", "") or ""

        # ✅ 이미 yf_symbol이 있으면 최우선 시도
        yf_symbol = (row.get("yf_symbol") or "").strip()

        # CASH 스킵
        if stock_code.upper() == "CASH":
            cnt["SKIP"] += 1
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "asset_type": asset_type,
                "country": country,
                "currency": currency,
                "tags": tags,
                "candidates": "",
                "matched_symbol": "",
                "status": "SKIP",
                "n_rows": 0,
                "first_date": "",
                "last_date": "",
                "probe_period": period,
                "probe_interval": interval,
                "heuristic": "skip:cash",
                "reason": "cash",
                "manual_hint": recommend_manual_mapping_hint(stock_code, stock_name),
            })
            continue

        if yf_symbol:
            candidates = [yf_symbol]
            heur_note = "prefer:yf_symbol"
        else:
            candidates, heur_note = generate_candidates(stock_code)

        if heur_note == "skip:cash":
            cnt["SKIP"] += 1
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "asset_type": asset_type,
                "country": country,
                "currency": currency,
                "tags": tags,
                "candidates": "",
                "matched_symbol": "",
                "status": "SKIP",
                "n_rows": 0,
                "first_date": "",
                "last_date": "",
                "probe_period": period,
                "probe_interval": interval,
                "heuristic": heur_note,
                "reason": "cash",
                "manual_hint": recommend_manual_mapping_hint(stock_code, stock_name),
            })
            continue

        if not candidates:
            cnt["MANUAL"] += 1
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "asset_type": asset_type,
                "country": country,
                "currency": currency,
                "tags": tags,
                "candidates": "",
                "matched_symbol": "",
                "status": "MANUAL",
                "n_rows": 0,
                "first_date": "",
                "last_date": "",
                "probe_period": period,
                "probe_interval": interval,
                "heuristic": heur_note,
                "reason": "no_candidates",
                "manual_hint": recommend_manual_mapping_hint(stock_code, stock_name),
            })

            # ✅ MANUAL도 DB에 상태 기록(원하면)
            if write_back_flag:
                payload = {
                    "yf_status": "MANUAL",
                    "yf_n_rows": 0,
                    "yf_first_date": None,
                    "yf_last_date": None,
                    "yf_probe_interval": interval,
                    "yf_probe_period": period,
                    "yf_reason": "no_candidates",
                    "yf_checked_at": datetime.now(timezone.utc).isoformat(),
                }
                write_back_probe_result(sb, stock_code, payload)

            continue

        matched = ""
        n_rows = 0
        first_date = ""
        last_date = ""
        last_reason = ""

        for sym in candidates:
            ok, n, fdt, ldt, reason = probe_symbol(sym, period=period, interval=interval)
            last_reason = reason
            if ok:
                matched = sym
                n_rows = n
                first_date = fdt or ""
                last_date = ldt or ""
                break

        if matched:
            status = "OK" if n_rows >= min_rows else "THIN"
            cnt[status] += 1

            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "asset_type": asset_type,
                "country": country,
                "currency": currency,
                "tags": tags,
                "candidates": "|".join(candidates),
                "matched_symbol": matched,
                "status": status,
                "n_rows": n_rows,
                "first_date": first_date,
                "last_date": last_date,
                "probe_period": period,
                "probe_interval": interval,
                "heuristic": heur_note,
                "reason": "ok",
                "manual_hint": "" if status == "OK" else "데이터는 있으나 표본 부족 → 기간 확대/다른 소스 고려",
            })

            if write_back_flag:
                payload = {
                    "yf_symbol": matched,
                    "yf_status": status,
                    "yf_n_rows": n_rows,
                    "yf_first_date": first_date or None,
                    "yf_last_date": last_date or None,
                    "yf_probe_interval": interval,
                    "yf_probe_period": period,
                    "yf_reason": "ok",
                    "yf_checked_at": datetime.now(timezone.utc).isoformat(),
                }
                write_back_probe_result(sb, stock_code, payload)

        else:
            cnt["FAIL"] += 1
            report_rows.append({
                "stock_code": stock_code,
                "stock_name": stock_name,
                "asset_type": asset_type,
                "country": country,
                "currency": currency,
                "tags": tags,
                "candidates": "|".join(candidates),
                "matched_symbol": "",
                "status": "FAIL",
                "n_rows": 0,
                "first_date": "",
                "last_date": "",
                "probe_period": period,
                "probe_interval": interval,
                "heuristic": heur_note,
                "reason": last_reason,
                "manual_hint": recommend_manual_mapping_hint(stock_code, stock_name),
            })

            if write_back_flag:
                payload = {
                    "yf_status": "FAIL",
                    "yf_n_rows": 0,
                    "yf_first_date": None,
                    "yf_last_date": None,
                    "yf_probe_interval": interval,
                    "yf_probe_period": period,
                    "yf_reason": last_reason,
                    "yf_checked_at": datetime.now(timezone.utc).isoformat(),
                }
                if clear_on_fail_flag:
                    payload["yf_symbol"] = None
                write_back_probe_result(sb, stock_code, payload)

    report = pd.DataFrame(report_rows)
    status_order = {"FAIL": 0, "MANUAL": 1, "THIN": 2, "OK": 3, "SKIP": 4}
    report["status_order"] = report["status"].map(status_order).fillna(9).astype(int)
    report = report.sort_values(["status_order", "asset_type", "stock_code"]).drop(columns=["status_order"])

    report.to_csv(out_csv, index=False, encoding="utf-8-sig")

    print("========================================")
    print("[yfinance symbol probe report]")
    print(f"probe_period={period}, interval={interval}, min_rows={min_rows}")
    print(f"output_csv={out_csv}")
    print("----------------------------------------")
    for k in ["OK", "THIN", "FAIL", "MANUAL", "SKIP"]:
        print(f"{k:6}: {cnt[k]}")
    print(f"WRITE_BACK={write_back_flag} (default={DEFAULT_WRITE_BACK})")
    print(f"CLEAR_SYMBOL_ON_FAIL={clear_on_fail_flag} (default={DEFAULT_CLEAR_SYMBOL_ON_FAIL})")
    print("========================================")

    head = report[report["status"].isin(["FAIL", "MANUAL", "THIN"])].head(30)
    if not head.empty:
        print("\n[Top issues]")
        print(head[["status", "stock_code", "stock_name", "candidates", "reason", "manual_hint"]].to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)