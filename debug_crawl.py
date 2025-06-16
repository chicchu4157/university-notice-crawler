import requests
from bs4 import BeautifulSoup

def debug_university_site(name, url):
    print(f"\n{'='*60}")
    print(f"테스트: {name}")
    print(f"URL: {url}")
    print('='*60)
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        print(f"상태 코드: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 일반적인 게시판 선택자들 시도
            selectors_to_try = [
                'table tbody tr',
                'ul.board-list li',
                'div.board-list',
                'div.list-wrap',
                '.notice-list',
                '.bbs-list',
                'div[class*="list"] tr',
                'div[class*="board"] tr',
                'ul[class*="list"] li'
            ]
            
            print("\n가능한 선택자 테스트:")
            for selector in selectors_to_try:
                elements = soup.select(selector)
                if elements:
                    print(f"✓ '{selector}' → {len(elements)}개 발견")
                    
                    # 첫 번째 요소의 텍스트 샘플 출력
                    if len(elements) > 0:
                        first_elem = elements[0]
                        text = first_elem.get_text(strip=True)[:100]
                        print(f"  샘플: {text}...")
            
            # HTML 일부 출력 (디버깅용)
            print(f"\nHTML 일부 (처음 1000자):")
            print(response.text[:1000])
            
    except Exception as e:
        print(f"오류: {str(e)}")

# 실제 대학 입학처 URL로 테스트
test_universities = [
    ("서울대학교", "https://admission.snu.ac.kr/undergraduate/notice"),
    ("연세대학교", "https://admission.yonsei.ac.kr/seoul/admission/html/rolling/notice.asp"),
    ("고려대학교", "https://oku.korea.ac.kr/oku/index.do")
]

for name, url in test_universities:
    debug_university_site(name, url)
