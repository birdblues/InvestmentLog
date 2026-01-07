#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise RuntimeError(f"Missing env var: {name}")
    return v

def main():
    sb = create_client(env_required("SUPABASE_URL"), env_required("SUPABASE_KEY"))

    # 1) factor_code 전체 목록/개수
    r = sb.table("factor_returns").select("factor_code,record_date,ret,frequency").execute()
    df = pd.DataFrame(r.data or [])
    print("rows:", len(df))
    if df.empty:
        print("factor_returns is empty")
        return

    df["record_date"] = pd.to_datetime(df["record_date"], errors="coerce").dt.date
    df["ret"] = pd.to_numeric(df["ret"], errors="coerce")

    print("\n[distinct factor_code]")
    print(df["factor_code"].value_counts().head(30).to_string())

    # 2) F_RATE_US10Y 존재 여부/기간/NULL 체크
    target = "F_RATE_US10Y"
    dft = df[df["factor_code"] == target].copy()

    print(f"\n[{target}] count:", len(dft))
    if not dft.empty:
        print("min_date:", dft["record_date"].min(), "max_date:", dft["record_date"].max())
        print("freq value_counts:\n", dft["frequency"].value_counts(dropna=False).to_string())
        print("ret null count:", int(dft["ret"].isna().sum()))

        # 3) 혹시 공백/대소문자 꼬임 찾기 (LIKE 대체)
        df_like = df[df["factor_code"].astype(str).str.contains("US10Y", na=False)]
        print("\n[factor_code contains 'US10Y']")
        print(df_like["factor_code"].value_counts().to_string())

if __name__ == "__main__":
    main()