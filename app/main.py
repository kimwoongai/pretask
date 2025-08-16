"""
FastAPI 애플리케이션 메인 파일
"""
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn
from pathlib import Path

from app.core.config import settings
from app.core.database import db_manager
from app.core.logging import setup_logging
from app.api.endpoints import router
from app.services.monitoring import metrics_collector, alert_manager

# 로깅 설정
logger = setup_logging()

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Document Processing Pipeline",
    description="법률 문서 전처리 파이프라인 API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# 정적 파일 및 템플릿 설정
app.mount("/static", StaticFiles(directory="app/ui/static"), name="static")
templates = Jinja2Templates(directory="app/ui/templates")

# API 라우터 등록
app.include_router(router, prefix="/api")


@app.on_event("startup")
async def startup_event():
    """애플리케이션 시작 이벤트"""
    logger.info("Starting Document Processing Pipeline")
    
    # 환경 변수 확인
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"MongoDB URL set: {'Yes' if settings.mongodb_url else 'No'}")
    logger.info(f"MongoDB DB: {settings.mongodb_db}")
    logger.info(f"Redis URL set: {'Yes' if settings.redis_url else 'No'}")
    
    try:
        # 데이터베이스 연결
        await db_manager.connect()
        logger.info("Database connection attempt completed")
        
        # 모니터링 시작
        await metrics_collector.start_collecting()
        await alert_manager.start_monitoring()
        logger.info("Monitoring started successfully")
        
        logger.info("Application startup completed")
        
        # DSL 규칙 시스템 자동 초기화 (MongoDB)
        try:
            from app.services.dsl_rules import dsl_manager
            logger.info("🔧 DSL 규칙 시스템 MongoDB 초기화 중...")
            
            # DSL 매니저는 자동으로 MongoDB에서 로드하거나 기본 규칙 생성
            performance_report = dsl_manager.get_performance_report()
            logger.info(f"✅ DSL 규칙 시스템 MongoDB 준비 완료: {performance_report['total_rules']}개 규칙")
                
        except Exception as e:
            logger.error(f"❌ DSL 규칙 시스템 초기화 실패: {e}")
            logger.warning("⚠️ 기본 전처리 시스템으로 계속 진행...")
        
    except Exception as e:
        logger.error(f"Failed to start application: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """애플리케이션 종료 이벤트"""
    logger.info("Shutting down Document Processing Pipeline")
    
    try:
        # 모니터링 중지
        await metrics_collector.stop_collecting()
        await alert_manager.stop_monitoring()
        
        # 데이터베이스 연결 해제
        await db_manager.disconnect()
        
        logger.info("Application shutdown completed")
        
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# 웹 UI 라우트
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/single-run", response_class=HTMLResponse)
async def single_run_page(request: Request):
    """단건 점검 페이지"""
    return templates.TemplateResponse("single_run.html", {"request": request})


@app.get("/batch", response_class=HTMLResponse)
async def batch_page(request: Request):
    """배치 개선 페이지"""
    return templates.TemplateResponse("batch.html", {"request": request})


@app.get("/full-processing", response_class=HTMLResponse)
async def full_processing_page(request: Request):
    """전량 처리 페이지"""
    return templates.TemplateResponse("full_processing.html", {"request": request})


@app.get("/monitoring", response_class=HTMLResponse)
async def monitoring_page(request: Request):
    """모니터링 페이지"""
    return templates.TemplateResponse("monitoring.html", {"request": request})


if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development"
    )
