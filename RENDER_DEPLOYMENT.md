# Render 배포 가이드

이 문서는 Document Processing Pipeline을 Render에 배포하는 방법을 설명합니다.

## 🚀 Render 배포 단계

### 1. GitHub 리포지토리 준비

```bash
# Git 초기화 (아직 안 했다면)
git init

# 파일 추가
git add .
git commit -m "Initial commit: Document Processing Pipeline"

# GitHub 리포지토리와 연결
git remote add origin https://github.com/YOUR_USERNAME/document-processing-pipeline.git
git push -u origin main
```

### 2. Render 서비스 생성

1. **Render 대시보드 접속**: https://render.com
2. **New +** 버튼 클릭
3. **Blueprint** 선택
4. GitHub 리포지토리 연결
5. `render.yaml` 파일이 자동으로 감지됨

### 3. 환경 변수 설정

Render 대시보드에서 다음 환경 변수들을 설정해야 합니다:

#### 필수 환경 변수
```
OPENAI_API_KEY=your_openai_api_key_here
```

#### 선택적 환경 변수 (기본값 사용 가능)
```
ENVIRONMENT=production
SINGLE_RUN_MODE=true
AUTO_PATCH=true
MIN_NRR=0.92
MIN_FPR=0.985
MIN_SS=0.90
MIN_TOKEN_REDUCTION=20
LOG_LEVEL=INFO
```

### 4. 데이터베이스 설정

`render.yaml`에 정의된 서비스들:

- **MongoDB**: PostgreSQL 서비스로 자동 생성
- **Redis**: Redis 서비스로 자동 생성
- **Web App**: 메인 애플리케이션

### 5. 배포 확인

배포가 완료되면 Render가 제공하는 URL로 접속:
```
https://your-app-name.onrender.com
```

## 📋 Render 설정 파일 구조

### render.yaml
```yaml
services:
  - type: web          # 웹 애플리케이션
  - type: pserv        # MongoDB (PostgreSQL 서비스)
  - type: redis        # Redis 캐시
```

### Dockerfile
- Python 3.11 베이스 이미지
- 의존성 설치 및 애플리케이션 복사
- 포트 8000 노출

## 🔧 환경별 설정

### 프로덕션 환경 특징
- `ENVIRONMENT=production`
- 자동 리로드 비활성화
- 로그 레벨: INFO
- 워커 수: 1 (Free tier 제한)

### 개발 환경과의 차이점
- MongoDB/Redis는 Render 관리형 서비스 사용
- 환경 변수로 연결 정보 자동 주입
- HTTPS 자동 적용

## 🚨 주의사항

### Free Tier 제한사항
- **Sleep Mode**: 15분 비활성화 시 앱 Sleep
- **빌드 시간**: 월 500시간 제한
- **대역폭**: 월 100GB 제한
- **데이터베이스**: 1GB 스토리지 제한

### 성능 최적화
```python
# 프로덕션에서는 워커 수 조정
workers = min(4, (os.cpu_count() or 1) * 2 + 1)
```

### 로그 관리
```python
# 로그 파일 위치
LOG_FILE=/opt/render/project/src/logs/app.log
```

## 🔍 배포 후 확인사항

### 1. 헬스체크
```bash
curl https://your-app.onrender.com/
```

### 2. API 문서 확인
```
https://your-app.onrender.com/docs
```

### 3. 데이터베이스 연결 확인
```
https://your-app.onrender.com/api/config
```

### 4. 모니터링 확인
```
https://your-app.onrender.com/monitoring
```

## 🛠️ 문제 해결

### 일반적인 문제들

#### 1. 빌드 실패
```bash
# 의존성 문제 확인
pip install -r requirements.txt
```

#### 2. 데이터베이스 연결 실패
- 환경 변수 `MONGODB_URL` 확인
- 네트워크 설정 확인

#### 3. OpenAI API 키 오류
- 환경 변수 `OPENAI_API_KEY` 설정 확인
- API 키 유효성 확인

#### 4. 메모리 부족
```yaml
# render.yaml에서 플랜 업그레이드
plan: starter  # 또는 standard
```

### 로그 확인 방법
```bash
# Render 대시보드에서 로그 확인
# 또는 API로 로그 조회
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.render.com/v1/services/YOUR_SERVICE_ID/logs
```

## 📊 모니터링 및 알림

### Render 대시보드
- CPU/메모리 사용률 모니터링
- 요청 수 및 응답 시간
- 에러율 추적

### 애플리케이션 모니터링
- `/monitoring` 페이지에서 실시간 메트릭 확인
- 알림 설정으로 이상 상황 감지

## 🔄 업데이트 및 배포

### 자동 배포
```bash
# main 브랜치에 푸시하면 자동 배포
git push origin main
```

### 수동 배포
1. Render 대시보드에서 **Manual Deploy** 클릭
2. 특정 커밋으로 롤백 가능

## 💰 비용 최적화

### Free Tier 활용
- 개발/테스트 환경으로 적합
- Sleep mode로 리소스 절약

### Paid Tier 고려사항
- 24/7 운영 필요 시
- 높은 트래픽 처리 시
- 더 많은 데이터베이스 용량 필요 시

## 📞 지원 및 문의

- **Render 문서**: https://render.com/docs
- **Render 커뮤니티**: https://community.render.com
- **GitHub Issues**: 프로젝트 이슈 트래커
