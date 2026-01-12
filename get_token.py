import json
import requests
import time
from datetime import datetime, timedelta, timezone
import os

AUTH_FILE = "kis_auth.json"
BASE_URL = "https://openapi.koreainvestment.com:9443"

def load_auth_data():
    if not os.path.exists(AUTH_FILE):
        return []
    with open(AUTH_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_auth_data(data):
    with open(AUTH_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

def get_new_token(app_key, app_secret):
    url = f"{BASE_URL}/oauth2/tokenP"
    headers = {"content-type": "application/json"}
    body = {
        "grant_type": "client_credentials",
        "appkey": app_key,
        "appsecret": app_secret
    }
    
    try:
        res = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
        res_json = res.json()
        
        if res.status_code == 200 and 'access_token' in res_json:
            return res_json['access_token'], res_json.get('access_token_token_expired')
        else:
            print(f"❌ 토큰 발급 실패 ({res.status_code}): {res_json.get('error_description', res.text)}")
            return None, None
    except Exception as e:
        print(f"❌ 요청 중 에러: {e}")
        return None, None

def refresh_tokens():
    print(f"🔄 토큰 점검 및 갱신 시작 ({AUTH_FILE})")
    data = load_auth_data()
    
    if not data:
        print(f"⚠️ {AUTH_FILE} 파일이 없거나 비어있습니다.")
        print("   다음 형식으로 파일을 생성해주세요:")
        print('   [{"name": "계좌별칭", "app_key": "...", "app_secret": "...", "acc_no": "..."}]')
        return

    updated = False
    # KST 설정
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)

    # 1. app_key별로 계좌(항목) 그룹화
    # key: app_key, value: list of item dicts
    key_groups = {}
    for item in data:
        app_key = item.get('app_key')
        if not app_key:
            continue
        if app_key not in key_groups:
            key_groups[app_key] = []
        key_groups[app_key].append(item)

    # 2. 그룹별로 토큰 점검 및 갱신
    for app_key, items in key_groups.items():
        # 그룹 내 첫 번째 항목을 기준으로 상태 확인 (모두 공유하므로)
        first_item = items[0]
        app_secret = first_item.get('app_secret')
        
        if not app_secret:
            print(f"❌ [AppKey: ...{app_key[-4:]}] App Secret 누락")
            continue

        current_token = first_item.get('token')
        issued_at_str = first_item.get('token_issued_at')
        
        should_refresh = False
        status_msg = ""

        # 토큰 유효성 검사
        if not current_token or not issued_at_str:
            should_refresh = True
            status_msg = "토큰 없음"
        else:
            try:
                # 저장된 시간 파싱 (ISO format expected)
                last_issued = datetime.fromisoformat(issued_at_str)
                
                # naive datetime인 경우 KST로 가정하고 timezone 부여, 아니면 KST로 변환
                if last_issued.tzinfo is None:
                     last_issued = last_issued.replace(tzinfo=KST)
                else:
                     last_issued = last_issued.astimezone(KST)

                # 날짜가 다르면 갱신 (KST 기준)
                if last_issued.date() != now_kst.date():
                    should_refresh = True
                    status_msg = f"날짜 변경됨 (발급: {last_issued.date()}, 현재: {now_kst.date()})"
                # 안전장치: 23시간 경과시에도 갱신 (자정이 안 지났어도 너무 오래되면 갱신)
                elif now_kst - last_issued > timedelta(hours=23):
                    should_refresh = True
                    status_msg = f"23시간 경과 ({issued_at_str})"
                else:
                    # 유효함 -> 하지만 그룹 내 다른 계좌들이 비어있을 수 있으니 동기화 필요
                    pass
            except ValueError:
                should_refresh = True
                status_msg = "날짜 형식 오류"

        new_token_data = None
        
        if should_refresh:
            aliases = ", ".join([i.get('name', 'Unknown') for i in items])
            print(f"🔸 [{aliases}] {status_msg} -> 갱신 시도")
            
            new_token, expired_info = get_new_token(app_key, app_secret)
            if new_token:
                new_token_data = {
                    'token': new_token,
                    'token_issued_at': now_kst.isoformat(),
                    'api_expired_info': expired_info
                }
                print(f"   ✨ 토큰 발급 완료")
                updated = True
                time.sleep(0.5) 
            else:
                print(f"   ❌ 토큰 발급 실패")
        else:
            # 갱신 필요 없음 -> 기존 토큰 데이터 사용
            new_token_data = {
                'token': current_token,
                'token_issued_at': issued_at_str,
                'api_expired_info': first_item.get('api_expired_info')
            }
            # 별도 로그 생략하거나 간단히 출력
            # aliases = ", ".join([i.get('name', 'Unknown') for i in items])
            # print(f"✅ [{aliases}] 토큰 유효함")

        # 3. 확보된 토큰(새것이든 기존것이든)을 그룹 내 모든 항목에 적용 (동기화)
        if new_token_data:
            for item in items:
                # 변경사항이 있을 때만 updated=True 마킹 (기존 값과 다르면)
                if (item.get('token') != new_token_data['token'] or 
                    item.get('token_issued_at') != new_token_data['token_issued_at']):
                    
                    item['token'] = new_token_data['token']
                    item['token_issued_at'] = new_token_data['token_issued_at']
                    if new_token_data['api_expired_info']:
                        item['api_expired_info'] = new_token_data['api_expired_info']
                    updated = True

    if updated:
        save_auth_data(data)
        print("💾 변경사항이 파일에 저장되었습니다.")
    else:
        print("👌 변경사항 없음.")

if __name__ == "__main__":
    refresh_tokens()
