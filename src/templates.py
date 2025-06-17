"""
템플릿 관리 모듈
대학 사이트의 공통 템플릿을 관리하고 매칭하는 기능
"""

import re
import json
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pathlib import Path

class TemplateManager:
    """템플릿 관리 클래스"""
    
    def __init__(self, templates_file: str = "data/templates.json"):
        self.logger = logging.getLogger(__name__)
        self.templates = {}
        self.domain_templates = {}
        self.system_templates = {}
        self.load_templates(templates_file)
    
    def load_templates(self, templates_file: str):
        """템플릿 파일 로드"""
        try:
            templates_path = Path(templates_file)
            if templates_path.exists():
                with open(templates_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                self.system_templates = data.get('systems', {})
                self.domain_templates = data.get('domains', {})
                self.templates = data.get('custom', {})
                
                self.logger.info(f"템플릿 로드 완료: 시스템 {len(self.system_templates)}개, 도메인 {len(self.domain_templates)}개")
            else:
                self.logger.warning(f"템플릿 파일이 없습니다: {templates_file}")
                self._create_default_templates()
                
        except Exception as e:
            self.logger.error(f"템플릿 로드 실패: {str(e)}")
            self._create_default_templates()
    
    def _create_default_templates(self):
        """기본 템플릿 생성"""
        self.system_templates = {
            "acapia": {
                "name": "아카피아 시스템",
                "indicators": [
                    "acapia.co.kr",
                    "class=\"board_list\"",
                    "id=\"board_list\""
                ],
                "selectors": {
                    "list_selector": "table.board_list tbody tr, .board_list tr",
                    "title_selector": "td.title a, td:nth-child(2) a",
                    "date_selector": "td.date, td:last-child",
                    "link_selector": "a"
                }
            },
            "jinhakapply": {
                "name": "진학어플라이 시스템",
                "indicators": [
                    "jinhakapply.com",
                    "class=\"bbs-list\"",
                    "jinhakapply"
                ],
                "selectors": {
                    "list_selector": "ul.bbs-list li, .notice-list li",
                    "title_selector": "a.tit, .title a",
                    "date_selector": "span.date, .regdate",
                    "link_selector": "a"
                }
            },
            "kiuri": {
                "name": "KIURI 시스템",
                "indicators": [
                    "kiuri.org",
                    "class=\"board\"",
                    "kiuri"
                ],
                "selectors": {
                    "list_selector": "table.board tbody tr",
                    "title_selector": "td.subject a",
                    "date_selector": "td.date",
                    "link_selector": "a"
                }
            },
            "campus": {
                "name": "캠퍼스 시스템",
                "indicators": [
                    "campus.ac.kr",
                    "campusXXX",
                    "class=\"bbsListTbl\""
                ],
                "selectors": {
                    "list_selector": "table.bbsListTbl tbody tr, .board-table tr",
                    "title_selector": "td.subject a, td:nth-child(2) a",
                    "date_selector": "td.date, td:last-child",
                    "link_selector": "a"
                }
            }
        }
        
        self.domain_templates = {
            "snu.ac.kr": {
                "name": "서울대학교",
                "selectors": {
                    "list_selector": "tbody tr",
                    "title_selector": "td:nth-child(2) a",
                    "date_selector": "td:last-child",
                    "link_selector": "a"
                }
            },
            "yonsei.ac.kr": {
                "name": "연세대학교",
                "selectors": {
                    "list_selector": ".board-list tr",
                    "title_selector": ".subject a",
                    "date_selector": ".date",
                    "link_selector": "a"
                }
            }
        }
    
    def match_template(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """URL과 HTML에서 매칭되는 템플릿 찾기"""
        try:
            # 1. 도메인 기반 매칭
            domain_match = self._match_by_domain(url)
            if domain_match:
                if self._validate_template(soup, domain_match['selectors']):
                    return {
                        'matched': True,
                        'template': domain_match['selectors'],
                        'template_name': domain_match['name'],
                        'match_type': 'domain'
                    }
            
            # 2. 시스템 기반 매칭
            system_match = self._match_by_system(soup, url)
            if system_match:
                if self._validate_template(soup, system_match['selectors']):
                    return {
                        'matched': True,
                        'template': system_match['selectors'],
                        'template_name': system_match['name'],
                        'match_type': 'system'
                    }
            
            # 3. 일반적인 패턴 매칭
            generic_match = self._match_generic_patterns(soup)
            if generic_match:
                return {
                    'matched': True,
                    'template': generic_match,
                    'template_name': 'generic',
                    'match_type': 'generic'
                }
            
            return {'matched': False}
            
        except Exception as e:
            self.logger.error(f"템플릿 매칭 중 오류: {str(e)}")
            return {'matched': False}
    
    def _match_by_domain(self, url: str) -> Optional[Dict]:
        """도메인으로 템플릿 매칭"""
        try:
            domain = urlparse(url).netloc.lower()
            
            # 정확한 도메인 매칭
            if domain in self.domain_templates:
                return self.domain_templates[domain]
            
            # 부분 도메인 매칭
            for template_domain, template in self.domain_templates.items():
                if template_domain in domain or domain.endswith(template_domain):
                    return template
            
            return None
            
        except Exception as e:
            self.logger.debug(f"도메인 매칭 중 오류: {str(e)}")
            return None
    
    def _match_by_system(self, soup: BeautifulSoup, url: str) -> Optional[Dict]:
        """시스템 지표로 템플릿 매칭"""
        html_content = str(soup).lower()
        url_lower = url.lower()
        
        for system_name, system_data in self.system_templates.items():
            indicators = system_data.get('indicators', [])
            match_count = 0
            
            for indicator in indicators:
                indicator_lower = indicator.lower()
                if indicator_lower in html_content or indicator_lower in url_lower:
                    match_count += 1
            
            # 지표의 절반 이상 매칭되면 해당 시스템으로 판단
            if match_count >= len(indicators) * 0.5:
                return system_data
        
        return None
    
    def _match_generic_patterns(self, soup: BeautifulSoup) -> Optional[Dict]:
        """일반적인 패턴으로 매칭"""
        generic_patterns = [
            # 테이블 기반 게시판
            {
                "list_selector": "table tbody tr, .board-table tr",
                "title_selector": "td:nth-child(2) a, td.title a, td.subject a",
                "date_selector": "td:last-child, td.date, td:nth-last-child(2)",
                "link_selector": "a"
            },
            # 목록 기반 게시판
            {
                "list_selector": "ul.board-list li, .notice-list li, .list-group-item",
                "title_selector": ".title a, .subject a, a",
                "date_selector": ".date, .regdate, .time",
                "link_selector": "a"
            },
            # div 기반 게시판
            {
                "list_selector": ".board-item, .notice-item, .item, .row",
                "title_selector": ".title a, .subject a, h3 a, h4 a",
                "date_selector": ".date, .regdate, .time, span:last-child",
                "link_selector": "a"
            }
        ]
        
        for pattern in generic_patterns:
            if self._validate_template(soup, pattern):
                return pattern
        
        return None
    
    def _validate_template(self, soup: BeautifulSoup, selectors: Dict) -> bool:
        """템플릿 선택자의 유효성 검증"""
        try:
            list_selector = selectors.get('list_selector', '')
            if not list_selector:
                return False
            
            # 목록 요소 찾기
            items = soup.select(list_selector)
            if len(items) < 3:  # 최소 3개 이상의 항목
                return False
            
            # 제목과 링크 확인
            title_selector = selectors.get('title_selector', '')
            link_selector = selectors.get('link_selector', 'a')
            
            valid_items = 0
            for item in items[:5]:  # 상위 5개만 확인
                # 제목 확인
                if title_selector:
                    title_elem = item.select_one(title_selector)
                    if title_elem and len(title_elem.get_text(strip=True)) > 5:
                        valid_items += 1
                        continue
                
                # 링크 확인
                link_elem = item.select_one(link_selector)
                if link_elem and link_elem.get('href'):
                    valid_items += 1
            
            # 절반 이상이 유효해야 함
            return valid_items >= len(items[:5]) * 0.5
            
        except Exception as e:
            self.logger.debug(f"템플릿 검증 중 오류: {str(e)}")
            return False
    
    def add_custom_template(self, university_name: str, selectors: Dict) -> bool:
        """커스텀 템플릿 추가"""
        try:
            self.templates[university_name] = {
                'name': university_name,
                'selectors': selectors,
                'created_at': str(datetime.now())
            }
            
            self.logger.info(f"커스텀 템플릿 추가: {university_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"커스텀 템플릿 추가 실패: {str(e)}")
            return False
    
    def save_templates(self, templates_file: str = "data/templates.json"):
        """템플릿을 파일에 저장"""
        try:
            templates_data = {
                'systems': self.system_templates,
                'domains': self.domain_templates,
                'custom': self.templates
            }
            
            templates_path = Path(templates_file)
            templates_path.parent.mkdir(exist_ok=True)
            
            with open(templates_path, 'w', encoding='utf-8') as f:
                json.dump(templates_data, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"템플릿 저장 완료: {templates_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"템플릿 저장 실패: {str(e)}")
            return False
    
    def get_template_stats(self) -> Dict[str, int]:
        """템플릿 통계 반환"""
        return {
            'system_templates': len(self.system_templates),
            'domain_templates': len(self.domain_templates),
            'custom_templates': len(self.templates),
            'total': len(self.system_templates) + len(self.domain_templates) + len(self.templates)
        }
    
    def suggest_template(self, soup: BeautifulSoup, url: str) -> Dict[str, Any]:
        """새로운 템플릿 제안"""
        try:
            # 일반적인 게시판 패턴 찾기
            suggestions = []
            
            # 테이블 기반 검사
            tables = soup.select('table')
            for table in tables:
                rows = table.select('tbody tr, tr')
                if len(rows) >= 5:
                    suggestion = self._analyze_table_structure(table, rows)
                    if suggestion:
                        suggestions.append(suggestion)
            
            # 목록 기반 검사
            lists = soup.select('ul, ol, .list, .board')
            for list_elem in lists:
                items = list_elem.select('li, .item, .row')
                if len(items) >= 5:
                    suggestion = self._analyze_list_structure(list_elem, items)
                    if suggestion:
                        suggestions.append(suggestion)
            
            if suggestions:
                # 가장 가능성 높은 제안 반환
                best_suggestion = max(suggestions, key=lambda s: s.get('confidence', 0))
                return {
                    'suggested': True,
                    'template': best_suggestion,
                    'confidence': best_suggestion.get('confidence', 0)
                }
            
            return {'suggested': False}
            
        except Exception as e:
            self.logger.error(f"템플릿 제안 중 오류: {str(e)}")
            return {'suggested': False}
    
    def _analyze_table_structure(self, table, rows) -> Optional[Dict]:
        """테이블 구조 분석"""
        try:
            # 첫 번째 행이 헤더인지 확인
            first_row = rows[0] if rows else None
            data_rows = rows[1:] if first_row and first_row.find('th') else rows
            
            if len(data_rows) < 3:
                return None
            
            # 칼럼 분석
            sample_row = data_rows[0]
            cells = sample_row.select('td')
            
            if len(cells) < 2:
                return None
            
            # 제목 칼럼 찾기 (보통 가장 긴 텍스트)
            title_col_idx = 0
            max_text_length = 0
            
            for i, cell in enumerate(cells):
                text_length = len(cell.get_text(strip=True))
                if text_length > max_text_length:
                    max_text_length = text_length
                    title_col_idx = i
            
            # 날짜 칼럼 찾기 (보통 마지막이나 날짜 패턴 포함)
            date_col_idx = len(cells) - 1  # 기본값: 마지막 칼럼
            
            return {
                'list_selector': self._generate_table_selector(table) + ' tbody tr',
                'title_selector': f'td:nth-child({title_col_idx + 1}) a, td:nth-child({title_col_idx + 1})',
                'date_selector': f'td:nth-child({date_col_idx + 1})',
                'link_selector': 'a',
                'confidence': 0.8,
                'type': 'table'
            }
            
        except Exception as e:
            self.logger.debug(f"테이블 구조 분석 중 오류: {str(e)}")
            return None
    
    def _analyze_list_structure(self, list_elem, items) -> Optional[Dict]:
        """목록 구조 분석"""
        try:
            sample_item = items[0]
            
            # 링크 찾기
            links = sample_item.select('a')
            if not links:
                return None
            
            return {
                'list_selector': self._generate_list_selector(list_elem) + ' li',
                'title_selector': 'a, .title, .subject',
                'date_selector': '.date, .regdate, .time, span:last-child',
                'link_selector': 'a',
                'confidence': 0.7,
                'type': 'list'
            }
            
        except Exception as e:
            self.logger.debug(f"목록 구조 분석 중 오류: {str(e)}")
            return None
    
    def _generate_table_selector(self, table) -> str:
        """테이블 선택자 생성"""
        if table.get('id'):
            return f"#{table['id']}"
        elif table.get('class'):
            classes = '.'.join(table['class'])
            return f"table.{classes}"
        else:
            return "table"
    
    def _generate_list_selector(self, list_elem) -> str:
        """목록 선택자 생성"""
        if list_elem.get('id'):
            return f"#{list_elem['id']}"
        elif list_elem.get('class'):
            classes = '.'.join(list_elem['class'])
            return f"{list_elem.name}.{classes}"
        else:
            return list_elem.name
