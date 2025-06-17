"""
스마트 대학 공지사항 크롤러
하이브리드 접근법으로 자동 패턴 감지, 템플릿 기반, 수동 설정을 조합
"""

import re
import logging
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from urllib.parse import urljoin, urlparse
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
import time
import json
from collections import Counter

from .patterns import PatternDetector
from .templates import TemplateManager
from .utils import clean_text, parse_date, is_valid_url

class SmartCrawler:
    """지능형 대학 공지사항 크롤러"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.pattern_detector = PatternDetector(config)
        self.template_manager = TemplateManager()
        self.session = self._create_session()
        self.stats = {
            'auto_detect': 0,
            'template': 0,
            'custom': 0,
            'failed': 0
        }
        
    def _create_session(self) -> requests.Session:
        """HTTP 세션 생성"""
        session = requests.Session()
        session.headers.update({
            'User-Agent': self.config['crawler']['user_agent']
        })
        return session
    
    def crawl_university(self, url: str, univ_name: str) -> Dict[str, Any]:
        """대학 공지사항 크롤링 메인 함수"""
        self.logger.info(f"{univ_name} 크롤링 시작: {url}")
        
        try:
            # 1. 기본 HTML 가져오기
            soup = self._get_soup(url)
            if not soup:
                return self._create_result(False, error="페이지 로드 실패")
            
            # 2. 템플릿 확인
            template_result = self.template_manager.match_template(soup, url)
            if template_result['matched']:
                self.logger.info(f"{univ_name}: 템플릿 매칭 성공 - {template_result['template_name']}")
                notices = self._crawl_with_template(soup, template_result['template'], url)
                if notices:
                    self.stats['template'] += 1
                    return self._create_result(True, notices=notices, method='template')
            
            # 3. 자동 패턴 감지
            auto_result = self.pattern_detector.detect_notice_structure(soup)
            if auto_result['confidence'] >= self.config['detection']['min_confidence']:
                self.logger.info(f"{univ_name}: 자동 감지 성공 (신뢰도: {auto_result['confidence']:.2f})")
                notices = self._extract_notices_from_structure(soup, auto_result['structure'], url)
                if notices:
                    self.stats['auto_detect'] += 1
                    return self._create_result(True, notices=notices, method='auto_detect')
            
            # 4. 수동 설정 확인
            custom_result = self._try_custom_selectors(soup, url, univ_name)
            if custom_result:
                self.logger.info(f"{univ_name}: 수동 설정 성공")
                self.stats['custom'] += 1
                return self._create_result(True, notices=custom_result, method='custom')
            
            # 5. Selenium 폴백
            if self.config['fallback']['use_selenium']:
                selenium_result = self._try_selenium_fallback(url, univ_name)
                if selenium_result:
                    self.logger.info(f"{univ_name}: Selenium 폴백 성공")
                    return self._create_result(True, notices=selenium_result, method='selenium')
            
            # 모든 방법 실패
            self.stats['failed'] += 1
            return self._create_result(False, error="모든 크롤링 방법 실패")
            
        except Exception as e:
            self.logger.error(f"{univ_name} 크롤링 중 오류: {str(e)}", exc_info=True)
            self.stats['failed'] += 1
            return self._create_result(False, error=str(e))
    
    def _get_soup(self, url: str) -> Optional[BeautifulSoup]:
        """URL에서 BeautifulSoup 객체 생성"""
        try:
            response = self.session.get(
                url, 
                timeout=self.config['crawler']['timeout']
            )
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            
            return BeautifulSoup(response.text, 'lxml')
            
        except Exception as e:
            self.logger.error(f"페이지 로드 실패 {url}: {str(e)}")
            return None
    
    def _crawl_with_template(self, soup: BeautifulSoup, template: Dict, base_url: str) -> List[Dict]:
        """템플릿을 사용한 크롤링"""
        notices = []
        
        try:
            # 공지사항 목록 요소 찾기
            list_elements = soup.select(template['list_selector'])
            
            for element in list_elements:
                notice = self._extract_notice_from_element(element, template, base_url)
                if notice:
                    notices.append(notice)
            
            return self._validate_notices(notices)
            
        except Exception as e:
            self.logger.error(f"템플릿 크롤링 중 오류: {str(e)}")
            return []
    
    def _extract_notices_from_structure(self, soup: BeautifulSoup, structure: Dict, base_url: str) -> List[Dict]:
        """감지된 구조를 사용한 공지사항 추출"""
        notices = []
        
        try:
            container = soup.select_one(structure['container_selector'])
            if not container:
                return []
            
            items = container.select(structure['item_selector'])
            
            for item in items:
                notice = {}
                
                # 제목 추출
                title_elem = item.select_one(structure['title_selector'])
                if title_elem:
                    notice['notice_title'] = clean_text(title_elem.get_text())
                    
                    # 링크 추출
                    link_elem = title_elem.find('a') or item.select_one('a')
                    if link_elem and link_elem.get('href'):
                        notice['notice_link'] = urljoin(base_url, link_elem['href'])
                
                # 날짜 추출
                date_elem = item.select_one(structure['date_selector'])
                if date_elem:
                    date_text = clean_text(date_elem.get_text())
                    notice['notice_date'] = parse_date(date_text)
                
                # 유효성 검사
                if self._is_valid_notice(notice):
                    notices.append(notice)
            
            return self._validate_notices(notices)
            
        except Exception as e:
            self.logger.error(f"구조 기반 추출 중 오류: {str(e)}")
            return []
    
    def _extract_notice_from_element(self, element, template: Dict, base_url: str) -> Optional[Dict]:
        """개별 요소에서 공지사항 정보 추출"""
        try:
            notice = {}
            
            # 제목 추출
            title_elem = element.select_one(template['title_selector'])
            if title_elem:
                notice['notice_title'] = clean_text(title_elem.get_text())
            
            # 날짜 추출
            date_elem = element.select_one(template['date_selector'])
            if date_elem:
                date_text = clean_text(date_elem.get_text())
                notice['notice_date'] = parse_date(date_text)
            
            # 링크 추출
            link_elem = element.select_one(template['link_selector'])
            if link_elem and link_elem.get('href'):
                notice['notice_link'] = urljoin(base_url, link_elem['href'])
            
            return notice if self._is_valid_notice(notice) else None
            
        except Exception as e:
            self.logger.debug(f"요소 추출 중 오류: {str(e)}")
            return None
    
    def _try_custom_selectors(self, soup: BeautifulSoup, url: str, univ_name: str) -> List[Dict]:
        """수동 설정된 선택자로 크롤링 시도"""
        # 일반적인 패턴들을 시도
        common_patterns = [
            {
                'list': 'tbody tr',
                'title': 'td:nth-child(2) a, td:nth-child(3) a',
                'date': 'td:last-child, td:nth-last-child(2)',
                'link': 'a'
            },
            {
                'list': 'ul.board-list li, .notice-list li',
                'title': '.title, .subject',
                'date': '.date, .regdate',
                'link': 'a'
            },
            {
                'list': '.board-item, .notice-item',
                'title': '.title a, .subject a',
                'date': '.date, .time',
                'link': 'a'
            }
        ]
        
        for pattern in common_patterns:
            try:
                notices = self._extract_with_pattern(soup, pattern, url)
                if len(notices) >= self.config['detection']['min_notices']:
                    return notices
            except:
                continue
        
        return []
    
    def _extract_with_pattern(self, soup: BeautifulSoup, pattern: Dict, base_url: str) -> List[Dict]:
        """패턴을 사용한 추출"""
        notices = []
        items = soup.select(pattern['list'])
        
        for item in items:
            notice = {}
            
            # 제목
            title_elem = item.select_one(pattern['title'])
            if title_elem:
                notice['notice_title'] = clean_text(title_elem.get_text())
            
            # 날짜
            date_elem = item.select_one(pattern['date'])
            if date_elem:
                date_text = clean_text(date_elem.get_text())
                notice['notice_date'] = parse_date(date_text)
            
            # 링크
            link_elem = item.select_one(pattern['link'])
            if link_elem and link_elem.get('href'):
                notice['notice_link'] = urljoin(base_url, link_elem['href'])
            
            if self._is_valid_notice(notice):
                notices.append(notice)
        
        return notices
    
    def _try_selenium_fallback(self, url: str, univ_name: str) -> List[Dict]:
        """Selenium을 사용한 폴백 크롤링"""
        driver = None
        try:
            # Chrome 드라이버 설정
            options = Options()
            for option in self.config['selenium']['chrome_options']:
                options.add_argument(option)
            
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(self.config['selenium_timeout'])
            
            # 페이지 로드
            driver.get(url)
            time.sleep(2)  # 동적 콘텐츠 로드 대기
            
            # HTML 가져오기
            soup = BeautifulSoup(driver.page_source, 'lxml')
            
            # 일반적인 선택자로 시도
            for selector in self.config['fallback']['selenium_selectors']:
                try:
                    elements = soup.select(selector)
                    if len(elements) >= 3:  # 최소 3개 이상의 항목
                        # 패턴 감지 재시도
                        auto_result = self.pattern_detector.detect_notice_structure(soup)
                        if auto_result['confidence'] >= 0.5:  # 더 낮은 임계값
                            return self._extract_notices_from_structure(soup, auto_result['structure'], url)
                except:
                    continue
            
            return []
            
        except Exception as e:
            self.logger.error(f"Selenium 폴백 실패 {univ_name}: {str(e)}")
            return []
        finally:
            if driver:
                driver.quit()
    
    def _is_valid_notice(self, notice: Dict) -> bool:
        """공지사항 유효성 검사"""
        if not notice.get('notice_title'):
            return False
        
        title = notice['notice_title']
        if len(title) < self.config['detection']['min_title_length']:
            return False
        
        if len(title) > self.config['detection']['max_title_length']:
            return False
        
        return True
    
    def _validate_notices(self, notices: List[Dict]) -> List[Dict]:
        """공지사항 목록 검증 및 정제"""
        valid_notices = []
        
        for notice in notices:
            if self._is_valid_notice(notice):
                # 중복 제거 (제목 기준)
                if not any(n['notice_title'] == notice['notice_title'] for n in valid_notices):
                    valid_notices.append(notice)
        
        # 최대 개수 제한
        max_notices = self.config['validation']['max_notices_per_university']
        return valid_notices[:max_notices]
    
    def _create_result(self, success: bool, notices: List[Dict] = None, method: str = None, error: str = None) -> Dict:
        """결과 딕셔너리 생성"""
        return {
            'success': success,
            'notices': notices or [],
            'method': method,
            'error': error,
            'timestamp': datetime.now().isoformat()
        }
    
    def get_stats(self) -> Dict[str, int]:
        """크롤링 통계 반환"""
        return self.stats.copy()
