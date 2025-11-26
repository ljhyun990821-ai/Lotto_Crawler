import requests
import json
import os
import time

# ==========================================
# [설정] 본인의 카카오 REST API 키를 여기에 입력하세요
KAKAO_API_KEY = "mine"
# ==========================================

# --- 파일 경로 설정 ---
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')
STORES_FILE = os.path.join(DATA_DIR, 'stores.json')

def get_lat_lng_from_kakao(query):
    """
    카카오 로컬 API를 사용하여 주소를 좌표(lat, lng)로 변환
    """
    url = 'https://dapi.kakao.com/v2/local/search/address.json'
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    params = {"query": query}

    try:
        response = requests.get(url, headers=headers, params=params, timeout=5)
        
        if response.status_code == 200:
            result = response.json()
            documents = result.get('documents', [])

            if documents:
                # 정확도순 등 고려할 수도 있으나, 보통 첫 번째 결과가 가장 정확함
                address_info = documents[0]
                lat = float(address_info['y'])
                lng = float(address_info['x'])
                return lat, lng
            else:
                return None, None
        else:
            print(f"❌ API 요청 실패: {response.status_code}")
            return None, None

    except Exception as e:
        print(f"❌ 에러 발생: {e}")
        return None, None

def update_coordinates():
    print("🚀 Kakao Map API를 이용하여 좌표 업데이트를 시작합니다...")

    if not os.path.exists(STORES_FILE):
        print(f"❌ {STORES_FILE} 파일이 없습니다. 먼저 stores.json을 생성해주세요.")
        return

    # 1. 파일 읽기
    with open(STORES_FILE, 'r', encoding='utf-8') as f:
        stores_list = json.load(f)

    total_count = len(stores_list)
    updated_count = 0
    failed_count = 0
    skipped_count = 0
    online_excluded_count = 0

    print(f"📊 총 {total_count}개의 판매점 데이터를 확인합니다.")

    # 2. 순회하며 좌표 업데이트
    for idx, store in enumerate(stores_list):
        name = store.get('name', 'Unknown')
        address = store.get('address', '')
        
        # [요청 1] 온라인 판매점 제외 ("동행복권(dhlottery.co.kr)")
        if "dhlottery.co.kr" in address or "동행복권" in address:
            # 온라인은 좌표를 0,0으로 유지하거나 필요시 특정 값으로 설정
            online_excluded_count += 1
            # print(f"[{idx+1}] 🌐 온라인 판매점 제외")
            continue

        # 이미 좌표가 있는 경우(0.0이 아닌 경우) 건너뛰기
        if store.get('lat') != 0.0 and store.get('lng') != 0.0:
            skipped_count += 1
            continue

        print(f"[{idx+1}/{total_count}] 검색: {name}", end="")

        # 1차 시도: 원본 주소로 검색
        lat, lng = get_lat_lng_from_kakao(address)

        # [요청 2] 실패 시 괄호 제거 후 재시도 로직
        if lat is None:
            # '(' 기준으로 자르고 앞부분만 가져옴 (공백 제거 포함)
            clean_address = address.split('(')[0].strip()
            
            # 정제된 주소가 원본과 다를 때만 재시도 (똑같으면 시도할 필요 없음)
            if clean_address != address and len(clean_address) > 2:
                print(f" ➡️ 재시도('{clean_address}')", end="")
                lat, lng = get_lat_lng_from_kakao(clean_address)

        # 결과 처리
        if lat is not None and lng is not None:
            store['lat'] = lat
            store['lng'] = lng
            updated_count += 1
            print(f" ✅ 성공")
        else:
            failed_count += 1
            print(f" ⚠️ 실패 (주소: {address})")

        # 카카오 API 제한 보호 (너무 빠르면 차단됨)
        time.sleep(0.1) 
        
        # 100건마다 중간 저장
        if updated_count > 0 and updated_count % 100 == 0:
             with open(STORES_FILE, 'w', encoding='utf-8') as f:
                json.dump(stores_list, f, ensure_ascii=False, indent=2)
             print("  💾 중간 저장 완료")

    # 3. 최종 저장
    with open(STORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(stores_list, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print(f"🎉 작업 완료!")
    print(f" - 총 데이터: {total_count}개")
    print(f" - 신규 업데이트: {updated_count}개")
    print(f" - 온라인 제외: {online_excluded_count}개")
    print(f" - 이미 존재(스킵): {skipped_count}개")
    print(f" - 실패(주소오류): {failed_count}개")
    print(f" - 저장 경로: {STORES_FILE}")
    print("="*50)

if __name__ == "__main__":
    if KAKAO_API_KEY == "여기에_REST_API_키를_넣으세요":
        print("❌ 오류: 스크립트 상단의 KAKAO_API_KEY 변수에 실제 키를 입력해주세요.")
    else:
        update_coordinates()