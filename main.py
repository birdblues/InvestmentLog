import requests
import json
import os
import time
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client

# ============================================================================
# [환경 변수 로드] GitHub Secrets에서 가져옵니다.
# ============================================================================
try:
    SUPABASE_URL = os.environ["SUPABASE_URL"]
    SUPABASE_KEY = os.environ["SUPABASE_KEY"]
    ACCOUNTS_JSON = os.environ["ACCOUNTS_JSON"]
    ACCOUNTS = json.loads(ACCOUNTS_JSON)
except KeyError as e:
    print(f"❌ 환경변수 설정 오류: {e} 키가 없습니다.")
    exit(1)
except json.JSONDecodeError:
    print("❌ ACCOUNTS_JSON 형식이 올바르지 않습니다.")
    exit(1)

BASE_URL = "https://openapi.koreainvestment.com:9443"

# ============================================================================

def get_token_from_api(app_key, app_secret):
    """API 서버에 요청하여 새 토큰 발급 (메모리용)"""
    url = f"{BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body))
        res_json = res.json()
        if res.status_code == 200:
            return res_json['access_token']
        else:
            print(f"❌ 토큰 발급 실패: {res_json.get('error_description')}")
            return None
    except Exception as e:
        print(f"❌ 요청 중 에러: {e}")
        return None

def process_account(account_info, token, supabase):
    name = account_info['name']
    acc_no = account_info['acc_no']
    app_key = account_info['app_key']
    app_secret = account_info['app_secret']

    print(f"   📊 [{name}] 잔고 조회 중...")

    # 잔고 조회
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "TTTC8434R",
        "custtype": "P",
    }
    params = {
        "CANO": acc_no[:8],
        "ACNT_PRDT_CD": acc_no[-2:],
        "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
        "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
        "CTX_AREA_FK100": "", "CTX_AREA_NK100": ""
    }

    res = requests.get(url, headers=headers, params=params)
    data = res.json()

    if data['rt_cd'] != '0':
        print(f"   ❌ 조회 실패: {data['msg1']}")
        return

    output1 = data['output1']
    output2 = data['output2'][0]

    # 날짜 (KST 강제 적용) - GitHub 서버는 UTC이므로 필수
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    
    # 1. Snapshot Upsert
    snapshot_data = {
        "account_no": acc_no,
        "account_name": name,
        "record_date": today_str,
        "recorded_at": now_kst.isoformat(),
        "total_cash": int(output2['dnca_tot_amt']),
        "total_stock_amt": int(output2['scts_evlu_amt']),
        "total_asset": int(output2['tot_evlu_amt'])
    }

    res_master = supabase.table("asset_snapshot").upsert(
        snapshot_data, on_conflict="account_no, record_date"
    ).select().execute()

    if not res_master.data:
        print("   ❌ DB 저장 실패")
        return
    snapshot_id = res_master.data[0]['id']

    # 2. Holdings Update
    supabase.table("asset_holdings").delete().eq("snapshot_id", snapshot_id).execute()
    
    holdings_data = []
    for item in output1:
        holdings_data.append({
            "snapshot_id": snapshot_id,
            "stock_code": item['pdno'],
            "stock_name": item['prdt_name'],
            "qty": int(item['hldg_qty']),
            "buy_price": float(item['pchs_avg_pric']),
            "cur_price": float(item['prpr']),
            "eval_amt": int(item['evlu_amt']),
            "earning_rate": float(item['evlu_pfls_rt'])
        })

    if holdings_data:
        supabase.table("asset_holdings").insert(holdings_data).execute()
        print(f"   ✅ 저장 완료 (총자산: {snapshot_data['total_asset']:,}원)")
    else:
        print(f"   ✅ 저장 완료 (보유종목 없음)")

def main():
    print("=== 🚀 GitHub Actions 자산 백업 시작 ===")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Supabase 접속 실패: {e}")
        return

    # 메모리 토큰 캐시 (AppKey 기준)
    memory_token_cache = {}

    for account in ACCOUNTS:
        app_key = account['app_key']
        app_secret = account['app_secret']

        # 토큰 재사용 로직
        if app_key in memory_token_cache:
            token = memory_token_cache[app_key]
            print(f"\n♻️ [캐시] 토큰 재사용 ({account['name']})")
        else:
            print(f"\n⚡ [{account['name']}] 새 토큰 발급 중...")
            token = get_token_from_api(app_key, app_secret)
            if token:
                memory_token_cache[app_key] = token
            else:
                continue 

        # 계좌 처리
        try:
            process_account(account, token, supabase)
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        
        # API 호출 제한 방지
        time.sleep(1)

    print("\n=== ✨ 작업 완료 ===")

if __name__ == "__main__":
    main()