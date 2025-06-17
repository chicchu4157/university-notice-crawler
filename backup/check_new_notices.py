import json
import os
from datetime import datetime, timedelta

def check_new_notices():
    # data 폴더의 최신 2개 파일 비교
    files = sorted([f for f in os.listdir('data') if f.endswith('.json')])
    
    if len(files) < 2:
        print("비교할 이전 데이터가 없습니다.")
        return
    
    # 최신 파일과 이전 파일 로드
    with open(f'data/{files[-1]}', 'r', encoding='utf-8') as f:
        current = json.load(f)
    with open(f'data/{files[-2]}', 'r', encoding='utf-8') as f:
        previous = json.load(f)
    
    # 새 공지사항 찾기
    new_notices = []
    for curr_univ in current:
        prev_univ = next((u for u in previous if u['code'] == curr_univ['code']), None)
        if prev_univ and curr_univ['success']:
            prev_titles = {n['title'] for n in prev_univ.get('notices', [])}
            for notice in curr_univ['notices']:
                if notice['title'] not in prev_titles:
                    new_notices.append({
                        'university': curr_univ['university'],
                        'notice': notice
                    })
    
    # 결과 출력
    if new_notices:
        print(f"\n🆕 새로운 공지사항 {len(new_notices)}개 발견!")
        for item in new_notices:
            print(f"\n[{item['university']}]")
            print(f"제목: {item['notice']['title']}")
            print(f"날짜: {item['notice']['date']}")
    else:
        print("\n새로운 공지사항이 없습니다.")

if __name__ == "__main__":
    check_new_notices()
