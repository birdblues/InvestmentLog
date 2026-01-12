#!/bin/bash
set -euo pipefail

REPO_DIR="/Users/birdblues/workspace/InvestmentLog"
cd "$REPO_DIR"

/usr/local/bin/uv run python update_factor_lag_policy.py
