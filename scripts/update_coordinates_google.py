import requests
import json
import os
import time

# ==========================================
# [설정] 본인의 Google Maps API 키를 입력하세요
GOOGLE_API_KEY = "mine"
# ==========================================

# --- 파일 경로 설정 ---
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')
STORES_FILE = os.path.join(DATA_DIR, 'stores.json')

def clean_address_string(address):
    """
    주소 정제 로직:
    1. '(' 뒷부분 제거
    2. ',' 뒷부분 제거
    3. 앞뒤 공백 제거
    """
    # '(' 기준으로 자르고 첫 번째 부분 선택
    addr = address.split('(')[0]
    # ',' 기준으로 자르고 첫 번째 부분 선택
    addr = addr.split(',')[0]
    return addr.strip()

def get_lat_lng_google(address):
    """
    Google Geocoding API를 사용하여 주소를 좌표로 변환
    """
    base_url = "https://maps.googleapis.com/maps/api/geocode/json"
    
    params = {
        "address": address,
        "key": GOOGLE_API_KEY,
        "language": "ko" # 한국어 결과 우선
    }

    try:
        response = requests.get(base_url, params=params, timeout=10)
        
        if response.status_code == 200:
            result = response.json()
            if result['status'] == 'OK':
                location = result['results'][0]['geometry']['location']
                return location['lat'], location['lng']
            else:
                # ZERO_RESULTS, OVER_QUERY_LIMIT 등
                # print(f"  API 상태: {result['status']}")
                return None, None
        else:
            print(f"❌ HTTP 요청 실패: {response.status_code}")
            return None, None

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return None, None

def update_missing_coordinates():
    print("🚀 Google Maps API로 누락된 좌표 보완을 시작합니다...")

    if not os.path.exists(STORES_FILE):
        print(f"❌ {STORES_FILE} 파일이 없습니다.")
        return

    # 1. 파일 읽기
    with open(STORES_FILE, 'r', encoding='utf-8') as f:
        stores_list = json.load(f)

    total_count = len(stores_list)
    updated_count = 0
    skipped_count = 0 # 이미 있거나 온라인이라 건너뛴 것
    failed_count = 0

    print(f"📊 총 {total_count}개의 데이터를 스캔합니다.")

    # 2. 순회
    for idx, store in enumerate(stores_list):
        address = store.get('address', '')
        current_lat = store.get('lat', 0.0)
        current_lng = store.get('lng', 0.0)

        # [조건 1] 온라인 판매점 제외
        if "dhlottery.co.kr" in address or "동행복권" in address:
            skipped_count += 1
            continue

        # [조건 2] 이미 좌표가 있는 경우 건너뜀 (0.0이 아닌 경우)
        if current_lat != 0.0 and current_lng != 0.0:
            skipped_count += 1
            continue

        # --- 여기서부터는 좌표가 없는(0.0) 데이터입니다 ---
        
        # [정제] 주소 클리닝 (괄호, 콤마 제거)
        clean_addr = clean_address_string(address)
        
        print(f"[{idx+1}/{total_count}] 보완 시도: {clean_addr} (원본: {address}) ... ", end="")

        lat, lng = get_lat_lng_google(clean_addr)

        if lat is not None and lng is not None:
            store['lat'] = lat
            store['lng'] = lng
            updated_count += 1
            print(f"✅ 성공 ({lat}, {lng})")
        else:
            failed_count += 1
            print(f"⚠️ 실패")

        # Google API도 짧은 시간 과다 요청 시 제한될 수 있음
        time.sleep(0.1)

        # 중간 저장 (데이터 보호)
        if updated_count > 0 and updated_count % 50 == 0:
            with open(STORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(stores_list, f, ensure_ascii=False, indent=2)
            print("  💾 중간 저장 완료")

    # 3. 최종 저장
    with open(STORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(stores_list, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print(f"🎉 작업 완료!")
    print(f" - 총 스캔: {total_count}")
    print(f" - 신규 성공: {updated_count}")
    print(f" - 건너뜀(기존존재/온라인): {skipped_count}")
    print(f" - 최종 실패: {failed_count}")
    print(f" - 파일 저장: {STORES_FILE}")
    print("="*50)

if __name__ == "__main__":
    if GOOGLE_API_KEY == "YOUR_GOOGLE_MAPS_API_KEY":
        print("❌ 오류: GOOGLE_API_KEY 변수에 실제 키를 입력해주세요.")
    else:
        update_missing_coordinates()