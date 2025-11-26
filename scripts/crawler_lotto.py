import requests
from bs4 import BeautifulSoup
import json
import os
import sys
import urllib3
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# --- [핵심] SSL 경고 무시 (서버 차단 방지) ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- 설정 ---
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')
LATEST_FILE = os.path.join(DATA_DIR, 'latest.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')

# --- 세션 설정 ---
session = requests.Session()
retries = Retry(
    total=5,
    connect=5,
    read=5,
    backoff_factor=1,
    status_forcelist=[500, 502, 503, 504],
    allowed_methods=["HEAD", "GET", "OPTIONS"]
)
session.mount('https://', HTTPAdapter(max_retries=retries))

# 봇 차단 완화용 헤더
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/129.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.dhlottery.co.kr/common.do?method=main"
})

def get_store_info(round_no):
    """해당 회차의 1등/2등 배출점 정보를 크롤링합니다."""
    url = f"https://dhlottery.co.kr/store.do?method=topStore&drwNo={round_no}"
    stores = {"1st": [], "2nd": []}
    
    try:
        response = session.get(url, timeout=10, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        tables = soup.select('table.tbl_data')
        
        # 1등 배출점
        if len(tables) >= 1:
            rows = tables[0].select('tbody tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 4:
                    try:
                        name = cols[1].text.strip()
                        method = cols[2].text.strip()
                        address = cols[3].text.strip()
                        if "조회 결과가 없습니다" not in name:
                            stores["1st"].append({"name": name, "addr": address, "method": method})
                    except: pass

        # 2등 배출점
        if len(tables) >= 2:
            rows = tables[1].select('tbody tr')
            for row in rows:
                cols = row.find_all('td')
                if len(cols) >= 3:
                    try:
                        name = cols[1].text.strip()
                        address = cols[2].text.strip()
                        if "조회 결과가 없습니다" not in name:
                            stores["2nd"].append({"name": name, "addr": address})
                    except: pass
                    
    except Exception as e:
        print(f"Warning: 판매점 정보 파싱 실패 ({e})")
    
    return stores

def get_latest_data():
    """메인 페이지에서 최신 정보(번호+상금)를 가져오고, 판매점 정보도 합칩니다."""
    url = 'https://dhlottery.co.kr/gameResult.do?method=byWin'
    
    try:
        response = session.get(url, timeout=10, verify=False)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 회차 파싱
        round_text = soup.select_one('.win_result h4 strong').text
        round_num = int(round_text.replace('회', ''))
        
        # 2. 날짜 파싱
        date_text = soup.select_one('.win_result .desc').text
        date_text = date_text.replace('(', '').replace(')', '').replace(' 추첨', '')
        
        # 3. 당첨 번호 파싱
        numbers = []
        ball_spans = soup.select('.ball_645')
        for span in ball_spans:
            numbers.append(int(span.text))
            
        bonus_number = numbers.pop()
        winning_numbers = numbers

        # 4. 상금 정보 파싱
        prizes = {
            "1st": {"prize": 0, "winners": 0},
            "2nd": {"prize": 0, "winners": 0},
            "3rd": {"prize": 0, "winners": 0}
        }

        try:
            rows = soup.select('.tbl_data tbody tr')
            for i, key in enumerate(["1st", "2nd", "3rd"]):
                if i >= len(rows): break
                row = rows[i]
                cells = row.find_all('td')
                
                prize_cell = None
                winner_cell = None
                
                for cell in reversed(cells):
                    txt = cell.text.strip()
                    if '원' in txt and prize_cell is None:
                        prize_cell = cell
                    elif prize_cell is not None and winner_cell is None:
                        winner_cell = cell
                        break
                
                if prize_cell and winner_cell:
                    prizes[key]["prize"] = int(prize_cell.text.replace(',', '').replace('원', '').strip())
                    prizes[key]["winners"] = int(winner_cell.text.replace(',', '').replace('개', '').strip())
        except Exception as e:
            print(f"Warning: 상금 파싱 중 오류 발생: {e}")

        # 5. 판매점 정보 추가
        print(f"🔎 {round_num}회차 판매점 정보를 수집합니다...")
        store_data = get_store_info(round_num)

        prizes["1st"]["stores"] = store_data["1st"]
        prizes["2nd"]["stores"] = store_data["2nd"]

        return {
            'round': round_num,
            'date': date_text,
            'numbers': winning_numbers,
            'bonus': bonus_number,
            'result': prizes 
        }

    except Exception as e:
        print(f"Error crawling latest data: {e}")
        return None

def update_weekly():
    print(f"🚀 Weekly Update Start... (Target: {DATA_DIR})")
    
    # 1. 최신 데이터 1건만 가져오기
    latest_data = get_latest_data()
    
    if not latest_data:
        print("❌ Failed to get data.")
        sys.exit(1)

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 2. latest.json 업데이트 (무조건 덮어쓰기)
    with open(LATEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Updated {LATEST_FILE} (Round {latest_data['round']})")

    # 3. history.json 업데이트 (없으면 추가)
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except json.JSONDecodeError:
            history = [] 
    
    # 중복 체크: 이미 해당 회차가 있는지 확인
    existing_rounds = {item['round'] for item in history}
    
    if latest_data['round'] not in existing_rounds:
        # 최신 데이터를 리스트 맨 앞에 삽입 (내림차순 유지)
        history.insert(0, latest_data)
        
        # 다시 저장
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"✅ Updated {HISTORY_FILE} (New round added)")
    else:
        print(f"ℹ️ History already contains round {latest_data['round']}. Skipping.")

    print("🎉 Update complete.")

if __name__ == "__main__":
    update_weekly()