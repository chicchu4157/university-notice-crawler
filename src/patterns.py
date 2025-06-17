"""
패턴 감지 모듈
웹페이지에서 공지사항 구조를 자동으로 감지하는 AI 기반 로직
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter, defaultdict
from bs4 import BeautifulSoup, Tag
from datetime import datetime
import difflib

class PatternDetector:
    """공지사항 패턴 자동 감지 클래스"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.date_patterns = [re.compile(pattern) for pattern in config['patterns']['date_patterns']]
        self.notice_keywords = config['patterns']['notice_keywords']
        
    def detect_notice_structure(self, soup: BeautifulSoup) -> Dict[str, Any]:
        """공지사항 구조 자동 감지"""
        try:
            # 1단계: 날짜 패턴이 있는 요소들 찾기
            date_elements = self._find_date_elements(soup)
            
            if len(date_elements) < self.config['detection']['min_notices']:
                return {'confidence': 0.0, 'structure': {}}
            
            # 2단계: 날짜 요소들의 공통 구조 분석
            common_structures = self._analyze_common_structure(date_elements)
            
            # 3단계: 가장 유력한 구조 선택
            best_structure = self._select_best_structure(common_structures, soup)
            
            # 4단계: 신뢰도 계산
            confidence = self._calculate_confidence(best_structure, soup)
            
            self.logger.debug(f"패턴 감지 완료 - 신뢰도: {confidence:.2f}")
            
            return {
                'confidence': confidence,
                'structure': best_structure
            }
            
        except Exception as e:
            self.logger.error(f"패턴 감지 중 오류: {str(e)}")
            return {'confidence': 0.0, 'structure': {}}
    
    def _find_date_elements(self, soup: BeautifulSoup) -> List[Tag]:
        """날짜 패턴이 포함된 요소들 찾기"""
        date_elements = []
        
        # 모든 텍스트에서 날짜 패턴 검색
        for pattern in self.date_patterns:
            text_nodes = soup.find_all(text=pattern)
            
            for text_node in text_nodes:
                parent = text_node.parent
                if parent and parent.name:
                    # 텍스트가 직접 포함된 요소나 그 부모 요소 중 적절한 것 선택
                    date_element = self._find_appropriate_container(parent)
                    if date_element and date_element not in date_elements:
                        date_elements.append(date_element)
        
        # 날짜 관련 클래스명/ID를 가진 요소들도 찾기
        date_selectors = [
            '[class*="date"]', '[class*="time"]', '[id*="date"]',
            '[class*="regist"]', '[class*="write"]', '[class*="post"]'
        ]
        
        for selector in date_selectors:
            elements = soup.select(selector)
            for elem in elements:
                if self._contains_date_pattern(elem.get_text()):
                    container = self._find_appropriate_container(elem)
                    if container and container not in date_elements:
                        date_elements.append(container)
        
        return date_elements
    
    def _find_appropriate_container(self, element: Tag) -> Optional[Tag]:
        """적절한 컨테이너 요소 찾기 (tr, li, div 등)"""
        current = element
        
        # 상위로 올라가면서 적절한 컨테이너 찾기
        for _ in range(5):  # 최대 5단계까지만
            if current.name in ['tr', 'li', 'article', 'section']:
                return current
            elif current.name == 'div' and self._is_item_container(current):
                return current
            
            current = current.parent
            if not current or not current.name:
                break
        
        return element if element.name in ['tr', 'li', 'div'] else None
    
    def _is_item_container(self, element: Tag) -> bool:
        """요소가 아이템 컨테이너인지 판단"""
        class_str = ' '.join(element.get('class', []))
        id_str = element.get('id', '')
        
        container_indicators = [
            'item', 'notice', 'board', 'list', 'row',
            'article', 'post', 'entry', 'content'
        ]
        
        text = (class_str + ' ' + id_str).lower()
        return any(indicator in text for indicator in container_indicators)
    
    def _contains_date_pattern(self, text: str) -> bool:
        """텍스트에 날짜 패턴이 포함되어 있는지 확인"""
        for pattern in self.date_patterns:
            if pattern.search(text):
                return True
        return False
    
    def _analyze_common_structure(self, date_elements: List[Tag]) -> List[Dict]:
        """날짜 요소들의 공통 구조 분석"""
        structures = []
        
        for element in date_elements:
            structure = self._analyze_element_structure(element)
            if structure:
                structures.append(structure)
        
        # 유사한 구조들을 그룹화
        grouped_structures = self._group_similar_structures(structures)
        
        return grouped_structures
    
    def _analyze_element_structure(self, element: Tag) -> Optional[Dict]:
        """개별 요소의 구조 분석"""
        try:
            structure = {
                'element': element,
                'tag_name': element.name,
                'classes': element.get('class', []),
                'parent_tag': element.parent.name if element.parent else None,
                'parent_classes': element.parent.get('class', []) if element.parent else [],
                'siblings_count': len(element.find_next_siblings(element.name)) + len(element.find_previous_siblings(element.name)),
                'has_link': bool(element.find('a')),
                'text_length': len(element.get_text(strip=True)),
                'children_tags': [child.name for child in element.find_all() if child.name],
                'position': self._get_element_position(element)
            }
            
            # 제목과 날짜 위치 분석
            structure.update(self._analyze_content_positions(element))
            
            return structure
            
        except Exception as e:
            self.logger.debug(f"요소 구조 분석 중 오류: {str(e)}")
            return None
    
    def _get_element_position(self, element: Tag) -> int:
        """요소의 형제 요소 중 위치 반환"""
        if not element.parent:
            return 0
        
        siblings = element.parent.find_all(element.name)
        try:
            return siblings.index(element)
        except ValueError:
            return 0
    
    def _analyze_content_positions(self, element: Tag) -> Dict:
        """요소 내 콘텐츠 위치 분석"""
        analysis = {
            'title_candidates': [],
            'date_candidates': [],
            'link_candidates': []
        }
        
        # 자식 요소들 분석
        children = element.find_all(['td', 'div', 'span', 'a', 'strong', 'em'])
        
        for i, child in enumerate(children):
            text = child.get_text(strip=True)
            
            # 날짜 후보
            if self._contains_date_pattern(text):
                analysis['date_candidates'].append({
                    'element': child,
                    'selector': self._generate_selector(child, element),
                    'position': i
                })
            
            # 링크 후보
            if child.name == 'a' or child.find('a'):
                analysis['link_candidates'].append({
                    'element': child,
                    'selector': self._generate_selector(child, element),
                    'position': i
                })
            
            # 제목 후보 (긴 텍스트)
            if len(text) > 10 and not self._contains_date_pattern(text):
                analysis['title_candidates'].append({
                    'element': child,
                    'selector': self._generate_selector(child, element),
                    'position': i,
                    'text_length': len(text)
                })
        
        return analysis
    
    def _generate_selector(self, element: Tag, container: Tag) -> str:
        """요소에 대한 CSS 선택자 생성"""
        path = []
        current = element
        
        while current and current != container:
            selector_part = current.name
            
            # 클래스가 있으면 추가
            if current.get('class'):
                classes = '.'.join(current['class'])
                selector_part += f'.{classes}'
            
            # nth-child 추가 (필요한 경우)
            siblings = current.parent.find_all(current.name) if current.parent else []
            if len(siblings) > 1:
                try:
                    index = siblings.index(current) + 1
                    selector_part += f':nth-child({index})'
                except ValueError:
                    pass
            
            path.insert(0, selector_part)
            current = current.parent
        
        return ' > '.join(path)
    
    def _group_similar_structures(self, structures: List[Dict]) -> List[Dict]:
        """유사한 구조들을 그룹화하고 대표 구조 선택"""
        if not structures:
            return []
        
        groups = []
        similarity_threshold = self.config['detection']['similarity_threshold']
        
        for structure in structures:
            # 기존 그룹과의 유사도 확인
            matched_group = None
            for group in groups:
                if self._calculate_structure_similarity(structure, group['representative']) >= similarity_threshold:
                    matched_group = group
                    break
            
            if matched_group:
                matched_group['members'].append(structure)
                # 그룹의 대표 구조 업데이트 (가장 형제가 많은 것)
                if structure['siblings_count'] > matched_group['representative']['siblings_count']:
                    matched_group['representative'] = structure
            else:
                groups.append({
                    'representative': structure,
                    'members': [structure],
                    'count': 1
                })
        
        # 멤버 수로 정렬 (많은 순)
        groups.sort(key=lambda g: len(g['members']), reverse=True)
        
        return [group['representative'] for group in groups]
    
    def _calculate_structure_similarity(self, struct1: Dict, struct2: Dict) -> float:
        """두 구조 간의 유사도 계산"""
        similarity_score = 0.0
        total_weight = 0.0
        
        # 태그명 비교
        if struct1['tag_name'] == struct2['tag_name']:
            similarity_score += 0.3
        total_weight += 0.3
        
        # 부모 태그 비교
        if struct1['parent_tag'] == struct2['parent_tag']:
            similarity_score += 0.2
        total_weight += 0.2
        
        # 클래스 유사도
        classes1 = set(struct1['classes'])
        classes2 = set(struct2['classes'])
        if classes1 or classes2:
            class_similarity = len(classes1 & classes2) / len(classes1 | classes2) if (classes1 | classes2) else 0
            similarity_score += class_similarity * 0.3
        total_weight += 0.3
        
        # 형제 요소 수 유사도
        siblings_diff = abs(struct1['siblings_count'] - struct2['siblings_count'])
        siblings_similarity = max(0, 1 - siblings_diff / 10)  # 차이가 10개 이상이면 0
        similarity_score += siblings_similarity * 0.2
        total_weight += 0.2
        
        return similarity_score / total_weight if total_weight > 0 else 0.0
    
    def _select_best_structure(self, structures: List[Dict], soup: BeautifulSoup) -> Dict:
        """가장 적합한 구조 선택"""
        if not structures:
            return {}
        
        best_structure = None
        best_score = 0.0
        
        for structure in structures:
            score = self._score_structure(structure, soup)
            if score > best_score:
                best_score = score
                best_structure = structure
        
        if best_structure:
            return self._build_final_structure(best_structure, soup)
        
        return {}
    
    def _score_structure(self, structure: Dict, soup: BeautifulSoup) -> float:
        """구조의 점수 계산"""
        score = 0.0
        
        # 형제 요소 수 (더 많을수록 좋음)
        siblings_score = min(structure['siblings_count'] / 20, 1.0)  # 최대 20개까지만 의미
        score += siblings_score * 0.4
        
        # 링크 유무
        if structure['has_link']:
            score += 0.3
        
        # 적절한 텍스트 길이
        text_length = structure['text_length']
        if 20 <= text_length <= 200:  # 적절한 길이
            score += 0.2
        elif text_length > 200:
            score += 0.1  # 너무 길면 감점
        
        # 공지사항 관련 키워드
        element_text = structure['element'].get_text().lower()
        keyword_count = sum(1 for keyword in self.notice_keywords if keyword in element_text)
        if keyword_count > 0:
            score += 0.1
        
        return score
    
    def _build_final_structure(self, structure: Dict, soup: BeautifulSoup) -> Dict:
        """최종 구조 정보 구성"""
        element = structure['element']
        
        # 컨테이너 찾기 (부모 요소 중 여러 개의 같은 형제를 가진 것)
        container = self._find_list_container(element)
        
        # 선택자 생성
        item_selector = self._generate_item_selector(element, container)
        container_selector = self._generate_container_selector(container)
        
        # 제목, 날짜, 링크 선택자 결정
        title_selector = self._determine_title_selector(structure)
        date_selector = self._determine_date_selector(structure)
        link_selector = self._determine_link_selector(structure)
        
        return {
            'container_selector': container_selector,
            'item_selector': item_selector,
            'title_selector': title_selector,
            'date_selector': date_selector,
            'link_selector': link_selector,
            'confidence_factors': {
                'siblings_count': structure['siblings_count'],
                'has_links': structure['has_link'],
                'structure_consistency': True
            }
        }
    
    def _find_list_container(self, element: Tag) -> Tag:
        """목록 컨테이너 찾기"""
        current = element.parent
        
        while current:
            # 같은 태그의 형제가 3개 이상인 부모 찾기
            siblings = current.find_all(element.name, recursive=False)
            if len(siblings) >= 3:
                return current
            
            current = current.parent
            if not current or current.name in ['body', 'html']:
                break
        
        return element.parent or element
    
    def _generate_container_selector(self, container: Tag) -> str:
        """컨테이너 선택자 생성"""
        selector_parts = []
        
        # 태그명
        selector_parts.append(container.name)
        
        # ID가 있으면 우선 사용
        if container.get('id'):
            return f"#{container['id']}"
        
        # 클래스가 있으면 사용
        if container.get('class'):
            classes = '.'.join(container['class'])
            selector_parts[0] += f'.{classes}'
        
        return selector_parts[0]
    
    def _generate_item_selector(self, element: Tag, container: Tag) -> str:
        """아이템 선택자 생성"""
        # 단순히 태그명으로 시작
        selector = element.name
        
        # 클래스가 있고 의미있어 보이면 추가
        if element.get('class'):
            classes = element['class']
            meaningful_classes = [cls for cls in classes if any(
                keyword in cls.lower() for keyword in ['item', 'row', 'notice', 'board', 'list']
            )]
            if meaningful_classes:
                selector += '.' + '.'.join(meaningful_classes)
        
        return selector
    
    def _determine_title_selector(self, structure: Dict) -> str:
        """제목 선택자 결정"""
        candidates = structure.get('title_candidates', [])
        
        if candidates:
            # 가장 긴 텍스트를 가진 요소 선택
            best_candidate = max(candidates, key=lambda c: c['text_length'])
            return best_candidate['selector']
        
        # 기본 선택자들 시도
        return 'a, .title, .subject, td:nth-child(2), td:nth-child(3)'
    
    def _determine_date_selector(self, structure: Dict) -> str:
        """날짜 선택자 결정"""
        candidates = structure.get('date_candidates', [])
        
        if candidates:
            return candidates[0]['selector']
        
        return '.date, .regdate, .time, td:last-child, td:nth-last-child(2)'
    
    def _determine_link_selector(self, structure: Dict) -> str:
        """링크 선택자 결정"""
        candidates = structure.get('link_candidates', [])
        
        if candidates:
            return candidates[0]['selector']
        
        return 'a'
    
    def _calculate_confidence(self, structure: Dict, soup: BeautifulSoup) -> float:
        """신뢰도 계산"""
        if not structure:
            return 0.0
        
        confidence = 0.0
        
        try:
            # 구조가 실제로 작동하는지 테스트
            container = soup.select_one(structure['container_selector'])
            if not container:
                return 0.0
            
            items = container.select(structure['item_selector'])
            if len(items) < self.config['detection']['min_notices']:
                return 0.3  # 최소한의 신뢰도만
            
            # 아이템 수에 따른 신뢰도
            item_count_score = min(len(items) / 10, 1.0)  # 최대 10개까지만 의미
            confidence += item_count_score * 0.4
            
            # 제목 추출 성공률
            title_success = 0
            for item in items[:5]:  # 상위 5개만 테스트
                title_elem = item.select_one(structure['title_selector'])
                if title_elem and len(title_elem.get_text(strip=True)) > 5:
                    title_success += 1
            
            if items:
                title_success_rate = title_success / min(len(items), 5)
                confidence += title_success_rate * 0.4
            
            # 날짜 추출 성공률
            date_success = 0
            for item in items[:5]:
                date_elem = item.select_one(structure['date_selector'])
                if date_elem and self._contains_date_pattern(date_elem.get_text()):
                    date_success += 1
            
            if items:
                date_success_rate = date_success / min(len(items), 5)
                confidence += date_success_rate * 0.2
            
            return min(confidence, 1.0)
            
        except Exception as e:
            self.logger.debug(f"신뢰도 계산 중 오류: {str(e)}")
            return 0.0
