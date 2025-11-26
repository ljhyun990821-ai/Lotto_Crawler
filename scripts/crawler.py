import requests
from bs4 import BeautifulSoup
import json
import os
import argparse
import sys # 에러 발생 시 GitHub Actions을 실패 처리하기 위해 추가

# 경로 설정 (프로젝트 루트 기준)
# 로컬이나 GitHub Actions 어디서든 'assets/data'를 잘 찾도록 설정
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')
LATEST_FILE = os.path.join(DATA_DIR, 'latest.json')
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')
STORES_FILE = os.path.join(DATA_DIR, 'stores.json')

def get_latest_numbers():
    url = 'https://dhlottery.co.kr/gameResult.do?method=byWin'
    try:
        response = requests.get(url, timeout=10) # 타임아웃 추가
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
            
        bonus_number = numbers.pop() # 마지막은 보너스 번호
        winning_numbers = numbers

        # 4. 1등 당첨금 파싱 (구조 변경에 대비해 예외처리 강화)
        try:
            # 당첨금 테이블의 첫 번째 행(1등), 4번째 열(1인당 당첨금) 가져오기
            rows = soup.select('.tbl_data tbody tr')
            first_row = rows[0]
            cells = first_row.find_all('td')
            # 보통 당첨금은 오른쪽 정렬(.tar) 되어 있음. 값: "2,512,345,678원"
            prize_text = cells[3].text 
            prize = int(prize_text.replace(',', '').replace('원', '').strip())
        except Exception as e:
            print(f"Warning: 당첨금 파싱 실패 ({e}). 0원으로 저장합니다.")
            prize = 0

        return {
            'round': round_num,
            'date': date_text,
            'numbers': winning_numbers,
            'bonus': bonus_number,
            'prize': prize
        }
    except Exception as e:
        print(f"Error crawling latest numbers: {e}")
        return None

def update_weekly():
    print(f"Running Weekly Update... (Target Dir: {DATA_DIR})")
    latest_data = get_latest_numbers()
    
    if not latest_data:
        print("Failed to get latest data.")
        sys.exit(1) # GitHub Actions를 실패로 처리

    # 폴더가 없으면 생성
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    # 1. Update latest.json
    with open(LATEST_FILE, 'w', encoding='utf-8') as f:
        json.dump(latest_data, f, ensure_ascii=False, indent=2)
    print(f"✅ Updated {LATEST_FILE} (Round {latest_data['round']})")

    # 2. Update history.json
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
        except json.JSONDecodeError:
            history = [] # 파일이 깨져있으면 초기화
    
    # 중복 체크 (이미 있는 회차면 저장 안 함)
    if not any(item['round'] == latest_data['round'] for item in history):
        history.insert(0, {
            'round': latest_data['round'],
            'date': latest_data['date'],
            'numbers': latest_data['numbers'],
            'bonus': latest_data['bonus'],
            'prize': latest_data['prize']
        })
        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        print(f"✅ Updated {HISTORY_FILE}")
    else:
        print("ℹ️ Latest round already in history.")

    print("Weekly update complete.")

def update_monthly():
    print("Running Monthly Update...")
    # 추후 판매점 로직 구현
    print("Monthly update logic is not yet implemented.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='LottoNova Crawler')
    parser.add_argument('--mode', type=str, choices=['weekly', 'monthly'], required=True, help='Update mode')
    args = parser.parse_args()

    if args.mode == 'weekly':
        update_weekly()
    elif args.mode == 'monthly':
        update_monthly()