"""
대학 공지사항 크롤러 패키지
하이브리드 접근법을 사용한 지능형 크롤링 시스템
"""

__version__ = "1.0.0"
__author__ = "University Crawler Team"
__description__ = "지능형 대학 공지사항 크롤러"

from .crawler import SmartCrawler
from .database import SupabaseManager
from .patterns import PatternDetector
from .templates import TemplateManager
from .utils import (
    setup_logging,
    load_config,
    clean_text,
    parse_date,
    is_valid_url,
    Timer
)

__all__ = [
    'SmartCrawler',
    'SupabaseManager', 
    'PatternDetector',
    'TemplateManager',
    'setup_logging',
    'load_config',
    'clean_text',
    'parse_date',
    'is_valid_url',
    'Timer'
]
