import requests
import json
import os
import time
from datetime import datetime, timezone, timedelta
from supabase import create_client, Client
from dotenv import load_dotenv
import keyring

load_dotenv()

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



# ============================================================================
# [핵심] 계좌별 API 조회 로직 분리
# ============================================================================

def fetch_balance_stock(token, app_key, app_secret, acc_no):
    """일반 주식 계좌 조회 (위탁, 연금저축, ISA 등)"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/inquire-balance"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "TTTC8434R", # 주식 잔고 조회
        "custtype": "P",
    }
    
    all_holdings = []
    tot_amt = 0
    stock_amt = 0
    cash_amt = 0
    
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    
    page_count = 0
    MAX_PAGES = 20

    while True:
        page_count += 1
        print(f"      ▶ 일반계좌 페이지 {page_count} 조회 중...", end="\r")

        params = {
            "CANO": acc_no[:8],
            "ACNT_PRDT_CD": acc_no[-2:],
            "AFHR_FLPR_YN": "N", "OFL_YN": "", "INQR_DVSN": "02", "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N", "FNCG_AMT_AUTO_RDPT_YN": "N", "PRCS_DVSN": "00",
            "CTX_AREA_FK100": ctx_area_fk100,
            "CTX_AREA_NK100": ctx_area_nk100
        }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=30)
            data = res.json()
        except Exception as e:
             print(f"\n   ❌ API 요청 실패: {e}")
             return None
        
        if data['rt_cd'] != '0':
            print(f"\n   ❌ 일반계좌 조회 실패: {data.get('msg1')}")
            return None

        # 첫 페이지에서 총액 정보 수집
        if tot_amt == 0 and data['output2']:
            out2 = data['output2'][0]
            tot_amt = int(out2['tot_evlu_amt'])
            stock_amt = int(out2['scts_evlu_amt'])
            try:
                cash_amt = int(out2['prvs_rcdl_excc_amt'])
            except:
                cash_amt = tot_amt - stock_amt

        # 보유 종목 추가
        if data['output1']:
            for item in data['output1']:
                all_holdings.append({
                    "stock_code": item['pdno'],
                    "stock_name": item['prdt_name'],
                    "qty": int(item['hldg_qty']),
                    "buy_price": float(item['pchs_avg_pric']),
                    "cur_price": float(item['prpr']),
                    "eval_amt": int(item['evlu_amt']),
                    "earning_rate": float(item['evlu_pfls_rt'])
                })
        else:
            break
        
        # [수정된 페이지네이션] 다음 키값 없으면 즉시 종료
        ctx_area_nk100 = data.get('ctx_area_nk100', '').strip()
        ctx_area_fk100 = data.get('ctx_area_fk100', '').strip()
        
        if ctx_area_nk100 == "":
            break
            
        if page_count < MAX_PAGES:
            time.sleep(0.1)
            continue
        else:
            break
    
    print("") 
    return {
        "total_asset": tot_amt,
        "total_stock": stock_amt,
        "total_cash": cash_amt,
        "holdings": all_holdings
    }

def fetch_balance_irp(token, app_key, app_secret, acc_no):
    """IRP / 퇴직연금 계좌 조회 (-29)"""
    url = f"{BASE_URL}/uapi/domestic-stock/v1/trading/pension/inquire-balance"
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "authorization": f"Bearer {token}",
        "appkey": app_key,
        "appsecret": app_secret,
        "tr_id": "TTTC2208R", # 퇴직연금 잔고 조회
    }
    
    all_holdings = []
    tot_amt = 0
    
    ctx_area_fk100 = ""
    ctx_area_nk100 = ""
    
    page_count = 0
    MAX_PAGES = 20

    while True:
        page_count += 1
        print(f"      ▶ IRP계좌 페이지 {page_count} 조회 중...", end="\r")

        params = {
            "CANO": acc_no[:8],
            "ACNT_PRDT_CD": acc_no[-2:],
            "ACCA_DVSN_CD": "00",
            "INQR_DVSN": "00",
            "CTX_AREA_FK100": ctx_area_fk100,
            "CTX_AREA_NK100": ctx_area_nk100
        }
        try:
            res = requests.get(url, headers=headers, params=params, timeout=30)
            data = res.json()
        except Exception as e:
             print(f"\n   ❌ API 요청 실패: {e}")
             return None
        
        if data['rt_cd'] != '0':
            print(f"\n   ❌ IRP계좌 조회 실패: {data.get('msg1')}")
            return None

        # IRP 총액 정보
        if tot_amt == 0 and data['output2']:
            out2 = data['output2']
            tot_amt = int(out2.get('tot_evlu_amt', 0))
            try:
                cash_amt = int(out2.get('prvs_rcdl_excc_amt', 0))
            except:
                pass
            
        # 보유 종목 추가
        if data['output1']:
            for item in data['output1']:
                all_holdings.append({
                    "stock_code": item['pdno'],
                    "stock_name": item['prdt_name'],
                    "qty": int(item['hldg_qty']),
                    "buy_price": float(item['pchs_avg_pric']),
                    "cur_price": float(item['prpr']),
                    "eval_amt": int(item['evlu_amt']),
                    "earning_rate": float(item.get('evlu_erng_rt', 0))
                })
        else:
            break
        
        # [수정된 페이지네이션] 다음 키값 없으면 즉시 종료 (무한루프 방지 핵심)
        ctx_area_nk100 = data.get('ctx_area_nk100', '').strip()
        ctx_area_fk100 = data.get('ctx_area_fk100', '').strip()
        
        if ctx_area_nk100 == "":
            break
            
        if page_count < MAX_PAGES:
            time.sleep(0.1)
            continue
        else:
            break
            
    print("")

    # [안전장치] 중복 종목 제거 (동일 stock_code가 여러번 들어온 경우 방지)
    unique_holdings = {}
    for h in all_holdings:
        code = h['stock_code']
        # 이미 있으면 덮어쓰거나 무시 (최신 페이지 데이터가 더 정확하다고 가정하거나, API 특성상 단순 중복일 가능성 높음)
        if code not in unique_holdings:
            unique_holdings[code] = h
    
    final_holdings = list(unique_holdings.values())
    
    # IRP 현금 = 총자산 - 주식평가합 (역산)
    sum_holdings = sum(h['eval_amt'] for h in final_holdings)
    
    if cash_amt == 0:
        cash_amt = tot_amt - sum_holdings
    
    return {
        "total_asset": tot_amt,
        "total_stock": sum_holdings,
        "total_cash": cash_amt,
        "holdings": final_holdings
    }

def process_account(account_info, token, app_key, app_secret, supabase):
    name = account_info['name']
    acc_no = account_info['acc_no']
    
    # 계좌번호 뒷자리가 '29'로 끝나면 IRP로 자동 인식
    is_irp = acc_no.endswith('29') or "IRP" in name.upper() or "퇴직" in name

    print(f"   📊 [{name}] 잔고 조회 시작... ({'IRP/연금' if is_irp else '일반주식'})")

    if is_irp:
        result = fetch_balance_irp(token, app_key, app_secret, acc_no)
    else:
        result = fetch_balance_stock(token, app_key, app_secret, acc_no)
        
    if not result:
        return

    # ====================================================
    # DB 저장 로직
    # ====================================================
    
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    today_str = now_kst.strftime("%Y-%m-%d")
    
    snapshot_data = {
        "account_no": acc_no,
        "account_name": name,
        "record_date": today_str,
        "recorded_at": now_kst.isoformat(),
        "total_asset": result['total_asset'],
        "total_stock_amt": result['total_stock'],
        "total_cash": result['total_cash']
    }

    res_master = supabase.table("asset_snapshot").upsert(
        snapshot_data, on_conflict="account_no, record_date"
    ).execute()
    
    if not res_master.data:
        print("   ❌ DB 저장 실패")
        return

    snapshot_id = res_master.data[0]['id']

    # 상세 내역 저장
    supabase.table("asset_holdings").delete().eq("snapshot_id", snapshot_id).execute()
    
    holdings_data = []
    for item in result['holdings']:
        if not item['stock_code']: continue
        
        item['snapshot_id'] = snapshot_id
        holdings_data.append(item)

    if holdings_data:
        supabase.table("asset_holdings").insert(holdings_data).execute()
        print(f"   ✅ 저장 완료 (자산: {result['total_asset']:,}원 / 종목수: {len(holdings_data)}개)")
    else:
        print(f"   ✅ 저장 완료 (보유종목 없음)")

def main():
    print("=== 🚀 GitHub Actions 자산 백업 시작 ===")
    
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    except Exception as e:
        print(f"❌ Supabase 접속 실패: {e}")
        return

    for idx, account in enumerate(ACCOUNTS):
        
        # Keyring에서 토큰 가져오기 (access_token_0, access_token_1, ...)
        # Service: access_token_{idx}, Username: birdblues
        service_name = f"access_token_{idx}"
        token = keyring.get_password(service_name, "birdblues")
        
        if not token:
            print(f"❌ [Error] Keyring에서 토큰을 찾을 수 없습니다: {service_name}")
            continue 

        # Keyring에서 API Key/Secret 가져오기
        # .env의 ACCOUNTS_JSON에 정의된 값을 Service Name으로 사용
        key_service = account['app_key']
        secret_service = account['app_secret']

        app_key = keyring.get_password(key_service, "birdblues")
        app_secret = keyring.get_password(secret_service, "birdblues")

        if not app_key or not app_secret:
             print(f"❌ [Error] Keyring에서 App Key/Secret을 찾을 수 없습니다: {key_service} / {secret_service}")
             continue

        try:
            process_account(account, token, app_key, app_secret, supabase)
        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        
        time.sleep(1)

    print("\n=== ✨ 작업 완료 ===")

if __name__ == "__main__":
    main()