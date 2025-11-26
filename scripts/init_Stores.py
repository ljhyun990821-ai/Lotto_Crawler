import json
import os
# 초기 store 구성 >> 로또 당첨지에 대한 ㅇㅇ


# --- 파일 경로 설정 ---
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')

# 입력 파일 (기존 크롤링한 데이터)
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')
# 출력 파일 (생성될 파일)
STORES_FILE = os.path.join(DATA_DIR, 'stores.json')

def normalize_key(name, addr):
    """
    판매점을 구분하는 고유 키 생성
    이름과 주소의 공백을 제거하고 합쳐서 비교 (오타/공백 차이 방지)
    """
    n = name.replace(' ', '').strip()
    a = addr.replace(' ', '').strip()
    return f"{n}|{a}"

def create_stores_from_history():
    print("📂 history.json 데이터를 기반으로 stores.json 생성을 시작합니다...")

    if not os.path.exists(HISTORY_FILE):
        print(f"❌ {HISTORY_FILE} 파일이 없습니다.")
        return

    # 1. history.json 읽기
    with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
        history_data = json.load(f)

    # 2. 데이터 집계를 위한 딕셔너리
    # Key: "이름|주소", Value: Store 객체
    stores_map = {}

    # 3. 데이터 순회 및 집계
    for round_data in history_data:
        round_no = round_data['round']
        result = round_data.get('result', {})

        # 1등, 2등 각각 처리
        for rank in ['1st', '2nd']:
            rank_data = result.get(rank, {})
            # history.json 구조상 stores 키가 없는 경우(3등 등) 대비
            store_list = rank_data.get('stores', [])

            if not store_list:
                continue

            for entry in store_list:
                name = entry['name']
                # history.json은 'addr'이지만 stores.json은 'address'로 저장
                addr = entry.get('addr', '') 
                
                # 고유 키 생성
                key = normalize_key(name, addr)

                # 이미 등록된 판매점인지 확인
                if key not in stores_map:
                    # 신규 등록
                    stores_map[key] = {
                        "name": name,
                        "address": addr,
                        "phone": "",  # 초기값 공란
                        "wins": {
                            "1st": [],
                            "2nd": []
                        },
                        "likes": 0,
                        "dislikes": 0,
                        # 요청하신 위도/경도 초기값 (lat: 위도-y, lng: 경도-x)
                        "lat": 0.0, 
                        "lng": 0.0
                    }
                
                # 해당 등수의 당첨 회차 추가
                # 리스트에 이미 있는지 확인 (중복 방지)
                if round_no not in stores_map[key]['wins'][rank]:
                    stores_map[key]['wins'][rank].append(round_no)

    # 4. 리스트 형태로 변환
    stores_list = list(stores_map.values())

    # (옵션) 회차 정렬: 최신 회차가 앞으로 오도록 내림차순 정렬
    for store in stores_list:
        store['wins']['1st'].sort(reverse=True)
        store['wins']['2nd'].sort(reverse=True)

    print(f"📊 총 {len(stores_list)}개의 판매점이 추출되었습니다.")

    # 5. 파일 저장
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    with open(STORES_FILE, 'w', encoding='utf-8') as f:
        json.dump(stores_list, f, ensure_ascii=False, indent=2)

    print(f"✨ 저장 완료: {STORES_FILE}")

if __name__ == "__main__":
    create_stores_from_history()