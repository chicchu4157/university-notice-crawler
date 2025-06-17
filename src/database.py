"""
Supabase 데이터베이스 관리 모듈
대학 공지사항 데이터 저장 및 관리
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, date
import json
from supabase import create_client, Client
from postgrest.exceptions import APIError

class SupabaseManager:
    """Supabase 데이터베이스 매니저"""
    
    def __init__(self, url: str, key: str, table_name: str = "university_notices"):
        self.logger = logging.getLogger(__name__)
        self.table_name = table_name
        
        try:
            self.client: Client = create_client(url, key)
            self.logger.info("Supabase 클라이언트 초기화 완료")
        except Exception as e:
            self.logger.error(f"Supabase 클라이언트 초기화 실패: {str(e)}")
            raise
    
    def save_notices(self, notices: List[Dict], university_name: str) -> int:
        """공지사항 목록을 데이터베이스에 저장"""
        if not notices:
            return 0
        
        saved_count = 0
        
        try:
            # 데이터 준비
            insert_data = []
            current_time = datetime.now().isoformat()
            
            for notice in notices:
                # 데이터 검증 및 정제
                processed_notice = self._prepare_notice_data(notice, university_name, current_time)
                if processed_notice:
                    insert_data.append(processed_notice)
            
            if not insert_data:
                self.logger.warning(f"{university_name}: 저장할 유효한 공지사항이 없음")
                return 0
            
            # 중복 확인 및 새로운 공지사항만 필터링
            new_notices = self._filter_new_notices(insert_data, university_name)
            
            if not new_notices:
                self.logger.info(f"{university_name}: 새로운 공지사항이 없음")
                return 0
            
            # 배치 저장
            saved_count = self._batch_insert(new_notices)
            
            if saved_count > 0:
                self.logger.info(f"{university_name}: {saved_count}개 공지사항 저장 완료")
            
            return saved_count
            
        except Exception as e:
            self.logger.error(f"{university_name} 공지사항 저장 중 오류: {str(e)}", exc_info=True)
            return 0
    
    def _prepare_notice_data(self, notice: Dict, university_name: str, crawled_at: str) -> Optional[Dict]:
        """공지사항 데이터 준비 및 검증"""
        try:
            # 필수 필드 확인
            if not notice.get('notice_title'):
                return None
            
            # 데이터 정제
            prepared_data = {
                'university_name': university_name,
                'notice_title': self._clean_title(notice['notice_title']),
                'notice_link': notice.get('notice_link'),
                'crawled_at': crawled_at
            }
            
            # 날짜 처리
            notice_date = notice.get('notice_date')
            if notice_date:
                if isinstance(notice_date, str):
                    prepared_data['notice_date'] = notice_date
                elif isinstance(notice_date, (date, datetime)):
                    prepared_data['notice_date'] = notice_date.isoformat()
            
            return prepared_data
            
        except Exception as e:
            self.logger.error(f"공지사항 데이터 준비 중 오류: {str(e)}")
            return None
    
    def _clean_title(self, title: str) -> str:
        """제목 정제"""
        if not title:
            return ""
        
        # 불필요한 공백 제거
        cleaned = ' '.join(title.split())
        
        # 최대 길이 제한
        max_length = 500
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length] + '...'
        
        return cleaned
    
    def _filter_new_notices(self, notices: List[Dict], university_name: str) -> List[Dict]:
        """중복되지 않은 새로운 공지사항만 필터링"""
        try:
            # 최근 크롤링된 공지사항 제목들 가져오기
            existing_response = (
                self.client
                .table(self.table_name)
                .select("notice_title")
                .eq("university_name", university_name)
                .order("crawled_at", desc=True)
                .limit(200)  # 최근 200개만 확인
                .execute()
            )
            
            existing_titles = {item['notice_title'] for item in existing_response.data}
            
            # 새로운 공지사항만 필터링
            new_notices = []
            for notice in notices:
                if notice['notice_title'] not in existing_titles:
                    new_notices.append(notice)
            
            return new_notices
            
        except Exception as e:
            self.logger.error(f"중복 확인 중 오류: {str(e)}")
            # 오류 발생 시 모든 공지사항을 새것으로 간주
            return notices
    
    def _batch_insert(self, notices: List[Dict]) -> int:
        """배치 단위로 데이터 삽입"""
        batch_size = 100
        total_saved = 0
        
        try:
            for i in range(0, len(notices), batch_size):
                batch = notices[i:i + batch_size]
                
                response = (
                    self.client
                    .table(self.table_name)
                    .insert(batch)
                    .execute()
                )
                
                if response.data:
                    batch_saved = len(response.data)
                    total_saved += batch_saved
                    self.logger.debug(f"배치 {i//batch_size + 1}: {batch_saved}개 저장")
                
            return total_saved
            
        except APIError as e:
            self.logger.error(f"Supabase API 오류: {str(e)}")
            return 0
        except Exception as e:
            self.logger.error(f"배치 삽입 중 오류: {str(e)}")
            return 0
    
    def get_university_stats(self, university_name: str) -> Dict[str, Any]:
        """특정 대학의 공지사항 통계 조회"""
        try:
            response = (
                self.client
                .table(self.table_name)
                .select("id", "notice_date", "crawled_at")
                .eq("university_name", university_name)
                .execute()
            )
            
            data = response.data
            total_count = len(data)
            
            if total_count == 0:
                return {
                    'university_name': university_name,
                    'total_notices': 0,
                    'latest_crawl': None,
                    'latest_notice_date': None
                }
            
            # 최신 크롤링 시간
            latest_crawl = max(item['crawled_at'] for item in data if item['crawled_at'])
            
            # 최신 공지사항 날짜
            latest_notice_date = None
            notice_dates = [item['notice_date'] for item in data if item['notice_date']]
            if notice_dates:
                latest_notice_date = max(notice_dates)
            
            return {
                'university_name': university_name,
                'total_notices': total_count,
                'latest_crawl': latest_crawl,
                'latest_notice_date': latest_notice_date
            }
            
        except Exception as e:
            self.logger.error(f"{university_name} 통계 조회 중 오류: {str(e)}")
            return {
                'university_name': university_name,
                'total_notices': 0,
                'latest_crawl': None,
                'latest_notice_date': None,
                'error': str(e)
            }
    
    def get_recent_notices(self, university_name: str = None, limit: int = 50) -> List[Dict]:
        """최근 공지사항 조회"""
        try:
            query = (
                self.client
                .table(self.table_name)
                .select("*")
            )
            
            if university_name:
                query = query.eq("university_name", university_name)
            
            response = (
                query
                .order("crawled_at", desc=True)
                .limit(limit)
                .execute()
            )
            
            return response.data
            
        except Exception as e:
            self.logger.error(f"최근 공지사항 조회 중 오류: {str(e)}")
            return []
    
    def delete_old_notices(self, days: int = 365) -> int:
        """오래된 공지사항 삭제"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            cutoff_str = cutoff_date.isoformat()
            
            response = (
                self.client
                .table(self.table_name)
                .delete()
                .lt("crawled_at", cutoff_str)
                .execute()
            )
            
            deleted_count = len(response.data) if response.data else 0
            self.logger.info(f"{days}일 이전 공지사항 {deleted_count}개 삭제")
            
            return deleted_count
            
        except Exception as e:
            self.logger.error(f"오래된 공지사항 삭제 중 오류: {str(e)}")
            return 0
    
    def health_check(self) -> bool:
        """데이터베이스 연결 상태 확인"""
        try:
            response = (
                self.client
                .table(self.table_name)
                .select("id")
                .limit(1)
                .execute()
            )
            
            self.logger.info("데이터베이스 연결 정상")
            return True
            
        except Exception as e:
            self.logger.error(f"데이터베이스 연결 실패: {str(e)}")
            return False
    
    def create_table_if_not_exists(self) -> bool:
        """테이블이 없으면 생성 (권한이 있는 경우)"""
        try:
            # Supabase에서는 보통 웹 인터페이스나 SQL 에디터로 테이블 생성
            # 여기서는 테이블 존재 여부만 확인
            response = (
                self.client
                .table(self.table_name)
                .select("id")
                .limit(1)
                .execute()
            )
            
            self.logger.info(f"테이블 '{self.table_name}' 존재 확인")
            return True
            
        except Exception as e:
            self.logger.error(f"테이블 확인 실패: {str(e)}")
            return False
