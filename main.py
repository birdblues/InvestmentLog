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
    print(f"❌ [Error] 환경변수 누락: {e}")
    exit(1)
except json.JSONDecodeError:
    print("❌ [Error] ACCOUNTS_JSON 형식이 올바르지 않습니다.")
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

    print(f"   📊 [{name}] 잔고 조회 중... ({acc_no})")

    # ====================================================
    # [페이지네이션] 연속 조회 처리 루프
    # ====================================================
    all_holdings = []
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    
    # 총액 정보는 첫 번째 호출에서 가져와서 고정
    final_output2 = None
    
    while True:
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
            # 연속 조회를 위한 파라미터 업데이트
            "CTX_AREA_FK100": ctx_area_fk100,
            "CTX_AREA_NK100": ctx_area_nk100
        }

        try:
            res = requests.get(url, headers=headers, params=params)
            data = res.json()
        except Exception as e:
            print(f"   ❌ API 요청 실패: {e}")
            return

        if data['rt_cd'] != '0':
            print(f"   ❌ 조회 실패(rt_cd!=0): {data.get('msg1', '알 수 없는 오류')}")
            return

        # 첫 페이지일 때만 총액 정보(output2) 저장
        if final_output2 is None and 'output2' in data and data['output2']:
            final_output2 = data['output2'][0]

        # 종목 리스트 수집
        if 'output1' in data and data['output1']:
            all_holdings.extend(data['output1'])
        
        # [연속 조회 체크] 
        # API 응답 헤더의 tr_cont가 'D' or 'M' 이거나, body의 ctx_area_nk100이 비어있지 않으면 다음 페이지 있음
        tr_cont = res.headers.get('tr_cont', 'N')
        ctx_area_nk100 = data.get('ctx_area_nk100', '').strip()
        ctx_area_fk100 = data.get('ctx_area_fk100', '').strip()

        if tr_cont in ['D', 'M'] or ctx_area_nk100 != "":
            # 다음 페이지 있음 -> 루프 계속
            time.sleep(0.1) # API 부하 방지
            continue
        else:
            # 더 이상 데이터 없음 -> 종료
            break

    # ====================================================
    # 데이터 저장 로직
    # ====================================================
    
    if final_output2 is None:
        print("   ⚠️ [주의] 계좌 총액 정보(output2)를 받지 못했습니다. 스킵합니다.")
        return

    # 날짜 생성 (KST 한국 시간)
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    
    # 데이터 정제 (총액 및 현금 역산)
    tot_amt = int(final_output2['tot_evlu_amt'])
    stock_amt = int(final_output2['scts_evlu_amt'])
    calc_cash = tot_amt - stock_amt 

    # [안전장치 🔥] 
    # 총액(stock_amt)은 있는데 종목 리스트(all_holdings)가 비어있다면, 
    # API 오류(주말/휴일 등)일 가능성이 높으므로 기존 데이터를 보호하기 위해 저장하지 않고 종료
    if stock_amt > 0 and not all_holdings:
        print(f"   ⚠️ [방어 로직 작동] 잔고({stock_amt:,}원)는 있으나 종목 리스트가 비어있습니다. 기존 데이터를 보호하기 위해 건너뜁니다.")
        return

    # [1] Master Data (Snapshot) Upsert
    snapshot_data = {
        "account_no": acc_no,
        "account_name": name,
        "record_date": today_str,
        "recorded_at": now_kst.isoformat(),
        "total_asset": tot_amt,
        "total_stock_amt": stock_amt,
        "total_cash": calc_cash
    }

    # execute()만 호출
    res_master = supabase.table("asset_snapshot").upsert(
        snapshot_data, on_conflict="account_no, record_date"
    ).execute()

    if not res_master.data:
        print("   ❌ DB 저장 실패 (Snapshot)")
        return
    
    snapshot_id = res_master.data[0]['id']

    # [2] Detail Data (Holdings) Replace
    # 안전장치를 통과했으므로, 해당 날짜의 기존 상세 내역을 지우고 새로 받은 전체 리스트를 저장
    supabase.table("asset_holdings").delete().eq("snapshot_id", snapshot_id).execute()
    
    holdings_data = []
    for item in all_holdings:
        # 혹시 모를 빈 데이터 필터링
        if not item['pdno']: continue
        
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
        # 대량 Insert (Batch)
        supabase.table("asset_holdings").insert(holdings_data).execute()
        print(f"   ✅ 저장 완료 (자산: {tot_amt:,}원 / 종목수: {len(holdings_data)}개)")
    else:
        # 주식 잔고가 0원이라 종목이 없는 경우
        print(f"   ✅ 저장 완료 (보유종목 없음 / 현금: {calc_cash:,}원)")

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