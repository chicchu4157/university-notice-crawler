#!/usr/bin/env python3
"""
대학 공지사항 크롤러 메인 실행 파일
n8n 트리거로 시작되어 GitHub Actions에서 실행됩니다.
"""

import os
import json
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.crawler import SmartCrawler
from src.database import SupabaseManager
from src.utils import setup_logging, load_config

def main():
    """메인 실행 함수"""
    
    # 로깅 설정
    setup_logging()
    logger = logging.getLogger(__name__)
    
    try:
        # 환경변수 및 설정 로드
        config = load_config()
        
        # 환경변수에서 배치 설정 읽기
        batch_size = int(os.getenv('BATCH_SIZE', config.get('batch_size', 50)))
        start_index = int(os.getenv('START_INDEX', 0))
        
        logger.info(f"크롤링 시작 - 배치 크기: {batch_size}, 시작 인덱스: {start_index}")
        
        # 대학 목록 로드
        with open('data/university_list.json', 'r', encoding='utf-8') as f:
            universities = json.load(f)
        
        # 배치 처리할 대학 선택
        end_index = min(start_index + batch_size, len(universities))
        batch_universities = universities[start_index:end_index]
        
        logger.info(f"처리할 대학 수: {len(batch_universities)}")
        
        # 데이터베이스 매니저 초기화
        db_manager = SupabaseManager(
            url=os.getenv('SUPABASE_URL'),
            key=os.getenv('SUPABASE_KEY')
        )
        
        # 크롤러 초기화
        crawler = SmartCrawler(config)
        
        # 크롤링 실행
        results = run_crawling(crawler, batch_universities, db_manager)
        
        # 결과 리포트 생성
        generate_report(results, batch_universities)
        
        logger.info("크롤링 완료")
        
    except Exception as e:
        logger.error(f"크롤링 중 오류 발생: {str(e)}", exc_info=True)
        sys.exit(1)

def run_crawling(crawler: SmartCrawler, universities: List[Dict], db_manager: SupabaseManager) -> Dict[str, Any]:
    """크롤링 실행"""
    logger = logging.getLogger(__name__)
    
    results = {
        'total': len(universities),
        'success': 0,
        'failed': 0,
        'auto_detect': 0,
        'template': 0,
        'custom': 0,
        'failed_universities': [],
        'notices_count': 0
    }
    
    for i, university in enumerate(universities, 1):
        univ_name = university['name']
        univ_url = university['notice_url']
        
        logger.info(f"[{i}/{len(universities)}] {univ_name} 크롤링 시작")
        
        try:
            # 크롤링 실행
            crawl_result = crawler.crawl_university(univ_url, univ_name)
            
            if crawl_result['success']:
                notices = crawl_result['notices']
                method = crawl_result['method']
                
                # 데이터베이스에 저장
                if notices:
                    saved_count = db_manager.save_notices(notices, univ_name)
                    logger.info(f"{univ_name}: {saved_count}개 공지사항 저장 완료 (방법: {method})")
                    
                    results['notices_count'] += saved_count
                    results[method] += 1
                else:
                    logger.warning(f"{univ_name}: 공지사항을 찾을 수 없음")
                
                results['success'] += 1
                
            else:
                error_msg = crawl_result.get('error', '알 수 없는 오류')
                logger.error(f"{univ_name} 크롤링 실패: {error_msg}")
                results['failed'] += 1
                results['failed_universities'].append({
                    'name': univ_name,
                    'url': univ_url,
                    'error': error_msg
                })
                
        except Exception as e:
            logger.error(f"{univ_name} 크롤링 중 예외 발생: {str(e)}", exc_info=True)
            results['failed'] += 1
            results['failed_universities'].append({
                'name': univ_name,
                'url': univ_url,
                'error': str(e)
            })
    
    return results

def generate_report(results: Dict[str, Any], universities: List[Dict]):
    """크롤링 결과 리포트 생성"""
    logger = logging.getLogger(__name__)
    
    # 로그 디렉토리 생성
    log_dir = Path('logs')
    log_dir.mkdir(exist_ok=True)
    
    # 리포트 파일 생성
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    report_path = log_dir / f'crawl_report_{timestamp}.json'
    
    report = {
        'timestamp': datetime.now().isoformat(),
        'statistics': {
            '전체 대학 수': results['total'],
            '성공': results['success'],
            '실패': results['failed'],
            '성공률': f"{(results['success'] / results['total'] * 100):.1f}%" if results['total'] > 0 else "0%",
            '총 공지사항 수': results['notices_count']
        },
        'methods': {
            '자동 감지': results['auto_detect'],
            '템플릿 사용': results['template'],
            '수동 설정': results['custom']
        },
        'failed_universities': results['failed_universities']
    }
    
    # 리포트 저장
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # 콘솔에 요약 출력
    logger.info("=" * 50)
    logger.info("크롤링 결과 요약")
    logger.info("=" * 50)
    logger.info(f"전체: {results['total']}개 대학")
    logger.info(f"성공: {results['success']}개")
    logger.info(f"실패: {results['failed']}개")
    logger.info(f"성공률: {(results['success'] / results['total'] * 100):.1f}%")
    logger.info(f"총 공지사항: {results['notices_count']}개")
    logger.info("-" * 30)
    logger.info(f"자동 감지: {results['auto_detect']}개")
    logger.info(f"템플릿: {results['template']}개")
    logger.info(f"수동 설정: {results['custom']}개")
    
    if results['failed_universities']:
        logger.info("-" * 30)
        logger.info("실패한 대학:")
        for failed in results['failed_universities']:
            logger.info(f"  - {failed['name']}: {failed['error']}")
    
    logger.info(f"상세 리포트: {report_path}")

if __name__ == "__main__":
    main()
