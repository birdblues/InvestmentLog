#!/bin/bash

set -euo pipefail

WORKDIR="/Users/birdblues/workspace/InvestmentLog"
UV_BIN="/usr/local/bin/uv"

cd "$WORKDIR"

echo "[`date '+%Y-%m-%d %H:%M:%S'`] factor jobs start"
"$UV_BIN" run python factor_returns_loader.py
"$UV_BIN" run python ticker_factor_beta_loader.py
FACTOR_RET_SOURCE=zscore "$UV_BIN" run python ticker_factor_beta_loader.py
echo "[`date '+%Y-%m-%d %H:%M:%S'`] factor jobs done"
