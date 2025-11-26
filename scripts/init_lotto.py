import requests
from requests.exceptions import RequestException, ConnectionError as ReqConnectionError
from bs4 import BeautifulSoup
import json
import os
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

## 동행복권에서 로또 데이터 크롤링하는 코드 -------------------------------------------


# --- 설정 ---
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, 'assets', 'data')
HISTORY_FILE = os.path.join(DATA_DIR, 'history.json')

# 요청 간 간격(성능 < 안정성 기준으로 넉넉하게 설정)
GLOBAL_ROUND_DELAY = 3.0   # 회차 하나 끝날 때마다 대기 시간(초)
REQUEST_DELAY = 1.0        # 각 HTTP 요청 사이 최소 대기 시간(초)

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


def robust_request(method, url, desc="", max_retries=8, base_sleep=2.0, **kwargs):
    """
    GET/POST 공통 재시도 래퍼.
    - ConnectionReset(10054) → 지수 백오프로 여러 번 재시도
    - 5xx / 429 → 재시도
    - 4xx(404 포함) → 한 번만 찍고 스킵
    """
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.request(method, url, timeout=10, **kwargs)
            status = resp.status_code

            # 5xx, 429는 서버/부하 문제로 보고 재시도
            if status >= 500 or status == 429:
                raise RequestException(f"Server error {status}", response=resp)

            # 나머지 4xx/2xx 처리
            resp.raise_for_status()

            # 성공한 요청 사이도 살짝 텀을 준다
            if REQUEST_DELAY > 0:
                time.sleep(REQUEST_DELAY)

            return resp

        except ReqConnectionError as e:
            # 연결이 끊겼을 때(10054 등)
            wait = base_sleep * attempt
            print(f"\n⚠️ {desc} 연결 오류 {attempt}/{max_retries}회차, "
                  f"{wait:.1f}초 후 재시도: {e}")
            time.sleep(wait)

        except RequestException as e:
            status = getattr(e, "response", None).status_code if getattr(e, "response", None) is not None else None

            # 서버 에러 계열은 한 번 더 시도
            if status in (500, 502, 503, 504, 429):
                wait = base_sleep * attempt
                print(f"\n⚠️ {desc} 서버 오류 {status}, "
                      f"{attempt}/{max_retries}회차, {wait:.1f}초 후 재시도")
                time.sleep(wait)
                continue

            # 나머지(404 포함)는 재시도 의미 없다고 보고 종료
            print(f"\n⚠️ {desc} HTTP 오류: {e}")
            break

    print(f"\n⚠️ {desc} 재시도 {max_retries}회 모두 실패, 스킵합니다.")
    return None


def get_base_info_api(round_no: int):
    """1. 기본 번호 및 날짜 (API)"""
    url = f"https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={round_no}"
    desc = f"기본 정보 ({round_no}회)"

    try:
        resp = robust_request("GET", url, desc=desc)
        if resp is None:
            return None

        data = resp.json()
        if data.get("returnValue") == "fail":
            # 존재하지 않는 회차 → 크롤 종료 신호로 사용
            return None

        return data
    except Exception as e:
        print(f"⚠️ API 파싱 오류 ({round_no}회): {e}")
        return None


def get_prize_info(round_no: int):
    """2. 1~3등 상금 및 당첨자 수 (HTML 파싱)"""
    url = f"https://dhlottery.co.kr/gameResult.do?method=byWin&drwNo={round_no}"
    desc = f"상금 정보 ({round_no}회)"

    prizes = {
        "1st": {"prize": 0, "winners": 0},
        "2nd": {"prize": 0, "winners": 0},
        "3rd": {"prize": 0, "winners": 0},
    }

    resp = robust_request("GET", url, desc=desc)
    if resp is None:
        return prizes

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.select(".tbl_data tbody tr")

        for i, key in enumerate(["1st", "2nd", "3rd"]):
            if i >= len(rows):
                break

            row = rows[i]
            cells = row.find_all("td")

            try:
                prize_cell = None
                winner_cell = None

                # 뒤에서부터: '... 원' 들어간 마지막 셀 = 당첨금, 그 앞 = 인원
                for cell in reversed(cells):
                    txt = cell.text.strip()
                    if "원" in txt and prize_cell is None:
                        prize_cell = cell
                    elif prize_cell is not None and winner_cell is None:
                        winner_cell = cell
                        break

                if prize_cell and winner_cell:
                    prize_val = int(
                        prize_cell.text.replace(",", "").replace("원", "").strip()
                    )
                    winner_val = int(
                        winner_cell.text.replace(",", "").replace("개", "").strip()
                    )

                    prizes[key]["prize"] = prize_val
                    prizes[key]["winners"] = winner_val

            except Exception:
                # 개별 등수만 실패한 경우 → 그 등수는 0으로 남겨둠
                pass

    except Exception as e:
        print(f"⚠️ 상금 파싱 오류 ({round_no}회): {e}")

    return prizes


