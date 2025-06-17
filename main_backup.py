import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import os

def load_config():
    with open('config.json', 'r', encoding='utf-8') as f:
        return json.load(f)

def crawl_university(univ_info):
    """각 대학의 공지사항을 크롤링"""
    print(f"\n{'='*50}")
    print(f"크롤링 시작: {univ_info['name']}")
    print(f"URL: {univ_info['notice_url']}")
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'ko-KR,ko;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
        
        response = requests.get(univ_info['notice_url'], headers=headers, timeout=15)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        notices = []
        
        # 디버깅 정보
        print(f"응답 상태: {response.status_code}")
        
        # 공지사항 목록 추출
        notice_list = soup.select(univ_info['selector']['list'])
        print(f"찾은 항목 수: {len(notice_list)}")
        
        if not notice_list:
            print(f"  ! 선택자 '{univ_info['selector']['list']}'로 항목을 찾을 수 없음")
            # HTML 일부 출력하여 구조 확인
            print(f"  ! HTML 샘플: {soup.prettify()[:500]}...")
        
        for idx, item in enumerate(notice_list[:5]):  # 최근 5개만
            try:
                title_elem = item.select_one(univ_info['selector']['title'])
                date_elem = item.select_one(univ_info['selector']['date'])
                link_elem = item.select_one(univ_info['selector']['link'])
                
                if title_elem:
                    # 제목에서 불필요한 공백 제거
                    title = ' '.join(title_elem.get_text().split())
                    
                    # 링크 처리 (상대 경로인 경우 절대 경로로 변환)
                    link = ''
                    if link_elem and link_elem.get('href'):
                        link = link_elem.get('href')
                        if link.startswith('/'):
                            from urllib.parse import urljoin
                            link = urljoin(univ_info['notice_url'], link)
                    
                    notice = {
                        'title': title,
                        'date': date_elem.get_text(strip=True) if date_elem else '',
                        'link': link,
                        'university': univ_info['name']
                    }
                    notices.append(notice)
                    print(f"  ✓ {notice['title'][:50]}...")
                else:
                    print(f"  ! {idx+1}번째 항목에서 제목을 찾을 수 없음")
                    
            except Exception as e:
                print(f"  ! 항목 파싱 오류: {str(e)}")
                continue
        
        return {
            'university': univ_info['name'],
            'code': univ_info['code'],
            'success': True,
            'notices': notices,
            'crawled_at': datetime.now().isoformat()
        }
        
    except requests.exceptions.RequestException as e:
        print(f"  ! 네트워크 오류: {str(e)}")
    except Exception as e:
        print(f"  ! 크롤링 실패: {str(e)}")
        import traceback
        traceback.print_exc()
        
    return {
        'university': univ_info['name'],
        'code': univ_info['code'],
        'success': False,
        'error': str(e),
        'crawled_at': datetime.now().isoformat()
    }

def save_results(results):
    """결과를 JSON 파일로 저장"""
    # data 폴더가 없으면 생성
    if not os.path.exists('data'):
        os.makedirs('data')
    
    # 날짜별 파일명
    filename = f"data/notices_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print(f"\n결과 저장 완료: {filename}")
    return filename

def main():
    print("대학 공지사항 크롤러 시작")
    print(f"실행 시간: {datetime.now()}")
    
    # 설정 로드
    config = load_config()
    
    # 각 대학 크롤링
    results = []
    for univ in config['universities']:
        result = crawl_university(univ)
        results.append(result)
    
    # 결과 저장
    save_results(results)
    
    # 요약
    success_count = sum(1 for r in results if r['success'])
    print(f"\n크롤링 완료: 성공 {success_count}/{len(results)}")

if __name__ == "__main__":
    main()
