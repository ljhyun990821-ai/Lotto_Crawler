import json
import os
import sys
# Store에 대한 Dislike 관리 스크립 ------------------------------------------------------


# --- 설정 ---
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')
STORES_FILE = os.path.join(DATA_DIR, 'stores.json')
DELETE_STORES_FILE = os.path.join(DATA_DIR, 'Delete_stores.json')

def normalize_key(store):
    """중복 방지를 위한 고유 키 생성 (이름+주소)"""
    name = store.get('name', '').replace(' ', '').strip()
    addr = store.get('address', '').replace(' ', '').strip()
    return f"{name}|{addr}"

def filter_bad_stores():
    print("🧹 판매점 데이터 정리 시작 (싫어요 > 30 필터링)...")

    if not os.path.exists(STORES_FILE):
        print(f"❌ {STORES_FILE} 파일을 찾을 수 없습니다.")
        return

    # 1. 데이터 로드
    try:
        with open(STORES_FILE, 'r', encoding='utf-8') as f:
            all_stores = json.load(f)
    except json.JSONDecodeError:
        print("❌ stores.json 파일이 손상되었습니다.")
        return

    # 삭제 목록 로드 (기존 데이터 유지)
    deleted_stores = []
    if os.path.exists(DELETE_STORES_FILE):
        try:
            with open(DELETE_STORES_FILE, 'r', encoding='utf-8') as f:
                deleted_stores = json.load(f)
        except:
            pass

    # 삭제 목록 맵핑 (중복 방지 및 업데이트용)
    deleted_map = {normalize_key(s): i for i, s in enumerate(deleted_stores)}

    valid_stores = []
    moved_count = 0

    # 2. 필터링 로직
    for store in all_stores:
        dislikes = store.get('dislikes', 0)
        
        if dislikes > 30:
            print(f"🚫 차단: {store['name']} (싫어요 {dislikes}개) -> Delete_stores.json으로 이동")
            
            # 고유 키 생성
            key = normalize_key(store)
            
            # 이미 삭제 목록에 있다면 정보 갱신(업데이트), 없으면 추가
            if key in deleted_map:
                deleted_stores[deleted_map[key]] = store
            else:
                deleted_stores.append(store)
                # 맵 갱신 (다음 루프 중복 방지용)
                deleted_map[key] = len(deleted_stores) - 1
            
            moved_count += 1
        else:
            valid_stores.append(store)

    # 3. 결과 저장
    if moved_count > 0:
        # 유효한 매장만 다시 저장
        with open(STORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(valid_stores, f, ensure_ascii=False, indent=2)
        
        # 차단된 매장 저장
        with open(DELETE_STORES_FILE, 'w', encoding='utf-8') as f:
            json.dump(deleted_stores, f, ensure_ascii=False, indent=2)
            
        print(f"\n✅ 정리 완료!")
        print(f"  - 기존 매장 수: {len(all_stores)}개")
        print(f"  - 차단된 매장 수: {moved_count}개")
        print(f"  - 남은 매장 수: {len(valid_stores)}개")
    else:
        print("\n✅ 차단할 매장이 없습니다. (모든 매장이 싫어요 30개 이하)")

if __name__ == "__main__":
    # 데이터 폴더가 없으면 생성
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    filter_bad_stores()