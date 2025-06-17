# university-notice-crawler
대학교 입학처 공지사항 자동 수집기


# 대학 공지사항 크롤러 - GitHub Actions 프로젝트

## 📁 프로젝트 구조

```
university-notice-crawler/
├── .github/
│   └── workflows/
│       └── crawl.yml                 # GitHub Actions 워크플로우
├── src/
│   ├── __init__.py
│   ├── crawler.py                    # 스마트 크롤러 메인 로직
│   ├── database.py                   # Supabase 연결 및 데이터 저장
│   ├── patterns.py                   # 패턴 감지 및 구조 분석
│   ├── templates.py                  # 템플릿 관리
│   └── utils.py                      # 유틸리티 함수
├── data/
│   ├── university_list.json          # 대학 목록 및 URL
│   └── templates.json               # 템플릿 그룹 정의
├── config.json                      # 설정 파일
├── main.py                         # 메인 실행 파일
├── requirements.txt                # Python 의존성
└── README.md                      # 프로젝트 문서
```

## 🔧 GitHub Secrets 설정 (Required)

GitHub 저장소의 Settings > Secrets and variables > Actions에서 설정:

- `SUPABASE_URL`: Supabase 프로젝트 URL
- `SUPABASE_KEY`: Supabase 서비스 키
- `N8N_WEBHOOK_SECRET`: n8n 웹훅 인증용 시크릿

## 🚀 사용 방법

1. **n8n에서 트리거**: Repository dispatch 이벤트 전송
2. **GitHub Actions 자동 실행**: 크롤링 시작
3. **결과 저장**: Supabase에 자동 저장
4. **로그 확인**: GitHub Actions 탭에서 실행 결과 확인

## 📊 데이터베이스 스키마 (Supabase)

```sql
-- university_notices 테이블
CREATE TABLE university_notices (
    id BIGSERIAL PRIMARY KEY,
    university_name VARCHAR(100) NOT NULL,
    notice_date DATE,
    notice_title TEXT NOT NULL,
    notice_link TEXT,
    crawled_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 인덱스 생성
CREATE INDEX idx_university_date ON university_notices(university_name, notice_date);
CREATE INDEX idx_crawled_at ON university_notices(crawled_at);
```

## 🔄 워크플로우

1. **자동 패턴 감지** (80% 커버리지 목표)
2. **템플릿 기반 크롤링** (15% 커버리지)
3. **수동 설정 처리** (5% 예외 케이스)
4. **결과 검증 및 저장**

## 📈 모니터링

- 각 대학별 성공/실패 로그
- 크롤링 방식별 통계
- 실행 시간 및 성능 메트릭