def get_store_info(round_no: int):
    """
    3. 판매점 정보 (HTML 파싱)
    - 동행복권 구조상:
      * URL: https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645
      * METHOD: POST
      * BODY: method=topStore&nowPage=1&gameNo=5133&drwNo=회차&...
    """
    stores = {"1st": [], "2nd": []}

    url = "https://dhlottery.co.kr/store.do?method=topStore&pageGubun=L645"
    desc = f"판매점 정보 ({round_no}회)"

    payload = {
        "method": "topStore",
        "nowPage": "1",
        "rankNo": "",       # 1등/2등 필터 (공란이면 기본 1등)
        "gameNo": "5133",   # 로또 6/45 gameNo (사이트에서 쓰는 값)
        "drwNo": str(round_no),
        "schKey": "all",
        "schVal": "",
    }

    resp = robust_request("POST", url, desc=desc, data=payload)
    if resp is None:
        return stores

    try:
        soup = BeautifulSoup(resp.text, "html.parser")
        tables = soup.select("table.tbl_data")

        print("----------------1--------------------")
        # 1등 배출점 테이블
        if len(tables) >= 1:
            rows = tables[1].select("tbody tr")

            print(rows)
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 4:
                    try:
                        print(cols)
                        name = cols[1].text.strip()
                        method = cols[2].text.strip()
                        address = cols[3].text.strip()
                        if "조회 결과가 없습니다" not in name:
                            stores["1st"].append(
                                {"name": name, "addr": address, "method": method}
                            )
                    except Exception:
                        pass
        

        print("------------------2------------------")
        # 2등 배출점 테이블 (있으면)
        if len(tables) >= 2:
            rows = tables[2].select("tbody tr")
            print(rows)
            for row in rows:
                cols = row.find_all("td")
                if len(cols) >= 3:
                    try:
                        print(cols)
                        name = cols[1].text.strip()
                        address = cols[2].text.strip()

                        if "조회 결과가 없습니다" not in name:
                            stores["2nd"].append(
                                {"name": name, "addr": address}
                            )
                    except Exception:
                        pass
        
        print("----------------end------------------")
    except Exception as e:
        print(f"⚠️ 판매점 파싱 오류 ({round_no}회): {e}")

    return stores


def run_crawler():
    print("🚀 로또 전체 데이터 수집 시작 (상금/판매점 포함)...")

    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    history_data = []
    start_round = 1

    # 이어하기 로직
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history_data = json.load(f)
                if history_data:
                    max_round = max(item["round"] for item in history_data)
                    start_round = max_round + 1
                    print(f"🔄 기존 데이터 발견! {start_round}회차부터 이어합니다.")
        except Exception:
            print("ℹ️ 처음부터 시작합니다.")

    current_round = start_round

    while True:
        print(f"[{current_round}회차] 수집 중...", end=" ", flush=True)

        # 1. 기본 정보 (없으면 이 시점에서 전체 종료)
        api_data = get_base_info_api(current_round)
        if api_data is None:
            print("\n🎉 수집 완료!")
            break

        # 2. 상금 정보
        prize_data = get_prize_info(current_round)

        # 3. 판매점 정보
        store_data = get_store_info(current_round)

        # 4. 데이터 조립
        formatted_data = {
            "round": api_data["drwNo"],
            "date": api_data["drwNoDate"],
            "numbers": [
                api_data["drwtNo1"],
                api_data["drwtNo2"],
                api_data["drwtNo3"],
                api_data["drwtNo4"],
                api_data["drwtNo5"],
                api_data["drwtNo6"],
            ],
            "bonus": api_data["bnusNo"],
            "result": {
                "1st": {
                    "prize": prize_data["1st"]["prize"],
                    "winners": prize_data["1st"]["winners"],
                    "stores": store_data["1st"],
                },
                "2nd": {
                    "prize": prize_data["2nd"]["prize"],
                    "winners": prize_data["2nd"]["winners"],
                    "stores": store_data["2nd"],
                },
                "3rd": {
                    "prize": prize_data["3rd"]["prize"],
                    "winners": prize_data["3rd"]["winners"],
                    # 3등은 판매점 정보가 너무 많아 수집하지 않음
                },
            },
        }

        # 최신순 유지를 위해 맨 앞에 삽입
        history_data.insert(0, formatted_data)

        print(
            f"✅ (1등: {len(store_data['1st'])}곳, "
            f"2등: {len(store_data['2nd'])}곳)"
        )

        # 중간 저장 (10회차마다)
        if current_round % 10 == 0:
            history_data.sort(key=lambda x: x["round"], reverse=True)
            with open(HISTORY_FILE, "w", encoding="utf-8") as f:
                json.dump(history_data, f, ensure_ascii=False, indent=2)
            print("💾 중간 저장")

        current_round += 1

        # 회차 사이 전체 딜레이
        if GLOBAL_ROUND_DELAY > 0:
            time.sleep(GLOBAL_ROUND_DELAY)

    # 최종 저장
    history_data.sort(key=lambda x: x["round"], reverse=True)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)
    print(f"\n✨ {HISTORY_FILE} 저장 완료!")


if __name__ == "__main__":
    run_crawler()
