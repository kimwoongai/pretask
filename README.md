# 문서 처리 파이프라인 (Document Processing Pipeline)

법률 문서 전처리를 위한 3단계 프로세스 시스템입니다.

## 시스템 개요

이 시스템은 다음 3단계 흐름으로 문서 처리를 수행합니다:

1. **단건 점검 모드 (Shakedown)**: 케이스 1건 기준으로 파이프라인 안정성 검증
2. **Batch API 반복 개선**: 대량 샘플로 규칙 자동 반복 개선 및 DSL 안정화  
3. **전량 처리 (16만건)**: 수동 버튼으로만 시작되는 전체 데이터 처리

## 주요 기능

### 🔍 단건 점검 모드
- 케이스별 전처리 → GPT-5 평가 → 자동 패치 → 재실행 순환
- 연속 20건 합격 시 Batch 모드로 승급
- 실시간 품질 지표 모니터링 (NRR, FPR, SS, 토큰절감)

### 🔄 Batch API 반복 개선
- 층화 샘플링 (200 → 1,000 → 5,000건 순으로 확대)
- 실패 클러스터링 및 자동 패치 제안
- 안전 게이트 통과 후에만 규칙 적용
- 오실레이션 방지 및 자동 롤백

### 🗄️ 전량 처리
- 16만건 전체 데이터 처리
- 1% 드라이런으로 성능 검증
- 실시간 진행률 모니터링
- 중단/재개 기능

### 🛡️ 안전 장치
- 유닛/회귀/홀드아웃 테스트 게이트
- 화이트리스트 DSL만 허용
- 자동 롤백 및 오실레이션 방지
- 로그 및 감사 추적

## 기술 스택

- **Backend**: FastAPI, Python 3.8+
- **Database**: MongoDB, Redis
- **AI**: OpenAI GPT-4 Turbo, Batch API
- **Frontend**: Bootstrap 5, Chart.js
- **Monitoring**: 실시간 메트릭 수집 및 알림

## 설치 및 실행

### 🌐 Render 배포 (권장)

1. GitHub 리포지토리에 코드 업로드
2. Render에서 Blueprint로 배포
3. `OPENAI_API_KEY` 환경 변수 설정
4. 자동 배포 완료!

자세한 내용은 [RENDER_DEPLOYMENT.md](RENDER_DEPLOYMENT.md) 참조

### 💻 로컬 개발 환경

```bash
# 프로젝트 클론
git clone <repository-url>
cd pretask

# Python 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

### 2. 환경 변수 설정

```bash
# 환경 설정 파일 복사
cp config.env.example .env

# .env 파일 편집
# - OPENAI_API_KEY: OpenAI API 키 설정
# - MONGODB_URL: MongoDB 연결 URL
# - REDIS_URL: Redis 연결 URL
```

### 3. 데이터베이스 설정

```bash
# MongoDB 시작 (로컬 설치 또는 Docker)
mongod

# Redis 시작 (로컬 설치 또는 Docker)  
redis-server
```

### 4. 애플리케이션 실행

```bash
# 개발 서버 시작
python -m app.main

# 또는 uvicorn 직접 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 5. 웹 인터페이스 접속

브라우저에서 http://localhost:8000 접속

## 사용 방법

### 단건 점검 모드

1. **단건 점검** 탭에서 케이스 선택
2. **처리 시작** 버튼 클릭
3. 품질 지표 확인 및 규칙 제안 검토
4. 필요 시 규칙 적용 후 재실행
5. 연속 20건 합격 달성 시 배치 모드로 승급

### 배치 개선 모드

1. **배치 개선** 탭에서 샘플 크기 설정
2. **개선 사이클 시작** 버튼 클릭
3. 자동 실행되는 단계들 모니터링:
   - 샘플 선정 → 전처리 → Batch 평가 → 클러스터링 → 자동 패치 → 게이트 검사 → 재검증
4. 규칙 안정화까지 반복

### 전량 처리 모드

1. **전량 처리** 탭에서 전환 조건 확인
2. 1% 드라이런 실행 (선택사항)
3. 처리 옵션 설정 (배치 크기, 동시성 등)
4. **전량 처리 시작** 버튼 클릭 (수동)
5. 진행률 모니터링 및 필요 시 중단/재개

## 모니터링

### 대시보드
- 시스템 상태 (CPU, 메모리, DB 연결)
- 처리 통계 (성공률, 처리 시간, 비용)
- 품질 지표 트렌드
- 최근 처리 결과

### 알림
- 높은 리소스 사용률
- 낮은 성공률
- 품질 지표 저하
- 시스템 오류

## API 문서

애플리케이션 실행 후 다음 URL에서 API 문서 확인:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 API 엔드포인트

### 단건 처리
- `POST /api/single-run/process/{case_id}` - 케이스 처리
- `GET /api/single-run/next-case` - 다음 케이스 제안
- `GET /api/single-run/stats` - 처리 통계

### 배치 처리  
- `POST /api/batch/start-improvement` - 배치 개선 시작
- `GET /api/batch/status/{job_id}` - 배치 상태 조회

### 전량 처리
- `POST /api/full-processing/start` - 전량 처리 시작
- `POST /api/full-processing/stop/{job_id}` - 처리 중단
- `GET /api/full-processing/status/{job_id}` - 처리 상태

### 모니터링
- `GET /api/monitoring/metrics` - 현재 메트릭
- `GET /api/monitoring/alerts` - 최근 알림

## 설정

### 환경 변수

| 변수명 | 설명 | 기본값 |
|--------|------|--------|
| `SINGLE_RUN_MODE` | 단건 모드 활성화 | `true` |
| `AUTO_PATCH` | 자동 패치 허용 | `true` |
| `USE_BATCH_API` | Batch API 사용 | `false` |
| `MIN_NRR` | 최소 NRR 임계값 | `0.92` |
| `MIN_FPR` | 최소 FPR 임계값 | `0.985` |
| `MIN_SS` | 최소 SS 임계값 | `0.90` |
| `MIN_TOKEN_REDUCTION` | 최소 토큰절감률 | `20` |

### 품질 게이트 설정

```python
# app/core/config.py에서 수정
quality_gates = {
    "min_nrr": 0.92,      # Noise Reduction Rate
    "min_fpr": 0.985,     # False Positive Rate  
    "min_ss": 0.90,       # Semantic Similarity
    "min_token_reduction": 20.0  # 토큰 절감률 (%)
}
```

## 개발

### 코드 구조

```
app/
├── core/           # 핵심 설정 및 데이터베이스
├── models/         # 데이터 모델
├── services/       # 비즈니스 로직
├── api/           # API 엔드포인트
└── ui/            # 웹 인터페이스
    ├── templates/ # HTML 템플릿
    └── static/    # CSS/JS 파일
```

### 테스트 실행

```bash
# 단위 테스트
pytest tests/

# 코드 포맷팅
black app/

# 린팅
flake8 app/
```

## 라이센스

MIT License

## 지원

문제가 발생하거나 기능 요청이 있으면 GitHub Issues를 통해 제보해 주세요.
