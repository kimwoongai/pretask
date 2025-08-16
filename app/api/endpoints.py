"""
API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from app.core.config import processing_mode, settings
from app.services.single_run_processor import SingleRunProcessor
from app.services.batch_processor import BatchProcessor
from app.services.full_processor import FullProcessor
from app.services.monitoring import metrics_collector, alert_manager
from app.services.safety_gates import safety_gate_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# 서비스 인스턴스
single_processor = SingleRunProcessor()
batch_processor = BatchProcessor()
full_processor = FullProcessor()


@router.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "Document Processing Pipeline API",
        "version": "1.0.0",
        "mode": processing_mode.get_mode_name(),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/config")
async def get_config():
    """현재 설정 조회"""
    return processing_mode.get_mode_config()


# 단건 점검 모드 엔드포인트
@router.post("/single-run/process/{case_id}")
async def process_single_case(case_id: str):
    """단일 케이스 처리"""
    if not processing_mode.is_single_run_mode():
        raise HTTPException(
            status_code=400, 
            detail="Not in single run mode"
        )
    
    try:
        result = await single_processor.process_single_case(case_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to process case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/single-run/next-case")
async def get_next_case():
    """다음 케이스 제안"""
    if not processing_mode.is_single_run_mode():
        raise HTTPException(
            status_code=400, 
            detail="Not in single run mode"
        )
    
    next_case = await single_processor.get_next_case_suggestion()
    if not next_case:
        return {"next_case_id": None, "message": "No more cases available"}
    
    return {"next_case_id": next_case}


@router.get("/single-run/stats")
async def get_single_run_stats():
    """단건 처리 통계"""
    return single_processor.get_processing_stats()


# 배치 개선 모드 엔드포인트
@router.post("/batch/start-improvement")
async def start_batch_improvement(
    sample_size: int = 200,
    stratification_criteria: Optional[Dict[str, Any]] = None
):
    """배치 개선 사이클 시작"""
    if not processing_mode.is_batch_mode():
        raise HTTPException(
            status_code=400, 
            detail="Not in batch mode"
        )
    
    try:
        result = await batch_processor.start_batch_improvement_cycle(
            sample_size, stratification_criteria
        )
        return result
    except Exception as e:
        logger.error(f"Failed to start batch improvement: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/batch/status/{job_id}")
async def get_batch_status(job_id: str):
    """배치 작업 상태 조회"""
    # 실제로는 데이터베이스에서 조회
    return {
        "job_id": job_id,
        "status": "in_progress",
        "current_step": "batch_evaluation",
        "progress": 65,
        "estimated_completion": "2024-01-15T18:30:00"
    }


# 전량 처리 모드 엔드포인트
@router.post("/full-processing/start")
async def start_full_processing(
    processing_options: Dict[str, Any],
    background_tasks: BackgroundTasks
):
    """전량 처리 시작 (수동 버튼)"""
    if processing_mode.is_single_run_mode() or processing_mode.is_batch_mode():
        raise HTTPException(
            status_code=400, 
            detail="Not in full processing mode"
        )
    
    try:
        result = await full_processor.start_full_processing(processing_options)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to start full processing: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full-processing/stop/{job_id}")
async def stop_full_processing(job_id: str):
    """전량 처리 중단"""
    try:
        result = await full_processor.stop_processing(job_id)
        return result
    except Exception as e:
        logger.error(f"Failed to stop processing {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full-processing/resume/{job_id}")
async def resume_full_processing(job_id: str):
    """전량 처리 재개"""
    try:
        result = await full_processor.resume_processing(job_id)
        return result
    except Exception as e:
        logger.error(f"Failed to resume processing {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/full-processing/status/{job_id}")
async def get_full_processing_status(job_id: str):
    """전량 처리 상태 조회"""
    try:
        result = await full_processor.get_processing_status(job_id)
        return result
    except Exception as e:
        logger.error(f"Failed to get processing status {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 안전 게이트 엔드포인트
@router.post("/safety-gates/run/{rules_version}")
async def run_safety_gates(rules_version: str):
    """안전 게이트 실행"""
    try:
        # 규칙 내용 가져오기 (실제로는 데이터베이스에서)
        rules_content = "{}"  # 실제 규칙 내용
        
        gate_results = await safety_gate_manager.run_all_gates(
            rules_version, rules_content
        )
        
        return {
            "rules_version": rules_version,
            "gates_passed": all(result.passed for result in gate_results),
            "results": [
                {
                    "gate_type": result.gate_type.value,
                    "passed": result.passed,
                    "score": result.score,
                    "details": result.details,
                    "error": result.error_message
                }
                for result in gate_results
            ]
        }
    except Exception as e:
        logger.error(f"Failed to run safety gates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# 모니터링 엔드포인트
@router.get("/monitoring/metrics")
async def get_current_metrics():
    """현재 메트릭 조회"""
    return metrics_collector.get_current_stats()


@router.get("/monitoring/metrics/{metric_type}")
async def get_historical_metrics(
    metric_type: str,
    hours: int = 24
):
    """과거 메트릭 조회"""
    if metric_type not in ["system", "processing", "quality", "cost"]:
        raise HTTPException(
            status_code=400, 
            detail="Invalid metric type"
        )
    
    return metrics_collector.get_historical_data(metric_type, hours)


@router.get("/monitoring/alerts")
async def get_recent_alerts(hours: int = 24):
    """최근 알림 조회"""
    return alert_manager.get_recent_alerts(hours)


@router.post("/monitoring/start")
async def start_monitoring():
    """모니터링 시작"""
    await metrics_collector.start_collecting()
    await alert_manager.start_monitoring()
    return {"message": "Monitoring started"}


@router.post("/monitoring/stop")
async def stop_monitoring():
    """모니터링 중지"""
    await metrics_collector.stop_collecting()
    await alert_manager.stop_monitoring()
    return {"message": "Monitoring stopped"}


# 규칙 관리 엔드포인트
@router.get("/rules/current")
async def get_current_rules():
    """현재 규칙 조회"""
    # 실제로는 데이터베이스에서 조회
    return {
        "version": "v1.0.0",
        "description": "Initial rules",
        "created_at": "2024-01-15T10:00:00",
        "rules_count": 5,
        "is_stable": True
    }


@router.get("/rules/versions")
async def get_rules_versions():
    """규칙 버전 목록 조회"""
    # 실제로는 데이터베이스에서 조회
    return [
        {
            "version": "v1.0.0",
            "description": "Initial rules",
            "created_at": "2024-01-15T10:00:00",
            "is_stable": True
        },
        {
            "version": "v1.0.1",
            "description": "Auto patch: page number improvement",
            "created_at": "2024-01-15T12:30:00",
            "is_stable": False
        }
    ]


# 케이스 관리 엔드포인트
@router.get("/cases")
async def get_cases(
    limit: int = 50,
    offset: int = 0,
    court_type: Optional[str] = None,
    case_type: Optional[str] = None,
    status: Optional[str] = None
):
    """케이스 목록 조회"""
    # 실제로는 데이터베이스에서 조회
    return {
        "cases": [
            {
                "case_id": f"case_{i:03d}",
                "court_type": "지방법원",
                "case_type": "민사",
                "year": 2023,
                "status": "pending",
                "created_at": "2024-01-15T09:00:00"
            }
            for i in range(offset, offset + limit)
        ],
        "total": 160000,
        "limit": limit,
        "offset": offset
    }


@router.get("/cases/{case_id}")
async def get_case_detail(case_id: str):
    """케이스 상세 조회"""
    # 실제로는 데이터베이스에서 조회
    return {
        "case_id": case_id,
        "court_type": "지방법원",
        "case_type": "민사",
        "year": 2023,
        "format_type": "pdf",
        "status": "pending",
        "original_content": "원본 문서 내용...",
        "processed_content": None,
        "processing_history": [],
        "created_at": "2024-01-15T09:00:00",
        "updated_at": "2024-01-15T09:00:00"
    }


@router.get("/cases/{case_id}/diff")
async def get_case_diff(case_id: str):
    """케이스 전후 비교"""
    # 실제로는 데이터베이스에서 조회하여 diff 생성
    return {
        "case_id": case_id,
        "before_content": "처리 전 내용...",
        "after_content": "처리 후 내용...",
        "diff_html": "<div>HTML diff 내용</div>",
        "summary": {
            "lines_removed": 15,
            "lines_added": 2,
            "characters_removed": 450,
            "characters_added": 20,
            "token_reduction_percent": 25.3
        }
    }
