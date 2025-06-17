"""
유틸리티 함수 모듈
공통으로 사용되는 헬퍼 함수들
"""

import re
import logging
import json
import os
from typing import Any, Dict, Optional, Union
from datetime import datetime, date
from pathlib import Path
from urllib.parse import urlparse, urljoin
import logging.handlers

def setup_logging():
    """로깅 설정"""
    # 로그 디렉토리 생성
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 로그 포맷 설정
    log_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # 기존 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(log_format)
    root_logger.addHandler(console_handler)
    
    # 파일 핸들러 (로테이팅)
    file_handler = logging.handlers.RotatingFileHandler(
        'logs/crawler.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)
    
    # 에러 파일 핸들러
    error_handler = logging.handlers.RotatingFileHandler(
        'logs/error.log',
        maxBytes=5*1024*1024,  # 5MB
        backupCount=3,
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(log_format)
    root_logger.addHandler(error_handler)

def load_config(config_path: str = 'config.json') -> Dict[str, Any]:
    """설정 파일 로드"""
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # 환경변수로 설정 오버라이드
        config = override_config_with_env(config)
        
        return config
        
    except FileNotFoundError:
        raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
    except json.JSONDecodeError as e:
        raise ValueError(f"설정 파일 JSON 파싱 오류: {str(e)}")

def override_config_with_env(config: Dict[str, Any]) -> Dict[str, Any]:
    """환경변수로 설정 오버라이드"""
    # 환경변수 매핑
    env_mappings = {
        'CRAWLER_TIMEOUT': ['crawler', 'timeout'],
        'CRAWLER_RETRY_COUNT': ['crawler', 'retry_count'],
        'BATCH_SIZE': ['batch_size'],
        'SELENIUM_HEADLESS': ['selenium', 'headless'],
        'LOG_LEVEL': ['logging', 'level']
    }
    
    for env_var, config_path in env_mappings.items():
        env_value = os.getenv(env_var)
        if env_value is not None:
            # 타입 변환
            if env_var in ['CRAWLER_TIMEOUT', 'CRAWLER_RETRY_COUNT', 'BATCH_SIZE']:
                env_value = int(env_value)
            elif env_var == 'SELENIUM_HEADLESS':
                env_value = env_value.lower() in ['true', '1', 'yes']
            
            # 중첩된 딕셔너리에 값 설정
            current = config
            for key in config_path[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]
            current[config_path[-1]] = env_value
    
    return config

def clean_text(text: str) -> str:
    """텍스트 정제"""
    if not text:
        return ""
    
    # HTML 엔티티 처리
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    
    # 연속된 공백 제거
    text = re.sub(r'\s+', ' ', text)
    
    # 앞뒤 공백 제거
    text = text.strip()
    
    # 특수 문자 정제 (선택적)
    # text = re.sub(r'[^\w\s가-힣.,!?()[\]{}:;"\'-]', '', text)
    
    return text

def parse_date(date_string: str) -> Optional[str]:
    """날짜 문자열을 표준 형식으로 변환"""
    if not date_string:
        return None
    
    # 텍스트 정제
    date_string = clean_text(date_string)
    
    # 날짜 패턴 정의
    date_patterns = [
        # YYYY-MM-DD, YYYY.MM.DD, YYYY/MM/DD
        (r'(\d{4})[-./](\d{1,2})[-./](\d{1,2})', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        
        # YY-MM-DD, YY.MM.DD, YY/MM/DD (2000년대 가정)
        (r'(\d{2})[-./](\d{1,2})[-./](\d{1,2})', lambda m: f"20{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        
        # YYYY년 MM월 DD일
        (r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', lambda m: f"{m.group(1)}-{m.group(2).zfill(2)}-{m.group(3).zfill(2)}"),
        
        # MM-DD (현재 연도 가정)
        (r'^(\d{1,2})[-./](\d{1,2})$', lambda m: f"{datetime.now().year}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}"),
        
        # MM월 DD일 (현재 연도 가정)
        (r'(\d{1,2})월\s*(\d{1,2})일', lambda m: f"{datetime.now().year}-{m.group(1).zfill(2)}-{m.group(2).zfill(2)}")
    ]
    
    for pattern, formatter in date_patterns:
        match = re.search(pattern, date_string)
        if match:
            try:
                formatted_date = formatter(match)
                # 날짜 유효성 검사
                datetime.strptime(formatted_date, '%Y-%m-%d')
                return formatted_date
            except ValueError:
                continue
    
    # 패턴 매칭 실패 시 None 반환
    return None

def is_valid_url(url: str) -> bool:
    """URL 유효성 검사"""
    if not url or not isinstance(url, str):
        return False
    
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def normalize_url(url: str, base_url: str = None) -> str:
    """URL 정규화"""
    if not url:
        return ""
    
    # 절대 URL인 경우
    if url.startswith(('http://', 'https://')):
        return url
    
    # 상대 URL인 경우 base_url과 결합
    if base_url:
        return urljoin(base_url, url)
    
    return url

def extract_domain(url: str) -> str:
    """URL에서 도메인 추출"""
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""

def is_notice_relevant(title: str, keywords: list = None) -> bool:
    """공지사항 제목의 관련성 검사"""
    if not title:
        return False
    
    title_lower = title.lower()
    
    # 기본 키워드
    default_keywords = [
        '공지', '안내', '모집', '전형', '입학', '합격', '발표',
        '시험', '접수', '마감', '변경', '연기', '취소', '선발'
    ]
    
    keywords = keywords or default_keywords
    
    # 키워드 포함 여부 확인
    for keyword in keywords:
        if keyword in title_lower:
            return True
    
    # 제외할 키워드 확인
    exclude_keywords = ['광고', '홍보', '이벤트', '세미나', '특강']
    for exclude in exclude_keywords:
        if exclude in title_lower:
            return False
    
    return True

def validate_notice_data(notice: Dict[str, Any]) -> bool:
    """공지사항 데이터 유효성 검사"""
    # 필수 필드 확인
    if not notice.get('notice_title'):
        return False
    
    title = notice['notice_title']
    
    # 제목 길이 확인
    if len(title) < 5 or len(title) > 500:
        return False
    
    # 링크 유효성 확인 (있는 경우)
    link = notice.get('notice_link')
    if link and not is_valid_url(link):
        return False
    
    # 날짜 유효성 확인 (있는 경우)
    notice_date = notice.get('notice_date')
    if notice_date:
        try:
            if isinstance(notice_date, str):
                datetime.strptime(notice_date, '%Y-%m-%d')
            elif not isinstance(notice_date, (date, datetime)):
                return False
        except ValueError:
            return False
    
    return True

def calculate_similarity(text1: str, text2: str) -> float:
    """두 텍스트 간의 유사도 계산 (0.0 ~ 1.0)"""
    if not text1 or not text2:
        return 0.0
    
    # 간단한 단어 기반 유사도
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    if not words1 and not words2:
        return 1.0
    
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0

def sanitize_filename(filename: str) -> str:
    """파일명에서 특수문자 제거"""
    # 윈도우/리눅스에서 사용할 수 없는 문자 제거
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # 연속된 언더스코어 정리
    filename = re.sub(r'_+', '_', filename)
    
    # 앞뒤 공백 및 점 제거
    filename = filename.strip('. ')
    
    return filename

def get_file_size(file_path: str) -> int:
    """파일 크기 반환 (바이트)"""
    try:
        return Path(file_path).stat().st_size
    except Exception:
        return 0

def ensure_directory(directory: str):
    """디렉토리가 없으면 생성"""
    Path(directory).mkdir(parents=True, exist_ok=True)

def load_json_file(file_path: str, default: Any = None) -> Any:
    """JSON 파일 로드 (오류 시 기본값 반환)"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return default

def save_json_file(data: Any, file_path: str) -> bool:
    """JSON 파일 저장"""
    try:
        ensure_directory(str(Path(file_path).parent))
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def get_current_timestamp() -> str:
    """현재 타임스탬프 반환 (ISO 형식)"""
    return datetime.now().isoformat()

def format_duration(seconds: float) -> str:
    """초를 읽기 쉬운 형식으로 변환"""
    if seconds < 60:
        return f"{seconds:.1f}초"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}분"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}시간"

def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """텍스트 자르기"""
    if not text or len(text) <= max_length:
        return text
    
    return text[:max_length - len(suffix)] + suffix

def remove_duplicates(items: list, key_func=None) -> list:
    """리스트에서 중복 제거"""
    if not items:
        return []
    
    if key_func is None:
        return list(dict.fromkeys(items))
    
    seen = set()
    result = []
    
    for item in items:
        key = key_func(item)
        if key not in seen:
            seen.add(key)
            result.append(item)
    
    return result

def batch_process(items: list, batch_size: int):
    """리스트를 배치 단위로 나누기"""
    for i in range(0, len(items), batch_size):
        yield items[i:i + batch_size]

def retry_on_exception(max_retries: int = 3, delay: float = 1.0, exceptions: tuple = (Exception,)):
    """예외 발생 시 재시도 데코레이터"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        time.sleep(delay * (attempt + 1))  # 지수적 백오프
                        continue
                    break
            
            raise last_exception
        
        return wrapper
    return decorator

def deep_merge_dicts(dict1: dict, dict2: dict) -> dict:
    """딕셔너리 깊은 병합"""
    result = dict1.copy()
    
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge_dicts(result[key], value)
        else:
            result[key] = value
    
    return result

class Timer:
    """실행 시간 측정용 컨텍스트 매니저"""
    
    def __init__(self, name: str = None):
        self.name = name
        self.start_time = None
        self.end_time = None
    
    def __enter__(self):
        self.start_time = datetime.now()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end_time = datetime.now()
        duration = self.elapsed
        
        if self.name:
            print(f"{self.name}: {format_duration(duration)}")
    
    @property
    def elapsed(self) -> float:
        """경과 시간 (초)"""
        if self.start_time is None:
            return 0.0
        
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

def memory_usage() -> dict:
    """메모리 사용량 정보 반환"""
    try:
        import psutil
        process = psutil.Process()
        memory_info = process.memory_info()
        
        return {
            'rss': memory_info.rss,  # 물리 메모리
            'vms': memory_info.vms,  # 가상 메모리
            'percent': process.memory_percent(),  # 메모리 사용률
            'available': psutil.virtual_memory().available
        }
    except ImportError:
        return {'error': 'psutil not installed'}
    except Exception as e:
        return {'error': str(e)}
