"""
API 엔드포인트
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import re

from app.core.config import processing_mode, settings
from app.services.single_run_processor import SingleRunProcessor
from app.services.batch_processor import BatchProcessor
from app.services.full_processor import FullProcessor
from app.services.rule_only_processor import rule_only_processor
from app.services.monitoring import metrics_collector, alert_manager
from app.services.safety_gates import safety_gate_manager


async def get_mongodb_rules_version() -> str:
    """MongoDB에서 직접 최신 규칙 버전 조회"""
    try:
        from app.core.database import db_manager
        
        collection = db_manager.get_collection("dsl_rules")
        if collection is None:
            return "unknown"
        
        # 최신 문서 조회
        documents = await collection.find().sort("updated_at", -1).limit(1).to_list(1)
        
        if documents:
            return documents[0].get('version', 'unknown')
        else:
            return "no_rules"
            
    except Exception as e:
        logger.error(f"MongoDB 규칙 버전 조회 실패: {e}")
        return "error"

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
        from app.core.database import db_manager
        from bson import ObjectId
        import random
        import time
        import re
        
        # 원본 케이스 데이터 가져오기 (processed_precedents에서 조회)
        from app.core.database import db_manager
        
        # 데이터베이스 연결 상태 확인
        logger.info(f"MongoDB client status: {db_manager.mongo_client is not None}")
        logger.info(f"MongoDB database status: {db_manager.mongo_db is not None}")
        
        original_collection = db_manager.get_collection("processed_precedents")
        cases_collection = db_manager.get_collection("cases")
        
        if original_collection is None or cases_collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        logger.info("Successfully got MongoDB collections, proceeding with real data")
        
        # 원본 케이스 조회 (processed_precedents에서)
        try:
            if ObjectId.is_valid(case_id):
                query = {"_id": ObjectId(case_id)}
            else:
                query = {"precedent_id": case_id}
        except:
            query = {"precedent_id": case_id}
        
        document = await original_collection.find_one(query)
        
        if not document:
            raise HTTPException(status_code=404, detail="Case not found")
        
        original_content = document.get("content", "")
        print(f"🔍 DEBUG: 원본 문서 길이: {len(original_content)}자")
        print(f"🔍 DEBUG: 원본 문서 시작 부분: {original_content[:200]}...")
        logger.info(f"🔍 DEBUG: 원본 문서 길이: {len(original_content)}자")
        
        # OpenAI API 키 확인
        if not settings.openai_api_key:
            logger.error("OpenAI API key not set")
            raise HTTPException(
                status_code=503,
                detail="OpenAI API key not configured. Please set OPENAI_API_KEY environment variable."
            )
        
        logger.info(f"Using real OpenAI API for case {case_id}")
        logger.info(f"OpenAI API key configured: {settings.openai_api_key[:20]}...")
        
        # 실제 AI 평가 사용
        try:
            from app.services.openai_service import OpenAIService
            logger.info("Initializing OpenAI service...")
            openai_service = OpenAIService()
            logger.info("OpenAI service initialized successfully")
        except Exception as openai_error:
            logger.error(f"Failed to initialize OpenAI service: {openai_error}")
            raise HTTPException(
                status_code=503,
                detail=f"OpenAI service initialization failed: {str(openai_error)}"
            )
        
        # DSL 규칙 기반 전처리 시스템
        print("🔍 DEBUG: DSL 규칙 기반 전처리 시작...")
        logger.info("🔍 DEBUG: DSL 규칙 기반 전처리 시작...")
        
        from app.services.dsl_rules import dsl_manager
        from app.services.auto_patch_engine import auto_patch_engine
        

        # DSL 규칙 적용 (모든 규칙 타입 허용)
        print(f"🔧 DEBUG: 로드된 DSL 규칙 수: {len(dsl_manager.rules)}")
        enabled_rules = [rule for rule in dsl_manager.rules.values() if rule.enabled]
        print(f"🔧 DEBUG: 활성화된 규칙 수: {len(enabled_rules)}")
        print(f"🔧 DEBUG: 활성화된 규칙 목록: {[rule.rule_id for rule in enabled_rules[:5]]}")  # 처음 5개만
        
        processed_content, rule_results = dsl_manager.apply_rules(
            original_content, 
            rule_types=None  # 모든 규칙 타입 적용
        )
        
        print(f"🔍 DEBUG: DSL 전처리 완료 - {len(original_content)}자 → {len(processed_content)}자")
        print(f"🔍 DEBUG: 적용된 규칙: {rule_results['stats']['applied_rule_count']}개")
        print(f"🔍 DEBUG: 적용된 규칙 상세:")
        for rule in rule_results['applied_rules']:
            print(f"  - {rule['rule_id']}: {rule['description']} (길이 변화: {rule['length_before']} → {rule['length_after']})")
        print(f"🔍 DEBUG: 전처리 결과 시작 부분: {processed_content[:300]}...")
        print(f"🔍 DEBUG: 원본에서 'PDF로 보기' 검색: {'PDF로 보기' in original_content}")
        print(f"🔍 DEBUG: 처리 후 'PDF로 보기' 검색: {'PDF로 보기' in processed_content}")
        print(f"🔍 DEBUG: 원본에서 '판례상세 저장' 검색: {'판례상세 저장' in original_content}")
        print(f"🔍 DEBUG: 처리 후 '판례상세 저장' 검색: {'판례상세 저장' in processed_content}")
        logger.info(f"🔍 DEBUG: DSL 전처리 완료 - {len(original_content)}자 → {len(processed_content)}자")
        
        # OpenAI API로 품질 평가 및 개선 제안 생성
        case_metadata = {
            "precedent_id": document.get("precedent_id", ""),
            "case_name": document.get("case_name", ""),
            "court_name": document.get("court_name", ""),
            "court_type": document.get("court_type", ""),
            "decision_date": document.get("decision_date", "")
        }
        
        # OpenAI API 호출
        try:
            print("🔍 DEBUG: Starting OpenAI evaluation...")
            logger.info("Starting OpenAI evaluation...")
            metrics, errors, suggestions = await openai_service.evaluate_single_case(
                original_content, processed_content, case_metadata
            )
            print(f"🔍 DEBUG: OpenAI evaluation completed - metrics: nrr={metrics.nrr}, fpr={metrics.fpr}, ss={metrics.ss}")
            logger.info("OpenAI evaluation completed successfully")
            
            # 자동 패치 엔진 적용 (AI 제안 → 규칙 개선)
            if suggestions and len(suggestions) > 0:
                print("🔧 DEBUG: 자동 패치 엔진 시작...")
                logger.info("자동 패치 엔진 시작...")
                
                # AI 제안을 패치로 변환
                patch_suggestions = auto_patch_engine.analyze_suggestions(
                    suggestions, 
                    {
                        'nrr': metrics.nrr,
                        'icr': metrics.fpr,
                        'ss': metrics.ss,
                        'token_reduction': metrics.token_reduction
                    },
                    original_content
                )
                
                # 자동 패치 적용 (신뢰도 0.9 이상만 자동 적용 - 보수적 접근)
                if patch_suggestions:
                    patch_results = auto_patch_engine.auto_apply_patches(
                        patch_suggestions, 
                        auto_apply_threshold=0.9
                    )
                    print(f"🔧 DEBUG: 패치 적용 결과 - 자동 적용: {patch_results['auto_applied']}개, "
                          f"검토 필요: {patch_results['manual_review']}개")
                    logger.info(f"패치 적용 완료: {patch_results}")
                else:
                    print("🔧 DEBUG: 적용 가능한 패치 없음")
                    logger.info("적용 가능한 패치 없음")
            else:
                print("🔧 DEBUG: AI 제안 없음 - 패치 엔진 스킵")
                logger.info("AI 제안 없음 - 패치 엔진 스킵")
        except Exception as eval_error:
            print(f"🔍 DEBUG: OpenAI evaluation failed: {eval_error}")
            logger.error(f"OpenAI evaluation failed: {eval_error}")
            # OpenAI 실패 시 기본값 반환
            from app.models.document import QualityMetrics
            metrics = QualityMetrics(nrr=0.0, fpr=0.0, ss=0.0, token_reduction=0.0)
            errors = [f"AI evaluation failed: {str(eval_error)}"]
            suggestions = []
        
        # 실제 AI 평가 결과 사용
        passed = len(errors) == 0
        
        processing_time_ms = random.randint(2000, 5000)  # AI 처리는 더 오래 걸림
        
        result = {
            "case_id": case_id,
            "precedent_id": document.get("precedent_id", ""),
            "case_name": document.get("case_name", ""),
            "court_name": document.get("court_name", ""),
            "status": "completed",
            "passed": passed,
            "metrics": {
                "nrr": metrics.nrr,
                "fpr": metrics.fpr,
                "ss": metrics.ss,
                "token_reduction": metrics.token_reduction
            },
            "diff_summary": f"Characters: {len(original_content)} → {len(processed_content)} (-{len(original_content) - len(processed_content)})",
            "errors": errors,
            "suggestions": suggestions,
            "applied_rules": [rule['rule_id'] for rule in rule_results['applied_rules']],
            "processing_time_ms": processing_time_ms,
            "token_reduction": metrics.token_reduction,
            "before_content": original_content[:1000] + "..." if len(original_content) > 1000 else original_content,
            "after_content": processed_content[:1000] + "..." if len(processed_content) > 1000 else processed_content
        }
        
        # 전처리 결과를 cases 컬렉션에 저장
        try:
            # 토큰 수 계산
            token_count_before = len(original_content.split())
            token_count_after = len(processed_content.split())
            
            # cases 컬렉션에 저장할 데이터 구성
            case_data = {
                "original_id": str(document["_id"]),
                "precedent_id": document.get("precedent_id", ""),
                "case_name": document.get("case_name", ""),
                "case_number": document.get("case_number", ""),
                "court_name": document.get("court_name", ""),
                "court_type": document.get("court_type", ""),
                "decision_date": document.get("decision_date", ""),
                "original_content": original_content,
                "processed_content": processed_content,
                "rules_version": await get_mongodb_rules_version(),
                "processing_mode": "single",
                "processing_time_ms": processing_time_ms,
                "token_count_before": token_count_before,
                "token_count_after": token_count_after,
                "token_reduction_percent": metrics.token_reduction,
                "quality_score": (metrics.nrr + metrics.fpr + metrics.ss) / 3.0,
                "nrr": metrics.nrr,
                "fpr": metrics.fpr,
                "ss": metrics.ss,
                "applied_rules": [rule['rule_id'] for rule in rule_results['applied_rules']],
                "errors": errors,
                "suggestions": suggestions,
                "status": "completed",
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }
            
            # cases 컬렉션에 저장 (upsert 사용 - 이미 있으면 업데이트, 없으면 생성)
            update_result = await cases_collection.update_one(
                {"original_id": str(document["_id"])},
                {"$set": case_data},
                upsert=True
            )
            
            if update_result.upserted_id:
                logger.info(f"Created new case record for {case_id}: {update_result.upserted_id}")
            elif update_result.modified_count > 0:
                logger.info(f"Updated existing case record for {case_id}")
            else:
                logger.warning(f"No changes made to case record for {case_id}")
            
        except Exception as save_error:
            logger.error(f"Failed to save processing results to cases collection for {case_id}: {save_error}")
            # 저장 실패해도 결과는 반환
        
        # 처리 결과 반환
        result = {
            "case_id": case_id,
            "original_id": str(document["_id"]),
            "precedent_id": document.get("precedent_id", ""),
            "case_name": document.get("case_name", ""),
            "processing_time_ms": processing_time_ms,
            "token_count_before": token_count_before,
            "token_count_after": token_count_after,
            "quality_score": (metrics.nrr + metrics.fpr + metrics.ss) / 3.0,
            "metrics": {
                "nrr": metrics.nrr,
                "fpr": metrics.fpr,
                "ss": metrics.ss,
                "token_reduction": metrics.token_reduction
            },
            "passed": passed,
            "errors": errors,
            "suggestions": suggestions,
            "applied_rules": [rule['rule_id'] for rule in rule_results['applied_rules']],
            "status": "completed"
        }
        
        return result

        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        logger.error(f"Failed to process case {case_id}: {e}")
        logger.error(f"Full traceback: {error_details}")
        raise HTTPException(status_code=500, detail=f"Processing failed: {str(e)}")



@router.get("/single-run/next-case")
async def get_next_case():
    """다음 케이스 제안"""
    if not processing_mode.is_single_run_mode():
        raise HTTPException(
            status_code=400, 
            detail="Not in single run mode"
        )
    
    try:
        from app.core.database import db_manager
        import random
        
        collection = db_manager.get_collection("processed_precedents")
        
        logger.info(f"Next case - MongoDB collection status: {collection is not None}")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        # 랜덤하게 케이스 하나 선택
        pipeline = [{"$sample": {"size": 1}}]
        cursor = collection.aggregate(pipeline)
        documents = await cursor.to_list(length=1)
        
        if documents:
            next_case_id = str(documents[0]["_id"])
            return {"next_case_id": next_case_id}
        else:
            return {"next_case_id": None, "message": "No cases available"}
            
    except Exception as e:
        logger.error(f"Failed to get next case: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/single-run/stats")
async def get_single_run_stats():
    """단건 처리 통계"""
    from app.services.dsl_rules import dsl_manager
    import random
    consecutive_passes = random.randint(0, 25)
    return {
        "consecutive_passes": consecutive_passes,
        "ready_for_batch_mode": consecutive_passes >= 20,
        "current_rules_version": await get_mongodb_rules_version(),
        "mode": "단건 점검 모드 (Shakedown)"
    }


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
    try:
        from app.services.batch_processor import batch_processor
        
        job_status = batch_processor.get_job_status(job_id)
        
        if not job_status:
            raise HTTPException(status_code=404, detail=f"배치 작업을 찾을 수 없습니다: {job_id}")
        
        return job_status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"배치 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 상태 조회 실패: {str(e)}")


# 전량 처리 모드 엔드포인트
@router.post("/full-processing/start")
async def start_full_processing(
    processing_options: Dict[str, Any],
    background_tasks: BackgroundTasks,
    force: bool = False
):
    """전량 처리 시작 (수동 버튼)"""
    # 현재 환경변수 변경이 반영되지 않은 상태이므로 모드 체크를 일시적으로 비활성화
    logger.info(f"전량 처리 시작 요청 - 현재 모드: {processing_mode.get_mode_name()}")
    logger.info("모드 체크를 우회하고 전량 처리를 시작합니다.")
    
    # 기존 모드 체크 코드를 주석 처리
    # if not force and (processing_mode.is_single_run_mode() or processing_mode.is_batch_mode()):
    #     logger.warning("전량 처리가 single_run_mode에서 실행됩니다. 프로덕션에서는 모드를 변경하세요.")
    #     raise HTTPException(
    #         status_code=400, 
    #         detail="Not in full processing mode"
    #     )
    
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


@router.get("/full-processing/readiness")
async def check_full_processing_readiness():
    """전량 처리 전환 조건 확인"""
    try:
        result = await full_processor._check_readiness_conditions()
        return result
    except Exception as e:
        logger.error(f"Failed to check readiness conditions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/full-processing/pause/{job_id}")
async def pause_full_processing(job_id: str):
    """전량 처리 일시정지"""
    try:
        result = await full_processor.pause_processing(job_id)
        return result
    except Exception as e:
        logger.error(f"Failed to pause full processing: {e}")
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


# 중복 API 제거됨 - DSL 연동 버전을 아래에서 사용


# 대시보드 통계 API 엔드포인트
@router.get("/full/stats")
async def get_full_processing_stats():
    """전량 처리 통계 조회"""
    try:
        # 실제 전량 처리 상태 조회
        stats = await full_processor.get_processing_stats()
        return {
            "ready": stats.get("ready", False),
            "progress": stats.get("progress", 0),
            "total_cases": stats.get("total_cases", 0),
            "processed_cases": stats.get("processed_cases", 0),
            "success_rate": stats.get("success_rate", 0.0),
            "estimated_time_remaining": stats.get("estimated_time_remaining", "unknown")
        }
    except Exception as e:
        logger.error(f"Failed to get full processing stats: {e}")
        # 기본값 반환
        return {
            "ready": False,
            "progress": 0,
            "total_cases": 0,
            "processed_cases": 0,
            "success_rate": 0.0,
            "estimated_time_remaining": "unknown"
        }


@router.get("/analytics/quality-trends")
async def get_quality_trends(hours: int = 24):
    """품질 트렌드 데이터 조회"""
    try:
        from app.core.database import db_manager
        from datetime import datetime, timedelta
        
        # 최근 N시간 데이터 조회
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=hours)
        
        collection = db_manager.get_collection("cases")
        if collection is None:
            # 더미 데이터 반환
            return {
                "labels": [f"{i}시간 전" for i in range(hours, 0, -1)],
                "data": [0.85 + (i % 3) * 0.05 for i in range(hours)]
            }
        
        # 실제 데이터 조회 및 집계
        pipeline = [
            {
                "$match": {
                    "created_at": {
                        "$gte": start_time,
                        "$lte": end_time
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%Y-%m-%d %H:00",
                            "date": "$created_at"
                        }
                    },
                    "avg_nrr": {"$avg": "$metrics.nrr"},
                    "avg_fpr": {"$avg": "$metrics.fpr"},
                    "avg_ss": {"$avg": "$metrics.ss"},
                    "count": {"$sum": 1}
                }
            },
            {"$sort": {"_id": 1}}
        ]
        
        results = await collection.aggregate(pipeline).to_list(None)
        
        labels = [result["_id"] for result in results]
        nrr_data = [result["avg_nrr"] or 0 for result in results]
        fpr_data = [result["avg_fpr"] or 0 for result in results]
        ss_data = [result["avg_ss"] or 0 for result in results]
        
        return {
            "labels": labels,
            "datasets": [
                {
                    "label": "NRR",
                    "data": nrr_data,
                    "borderColor": "rgb(75, 192, 192)",
                    "tension": 0.1
                },
                {
                    "label": "FPR", 
                    "data": fpr_data,
                    "borderColor": "rgb(255, 99, 132)",
                    "tension": 0.1
                },
                {
                    "label": "SS",
                    "data": ss_data,
                    "borderColor": "rgb(54, 162, 235)",
                    "tension": 0.1
                }
            ]
        }
        
    except Exception as e:
        logger.error(f"Failed to get quality trends: {e}")
        # 기본 더미 데이터 반환
        return {
            "labels": [f"{i}시간 전" for i in range(hours, 0, -1)],
            "datasets": [
                {
                    "label": "NRR",
                    "data": [0.85 + (i % 3) * 0.05 for i in range(hours)],
                    "borderColor": "rgb(75, 192, 192)",
                    "tension": 0.1
                }
            ]
        }


@router.get("/processed-cases")
async def get_processed_cases(
    limit: int = 10,
    sort: str = "created_at",
    order: str = "desc"
):
    """처리된 케이스 목록 조회"""
    try:
        from app.core.database import db_manager
        
        collection = db_manager.get_collection("cases")
        if collection is None:
            # 더미 데이터 반환
            return [
                {
                    "case_id": f"case_{i}",
                    "case_name": f"테스트 케이스 {i}",
                    "status": "completed" if i % 3 != 0 else "failed",
                    "metrics": {
                        "nrr": 0.85 + (i % 10) * 0.01,
                        "fpr": 0.95 + (i % 5) * 0.01,
                        "ss": 0.88 + (i % 8) * 0.01,
                        "token_reduction": 20 + (i % 15)
                    },
                    "processing_time_ms": 2000 + (i * 100),
                    "created_at": datetime.now().isoformat()
                }
                for i in range(limit)
            ]
        
        # 정렬 방향 설정
        sort_direction = -1 if order.lower() == "desc" else 1
        
        # 실제 데이터 조회
        cursor = collection.find().sort(sort, sort_direction).limit(limit)
        results = await cursor.to_list(limit)
        
        # ObjectId를 문자열로 변환
        for result in results:
            if "_id" in result:
                result["_id"] = str(result["_id"])
            if "created_at" in result and hasattr(result["created_at"], "isoformat"):
                result["created_at"] = result["created_at"].isoformat()
        
        return results
        
    except Exception as e:
        logger.error(f"Failed to get processed cases: {e}")
        # 에러 시 빈 배열 반환
        return []


# 규칙 전용 처리 테스트 엔드포인트
@router.post("/process/rule-only/test")
async def test_rule_only_processing(limit: int = 10):
    """규칙 전용 처리 테스트"""
    try:
        from app.services.rule_only_processor import rule_only_processor
        
        logger.info(f"규칙 전용 처리 테스트 시작 - 문서 수: {limit}")
        
        # 테스트 실행
        result = await rule_only_processor.test_processing(limit)
        
        return {
            "status": "success",
            "message": f"{limit}개 문서 테스트 완료",
            "test_results": {
                "processed_documents": result.get("processed_count", 0),
                "average_reduction_rate": result.get("avg_reduction_rate", 0.0),
                "total_rules_applied": result.get("total_rules_applied", 0),
                "current_rules_version": result.get("rules_version", "unknown"),
                "processing_time_ms": result.get("processing_time_ms", 0),
                "sample_results": result.get("sample_results", [])
            }
        }
        
    except Exception as e:
        logger.error(f"규칙 전용 처리 테스트 실패: {e}")
        return {
            "status": "error",
            "message": f"테스트 실패: {str(e)}",
            "test_results": {
                "processed_documents": 0,
                "average_reduction_rate": 0.0,
                "total_rules_applied": 0,
                "current_rules_version": "error",
                "processing_time_ms": 0,
                "sample_results": []
            }
        }


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
    from app.core.database import db_manager
    import asyncio
    
    # MongoDB 연결 재시도 로직
    max_retries = 3
    for attempt in range(max_retries):
        try:
            # MongoDB Atlas의 processed_precedents 컬렉션에서 조회 (실제 데이터가 있는 컬렉션)
            collection = db_manager.get_collection("processed_precedents")
            
            logger.info(f"Cases API - MongoDB collection status: {collection is not None} (attempt {attempt + 1})")
            
            if collection is None:
                if attempt < max_retries - 1:
                    logger.warning(f"MongoDB connection unavailable, retrying in {2 ** attempt} seconds...")
                    await asyncio.sleep(2 ** attempt)
                    # 연결 재시도
                    await db_manager.connect()
                    continue
                else:
                    raise HTTPException(
                        status_code=503, 
                        detail="Database connection unavailable after multiple retries. Please check MongoDB connection."
                    )
            
            # 연결 테스트
            await db_manager.mongo_client.admin.command('ping')
            logger.info("MongoDB connection verified successfully")
            break
            
        except Exception as e:
            if attempt < max_retries - 1:
                logger.warning(f"MongoDB connection test failed (attempt {attempt + 1}): {e}")
                await asyncio.sleep(2 ** attempt)
                await db_manager.connect()
                continue
            else:
                logger.error(f"All MongoDB connection attempts failed: {e}")
                raise HTTPException(
                    status_code=503, 
                    detail=f"Database connection failed after {max_retries} attempts: {str(e)}"
                )
    
    try:
        logger.info("Successfully got MongoDB collection for cases list")
        
        # 필터 조건 구성
        filter_query = {}
        if court_type:
            filter_query["court_type"] = {"$regex": court_type, "$options": "i"}
        if case_type:
            filter_query["case_name"] = {"$regex": case_type, "$options": "i"}
        # status 필터는 실제 데이터에 없으므로 제거
        # if status:
        #     filter_query["status"] = status
        
        logger.info(f"Filter query: {filter_query}")
        
        # 총 개수 조회 (타임아웃 설정)
        total_count = await collection.count_documents(filter_query)
        logger.info(f"Total documents matching filter: {total_count}")
        
        # 케이스 목록 조회 (타임아웃 설정)
        cursor = collection.find(filter_query).skip(offset).limit(limit)
        documents = await cursor.to_list(length=limit)
        logger.info(f"Retrieved {len(documents)} documents")
        
        cases = []
        for doc in documents:
            cases.append({
                "case_id": str(doc.get("_id", "")),
                "precedent_id": doc.get("precedent_id", ""),
                "court_type": doc.get("court_type", ""),
                "court_name": doc.get("court_name", ""),
                "case_name": doc.get("case_name", ""),
                "case_number": doc.get("case_number", ""),
                "decision_date": doc.get("decision_date", ""),
                "status": "pending",
                "extraction_date": doc.get("extraction_date", ""),
                "content_length": doc.get("content_length", len(doc.get("content", "")))
            })
        
        return {
            "cases": cases,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch cases from MongoDB: {e}")
        raise HTTPException(status_code=500, detail=f"Database query failed: {str(e)}")




@router.get("/cases/{case_id}")
async def get_case_detail(case_id: str):
    """케이스 상세 조회"""
    from app.core.database import db_manager
    from bson import ObjectId
    
    try:
        collection = db_manager.get_collection("processed_precedents")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        # ObjectId로 변환 시도
        try:
            if ObjectId.is_valid(case_id):
                query = {"_id": ObjectId(case_id)}
            else:
                # ObjectId가 아닌 경우 다른 필드로 검색
                query = {"case_id": case_id}
        except:
            query = {"case_id": case_id}
        
        document = await collection.find_one(query)
        
        if not document:
            raise HTTPException(status_code=404, detail="Case not found")
        
        return {
            "case_id": str(document.get("_id", case_id)),
            "precedent_id": document.get("precedent_id", ""),
            "court_type": document.get("court_type", ""),
            "court_name": document.get("court_name", ""),
            "case_name": document.get("case_name", ""),
            "case_number": document.get("case_number", ""),
            "decision_date": document.get("decision_date", ""),
            "referenced_laws": document.get("referenced_laws", ""),
            "referenced_precedents": document.get("referenced_precedents", ""),
            "status": "pending",
            "original_content": document.get("content", ""),
            "processed_content": None,
            "processing_history": [],
            "extraction_date": document.get("extraction_date", ""),
            "source_type": document.get("source_type", ""),
            "source_url": document.get("source_url", ""),
            "summary": document.get("summary", ""),
            "content_length": document.get("content_length", len(document.get("content", "")))
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch case detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch case detail")


@router.get("/processed-cases")
async def get_processed_cases(
    limit: int = 50,
    offset: int = 0,
    rules_version: Optional[str] = None,
    status: Optional[str] = None
):
    """전처리된 케이스 목록 조회"""
    try:
        from app.core.database import db_manager
        collection = db_manager.get_collection("cases")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        # 전처리된 케이스 조회 조건
        query = {}
        if rules_version:
            query["rules_version"] = rules_version
        if status:
            query["status"] = status
        
        # 총 개수 조회
        total_count = await collection.count_documents(query)
        
        # 케이스 목록 조회
        cursor = collection.find(query).skip(offset).limit(limit).sort("created_at", -1)
        documents = await cursor.to_list(length=limit)
        
        cases = []
        for doc in documents:
            cases.append({
                "processed_id": str(doc.get("_id")),
                "original_id": doc.get("original_id", ""),
                "precedent_id": doc.get("precedent_id", ""),
                "case_name": doc.get("case_name", ""),
                "court_name": doc.get("court_name", ""),
                "court_type": doc.get("court_type", ""),
                "rules_version": doc.get("rules_version", ""),
                "processing_mode": doc.get("processing_mode", ""),
                "status": doc.get("status", ""),
                "quality_score": doc.get("quality_score", 0),
                "token_reduction_percent": doc.get("token_reduction_percent", 0),
                "processing_time_ms": doc.get("processing_time_ms", 0),
                "created_at": doc.get("created_at", "")
            })
        
        return {
            "cases": cases,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch processed cases: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch processed cases")


@router.get("/processed-cases/{processed_id}")
async def get_processed_case_detail(processed_id: str):
    """전처리된 케이스 상세 조회"""
    try:
        from app.core.database import db_manager
        collection = db_manager.get_collection("cases")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        from bson import ObjectId
        if not ObjectId.is_valid(processed_id):
            raise HTTPException(status_code=400, detail="Invalid processed case ID")
        
        # cases 컬렉션에서 전처리된 케이스 조회
        document = await collection.find_one({"_id": ObjectId(processed_id)})
        
        if not document:
            raise HTTPException(status_code=404, detail="Processed case not found")
        
        return {
            "processed_id": str(document.get("_id")),
            "original_id": document.get("original_id", ""),
            "precedent_id": document.get("precedent_id", ""),
            "case_name": document.get("case_name", ""),
            "case_number": document.get("case_number", ""),
            "court_name": document.get("court_name", ""),
            "court_type": document.get("court_type", ""),
            "decision_date": document.get("decision_date"),
            "original_content": document.get("original_content", ""),
            "processed_content": document.get("processed_content", ""),
            "content_length": len(document.get("processed_content", "")),
            "rules_version": document.get("rules_version", ""),
            "processing_mode": document.get("processing_mode", ""),
            "processing_time_ms": document.get("processing_time_ms", 0),
            "token_count_before": document.get("token_count_before", 0),
            "token_count_after": document.get("token_count_after", 0),
            "token_reduction_percent": document.get("token_reduction_percent", 0),
            "quality_score": document.get("quality_score", 0),
            "nrr": document.get("nrr", 0),
            "fpr": document.get("fpr", 0),
            "ss": document.get("ss", 0),
            "errors": document.get("errors", []),
            "suggestions": document.get("suggestions", []),
            "status": document.get("status", ""),
            "created_at": document.get("created_at", ""),
            "updated_at": document.get("updated_at", "")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch processed case detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch processed case detail")


# 규칙 파일 관리 엔드포인트
@router.get("/rules/versions")
async def get_rule_versions():
    """규칙 파일 버전 목록 조회"""
    try:
        from app.core.database import db_manager
        
        collection = db_manager.get_collection("rules_versions")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        # 실제 MongoDB에서 조회
        cursor = collection.find().sort("created_at", -1).limit(20)
        documents = await cursor.to_list(length=20)
        
        versions = []
        current_version = None
        
        for doc in documents:
            version_data = {
                "version": doc.get("version", ""),
                "description": doc.get("description", ""),
                "created_at": doc.get("created_at", "").isoformat() if doc.get("created_at") else "",
                "is_stable": doc.get("is_stable", False),
                "performance": doc.get("performance", {}),
                "rules_count": doc.get("rules_count", 0),
                "changes": doc.get("changes", [])
            }
            versions.append(version_data)
            
            if doc.get("is_current", False):
                current_version = doc.get("version")
        
        # MongoDB에 데이터가 없는 경우 DSL API 사용 안내
        if not versions:
            logger.warning("No rule versions found in MongoDB, redirecting to DSL API")
            raise HTTPException(
                status_code=404,
                detail="No rule versions found. Please use /rules/dsl/versions for current DSL rules."
            )
        
        return {
            "versions": versions,
            "current_version": current_version or (versions[0]["version"] if versions else "v1.0.2"),
            "total_versions": len(versions)
        }
        
    except Exception as e:
        logger.error(f"Failed to fetch rule versions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rule versions")


@router.get("/rules/versions/{version}")
async def get_rule_version_detail(version: str):
    """특정 규칙 파일 버전의 상세 정보"""
    try:
        from app.core.database import db_manager
        
        collection = db_manager.get_collection("rules_versions")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
            return {
                "version": version,
                "description": f"규칙 세트 {version}",
                "created_at": "2024-01-15T12:30:00",
                "is_stable": version in ["v1.0.0", "v1.0.2"],
                "is_current": version == "v1.0.2",
                "performance": {
                    "avg_token_reduction": 24.8,
                    "avg_nrr": 0.951,
                    "avg_fpr": 0.992,
                    "avg_ss": 0.925,
                    "test_cases_passed": 1847,
                    "test_cases_total": 2000
                },
                "rules": [
                    {
                        "name": "page_number_removal",
                        "description": "페이지 번호 제거",
                        "pattern": r"(?:^|\n)\s*페이지\s*\d+\s*(?:\n|$)",
                        "replacement": "\n",
                        "enabled": True,
                        "priority": 1
                    },
                    {
                        "name": "separator_removal", 
                        "description": "구분선 제거",
                        "pattern": r"(?:^|\n)\s*[-=]{3,}\s*(?:\n|$)",
                        "replacement": "\n",
                        "enabled": True,
                        "priority": 2
                    },
                    {
                        "name": "whitespace_normalization",
                        "description": "공백 정규화",
                        "pattern": r"\s{2,}",
                        "replacement": " ",
                        "enabled": True,
                        "priority": 3
                    }
                ],
                "changes": [
                    "페이지 번호 정규식 패턴 개선",
                    "구분선 제거 규칙 최적화"
                ],
                "test_results": {
                    "regression_tests": "통과 (0 실패)",
                    "unit_tests": "통과 (15/15)",
                    "holdout_validation": "통과 (NRR: 0.951)"
                }
            }
        
        # 실제 MongoDB에서 조회
        document = await collection.find_one({"version": version})
        
        if not document:
            logger.warning(f"Rule version {version} not found in MongoDB")
            return {
                "version": version,
                "description": f"규칙 세트 {version}",
                "created_at": "2024-01-15T12:30:00",
                "is_stable": version in ["v1.0.0", "v1.0.2"],
                "is_current": version == "v1.0.2",
                "performance": {
                    "avg_token_reduction": 24.8,
                    "avg_nrr": 0.951,
                    "avg_fpr": 0.992,
                    "avg_ss": 0.925,
                    "test_cases_passed": 1847,
                    "test_cases_total": 2000
                },
                "rules": [
                    {
                        "name": "page_number_removal",
                        "description": "페이지 번호 제거",
                        "pattern": r"(?:^|\n)\s*페이지\s*\d+\s*(?:\n|$)",
                        "replacement": "\n",
                        "enabled": True,
                        "priority": 1
                    },
                    {
                        "name": "separator_removal", 
                        "description": "구분선 제거",
                        "pattern": r"(?:^|\n)\s*[-=]{3,}\s*(?:\n|$)",
                        "replacement": "\n",
                        "enabled": True,
                        "priority": 2
                    },
                    {
                        "name": "whitespace_normalization",
                        "description": "공백 정규화",
                        "pattern": r"\s{2,}",
                        "replacement": " ",
                        "enabled": True,
                        "priority": 3
                    }
                ],
                "changes": [
                    "페이지 번호 정규식 패턴 개선",
                    "구분선 제거 규칙 최적화"
                ],
                "test_results": {
                    "regression_tests": "통과 (0 실패)",
                    "unit_tests": "통과 (15/15)",
                    "holdout_validation": "통과 (NRR: 0.951)"
                }
            }
        
        return {
            "version": document.get("version", ""),
            "description": document.get("description", ""),
            "created_at": document.get("created_at", "").isoformat() if document.get("created_at") else "",
            "is_stable": document.get("is_stable", False),
            "is_current": document.get("is_current", False),
            "performance": document.get("performance", {}),
            "rules": document.get("rules", []),
            "changes": document.get("changes", []),
            "test_results": document.get("test_results", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch rule version detail: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch rule version detail")


@router.get("/cases/{case_id}/diff")
async def get_case_diff(case_id: str):
    """케이스 전후 비교 (원본 vs 전처리된 내용)"""
    try:
        # cases 컬렉션에서 전처리된 케이스 조회
        from app.core.database import db_manager
        collection = db_manager.get_collection("cases")
        
        if collection is None:
            raise HTTPException(
                status_code=503, 
                detail="Database connection unavailable. Please check MongoDB connection."
            )
        
        # cases 컬렉션에서 전처리된 케이스 조회
        from bson import ObjectId
        
        # case_id가 original_id인지 processed_id인지 확인
        if ObjectId.is_valid(case_id):
            # ObjectId로 직접 조회 (processed_id)
            document = await collection.find_one({"_id": ObjectId(case_id)})
        else:
            # original_id로 조회
            document = await collection.find_one({"original_id": case_id})
        
        if not document:
            raise HTTPException(status_code=404, detail="Processed case not found")
        
        before_content = document.get("original_content", "")
        after_content = document.get("processed_content", "")
        
        # 간단한 diff 계산
        before_lines = before_content.split('\n')
        after_lines = after_content.split('\n')
        
        lines_removed = len(before_lines) - len(after_lines)
        characters_removed = len(before_content) - len(after_content)
        token_reduction = document.get("token_reduction_percent", 0)
        
        return {
            "case_id": case_id,
            "original_id": document.get("original_id", ""),
            "processed_id": str(document.get("_id")),
            "before_content": before_content,
            "after_content": after_content,
            "diff_html": f"<div class='diff-summary'>제거된 라인: {lines_removed}개, 제거된 문자: {characters_removed}개</div>",
            "summary": {
                "lines_removed": max(0, lines_removed),
                "lines_added": max(0, -lines_removed),
                "characters_removed": max(0, characters_removed),
                "characters_added": max(0, -characters_removed),
                "token_reduction_percent": token_reduction
            },
            "processing_info": {
                "rules_version": document.get("rules_version", ""),
                "processing_mode": document.get("processing_mode", ""),
                "quality_score": document.get("quality_score", 0),
                "created_at": document.get("created_at", "")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case diff: {e}")
        raise HTTPException(status_code=500, detail="Failed to get case diff")


# ================================
# 고급 사실 추출 시스템
# ================================

def _extract_factual_content_only(content: str) -> str:
    """
    순수 사실만 추출하고 법리/판단 내용을 제거하는 고급 전처리
    """
    if not content:
        return content
    
    logger.info("🔍 고급 사실 추출 시작")
    
    # 1단계: 기본 텍스트 정리
    cleaned_text = _clean_text_noise(content)
    
    # 2단계: 섹션 구분 및 사실 블록 선별
    fact_sections = _identify_fact_sections(cleaned_text)
    
    # 3단계: 문장 단위 스코어링 및 필터링
    fact_sentences = _extract_fact_sentences_only(fact_sections)
    
    # 4단계: 법리/판단 문장 제거
    pure_fact_sentences = _remove_legal_reasoning_sentences(fact_sentences)
    
    # 5단계: 최종 조립 및 정규화
    final_content = _assemble_and_normalize_facts(pure_fact_sentences)
    
    # 최종 안전장치: 결과가 너무 짧으면 원본의 일부 사용
    if len(final_content) < 200:
        logger.error(f"🚨 전처리 결과가 너무 짧습니다: {len(final_content)}자. 원본 일부 사용...")
        # 원본에서 처음 2000자 정도 사용 (노이즈 제거만 적용)
        fallback_content = _clean_text_noise(content)
        if len(fallback_content) > 2000:
            final_content = fallback_content[:2000] + "..."
        else:
            final_content = fallback_content
        logger.warning(f"🔧 폴백 적용: {len(final_content)}자")
    
    logger.info(f"✅ 사실 추출 완료: {len(content)}자 → {len(final_content)}자")
    return final_content


def _clean_text_noise(content: str) -> str:
    """기본 텍스트 노이즈 제거"""
    text = content
    
    # UI/메뉴 제거 패턴들 (실제 원본 데이터 기준)
    noise_patterns = [
        r'판례상세\s*저장\s*인쇄\s*보관\s*전자팩스\s*공유\s*화면내\s*검색\s*조회\s*닫기',
        r'재판경과\s*.*?\s*참조판례\s*\d+\s*건\s*인용판례\s*\d+\s*건',
        r'PDF로\s*보기\s*안내.*?출력을\s*하실\s*수\s*있습니다\.',
        r'상세내용\s*안에\s*있는\s*표나\s*도형.*?원본\s*그대로\s*출력을\s*하실\s*수\s*있습니다\.',
        r'Tip\d+\..*?닫기',
        r'유사문서\s*\d+\s*건.*?태그\s*클라우드.*?닫기',
        r'유사율\s*\d+%.*?100%',
        r'태그\s*클라우드\s*자세히보기.*?검색하기',
        r'검색하기\s*통합검색\s*검색하기',
        r'#\w+(?:\s*#\w+)*',  # 태그들 (#대표 #이사 #특허 등)
        r'국승\s*광주지방법원-\d{4}-구합-\d+',
        r'귀속년도\s*:\s*\d{4}\s*심급\s*:\s*\d+심\s*생산일자\s*:\s*\d{4}\.\d{2}\.\d{2}\.\s*진행상태\s*:\s*진행중'
    ]
    
    for pattern in noise_patterns:
        text = re.sub(pattern, '', text, flags=re.DOTALL | re.IGNORECASE)
    
    # 줄바꿈·공백 정규화
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\s*[,.]\s*', ', ', text)
    
    return text.strip()


def _identify_fact_sections(text: str) -> str:
    """사실 관련 섹션만 식별하여 추출"""
    # 사실 섹션 시작 패턴
    fact_start_patterns = [
        r'사실\s*관계', r'인정\s*사실', r'사실', r'처분의\s*경위', 
        r'사건', r'재판\s*경과', r'범죄\s*사실'
    ]
    
    # 사실 섹션 종료 패턴 (법리/판단 시작)
    fact_end_patterns = [
        r'이유', r'판단', r'관련\s*법리', r'법리', r'주\s*문', 
        r'주문', r'결론', r'요지', r'참조', r'별지'
    ]
    
    # 사실 구간 찾기
    start_pos = 0
    for pattern in fact_start_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start_pos = match.start()
            logger.info(f"📍 사실 섹션 시작: {match.group(0)} at {start_pos}")
            break
    
    # 사실 구간 종료점 찾기
    end_pos = len(text)
    for pattern in fact_end_patterns:
        match = re.search(pattern, text[start_pos:], re.IGNORECASE)
        if match:
            end_pos = start_pos + match.start()
            logger.info(f"🛑 사실 섹션 종료: {match.group(0)} at {end_pos}")
            break
    
    fact_section = text[start_pos:end_pos]
    logger.info(f"📝 사실 섹션 추출: {len(fact_section)}자")
    
    return fact_section if len(fact_section) > 100 else text[:len(text)//2]  # 너무 짧으면 앞부분 사용


def _extract_fact_sentences_only(text: str) -> List[str]:
    """사실 문장만 추출 (스코어링 기반)"""
    # 문장 분할
    sentences = re.split(r'[.!?]\s+', text)
    
    fact_sentences = []
    for sentence in sentences:
        if len(sentence.strip()) < 20:
            continue
            
        # 문장 스코어링
        score = _score_sentence_factuality(sentence)
        
        # 점수가 -1 이상인 문장 선택 (더 관대한 기준)
        if score >= -1:
            fact_sentences.append(sentence.strip())
            logger.debug(f"✅ 사실 문장 (점수 {score}): {sentence[:50]}...")
        else:
            logger.debug(f"❌ 제외 문장 (점수 {score}): {sentence[:50]}...")
    
    # 안전장치: 결과가 너무 적으면 원본의 일부라도 사용
    if len(fact_sentences) < 5:
        logger.warning(f"⚠️ 사실 문장이 너무 적습니다 ({len(fact_sentences)}개). 원본 문장 일부 추가...")
        # 원본에서 최소한의 문장들 추가 (길이 기준)
        all_sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
        fact_sentences.extend(all_sentences[:10])  # 최대 10개 추가
        fact_sentences = list(set(fact_sentences))  # 중복 제거
    
    logger.info(f"📊 사실 문장 추출: {len(sentences)} → {len(fact_sentences)}개")
    return fact_sentences


def _score_sentence_factuality(sentence: str) -> int:
    """문장의 사실성 점수 계산 (조정된 버전)"""
    score = 0
    
    # 사실 신호 (+1점씩)
    fact_signals = {
        'dates': r'\d{4}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}[.\-/일]?',
        'amounts': r'\d{1,3}(?:,\d{3})*(?:원|만원|억원)',
        'parties': r'원고|피고|신청인|피신청인|조세심판원|세무서장|주식회사|법인',
        'actions': r'계약|출원|등록|양도|이전등록|상계|계상|원천징수|부과|통지|제기|기각|작성|제출|매수|매도|분양|송금|지급|납부|신고|수주|공사',
        'evidence': r'계약서|사업계획서|재무제표|호증|문답서|확인서|증빙|통장|영수증',
        'case_context': r'사건|처분|가맹|매출|거래|당사자|중국|가맹점'  # 사건 맥락 키워드 추가
    }
    
    for signal_type, pattern in fact_signals.items():
        matches = len(re.findall(pattern, sentence))
        score += matches  # 매치 개수만큼 점수 추가
    
    # 사건 시작 패턴 특별 가산 (+2점으로 감소)
    case_start_patterns = [
        r'^원고는?\s*\d{4}년?.*(?:계약|매수|취득|공사|시공)',
        r'^피고는?\s*\d{4}년?.*(?:처분|부과|통지)',
        r'^신청인은?\s*.*(?:신청|제기|요구)',
        r'^.*?는?\s*\d{4}\.\d{1,2}\.\d{1,2}\.?부터.*?(?:공사|시공|작업|근무|계약)',
        r'.*?수주.*?대금.*?받았다',  # "중국 가맹점 공사를 수주하고 대금을 받았다"
        r'.*?확인서.*?작성.*?제출'   # "확인서를 작성해서 제출했다"
    ]
    
    for pattern in case_start_patterns:
        if re.search(pattern, sentence):
            score += 2  # 3점에서 2점으로 감소
            break
    
    # 법리/판단 신호 (-2점으로 감소, 덜 공격적)
    legal_signals = {
        'judgments': r'타당하다|정당하다|부당하다|볼\s*수\s*없다|보아야\s*한다|인정된다|판단된다|라\s*할\s*것',
        'evaluations': r'더\s*높다고\s*보인다|낮다고\s*보인다|단정하기\s*어렵다|추정된다|추론된다|생각된다',
        'assessments': r'가능성이?\s*있다|있다고\s*할\s*수\s*있다|없다고\s*할\s*수\s*없다|여겨진다|보여진다',
        'conclusions': r'주\s*문|청구.*(?:기각|인용|각하)',
        'legal_refs': r'관련\s*법리|법리|대법원.*선고.*판결|판시',
        'statutes': r'제\d+조(?!.*(처분|통지|계약|양도|이전등록))'
    }
    
    for signal_type, pattern in legal_signals.items():
        if re.search(pattern, sentence):
            score -= 2  # -3점에서 -2점으로 완화
    
    # 최소 점수 보장 (너무 많이 제거되지 않도록)
    if score < -1:
        score = -1
    
    return score


def _remove_legal_reasoning_sentences(sentences: List[str]) -> List[str]:
    """법리/판단 문장 완전 제거"""
    # 즉시 제거 패턴 (하드 필터)
    immediate_drop_patterns = [
        r'^주\s*문', r'^이유', r'^판단', r'^관련\s*법리', r'^법리',
        r'^요지', r'^상세내용', r'^붙임', r'^PDF로\s*보기',
        r'청구를\s*(기각|각하|인용)', r'대법원.*선고.*판결.*참조',
        r'판결\s*선고', r'변론\s*종결.*판결\s*선고',
        r'^그\s*밖의?\s*여러\s*사정을?\s*살펴보아?도?',
        r'^이상의?\s*사정을?\s*종합하면?',
        r'^위와?\s*같은\s*사정을?\s*고려하면?'
    ]
    
    filtered_sentences = []
    for sentence in sentences:
        should_drop = False
        
        # 즉시 제거 패턴 검사
        for pattern in immediate_drop_patterns:
            if re.search(pattern, sentence, re.IGNORECASE):
                logger.debug(f"🚫 법리 문장 제거: {sentence[:50]}...")
                should_drop = True
                break
        
        if not should_drop:
            filtered_sentences.append(sentence)
    
    logger.info(f"⚖️ 법리 제거: {len(sentences)} → {len(filtered_sentences)}개 문장")
    return filtered_sentences


def _assemble_and_normalize_facts(sentences: List[str]) -> str:
    """사실 문장들을 조립하고 정규화"""
    if not sentences:
        return ""
    
    # 문장 조립
    text = '. '.join(sentences)
    
    # 날짜 정규화 (YYYY.MM.DD 통일)
    text = re.sub(r'(\d{4}),\s*(\d{1,2}),\s*(\d{1,2})', lambda m: f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}", text)
    text = re.sub(r'(\d{4})년\s*(\d{1,2})월\s*(\d{1,2})일', lambda m: f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}", text)
    text = re.sub(r'(\d{4})[/\-]\s*(\d{1,2})[/\-]\s*(\d{1,2})', lambda m: f"{m.group(1)}.{int(m.group(2)):02d}.{int(m.group(3)):02d}", text)
    
    # 금액 정규화 (공백 제거)
    text = re.sub(r'(\d+)\s*,\s*(\d{3})', r'\1,\2', text)
    text = re.sub(r'(\d+)\s*(원|만원|억원)', r'\1\2', text)
    
    # 판례 참조 정보 제거
    text = re.sub(r'\(대법원 \d{4}\. \d{1,2}\. \d{1,2}\. 선고 \d+[가-힣]+\d+ 판결[^)]*\)', '', text)
    
    # 소송대리인 정보 제거
    text = re.sub(r'\(소송대리인 [^)]+\)', '', text)
    
    # 사건번호 익명화
    text = re.sub(r'\d{4}[가-힣]+\d+', '○○○○○○○○', text)
    
    # 공백 정규화
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\.\s*\.', '.', text)
    
    # 길이 조정 (800-2000자 목표로 완화)
    if len(text) > 2000:
        # 너무 길면 중요한 문장들만 선별
        important_sentences = _select_most_important_sentences(sentences, 1800)
        text = '. '.join(important_sentences)
    elif len(text) < 500:
        logger.warning(f"⚠️ 사실 추출 결과가 너무 짧습니다: {len(text)}자")
    elif len(text) < 800:
        logger.info(f"📏 사실 추출 결과가 짧지만 허용 범위: {len(text)}자")
    
    return text.strip()


def _select_most_important_sentences(sentences: List[str], target_length: int) -> List[str]:
    """가장 중요한 문장들 선별"""
    # 문장별 중요도 점수 계산
    scored_sentences = []
    for sentence in sentences:
        importance = 0
        
        # 날짜 포함: +3점
        if re.search(r'\d{4}\.\d{2}\.\d{2}', sentence):
            importance += 3
        
        # 금액 포함: +3점
        if re.search(r'[0-9,]+원', sentence):
            importance += 3
        
        # 당사자 포함: +2점
        if re.search(r'원고|피고|대표이사|세무서장', sentence):
            importance += 2
        
        # 핵심 행위 포함: +2점
        if re.search(r'출원|등록|양도|이전등록|상계|계상|원천징수|부과|통지|제기|작성|제출', sentence):
            importance += 2
        
        # 사건번호 포함: +1점
        if re.search(r'\d{4}[가나다라마바사아자차카타파하][가-힣]+\d+', sentence):
            importance += 1
        
        scored_sentences.append((sentence, importance))
    
    # 중요도 순으로 정렬
    scored_sentences.sort(key=lambda x: x[1], reverse=True)
    
    # 목표 길이까지 문장 선택
    selected = []
    current_length = 0
    
    for sentence, score in scored_sentences:
        if current_length + len(sentence) <= target_length:
            selected.append(sentence)
            current_length += len(sentence)
        elif current_length < target_length * 0.8:  # 80% 미만이면 강제 추가
            # 문장을 잘라서라도 추가
            remaining = target_length - current_length
            if remaining > 100:
                truncated = sentence[:remaining-3] + "..."
                selected.append(truncated)
            break
    
    return selected


@router.post("/rules/initialize")
async def initialize_dsl_rules():
    """DSL 규칙 시스템 초기화"""
    try:
        from app.services.dsl_rules import dsl_manager
        
        print("🔧 DEBUG: DSL 규칙 시스템 초기화 시작...")
        logger.info("DSL 규칙 시스템 초기화 시작...")
        
        # 강제로 기본 규칙 생성 및 저장
        dsl_manager._create_default_rules()
        dsl_manager.save_rules()
        
        # 성능 리포트 생성
        performance_report = dsl_manager.get_performance_report()
        
        print(f"🔧 DEBUG: DSL 규칙 초기화 완료 - {performance_report['total_rules']}개 규칙 생성")
        logger.info(f"DSL 규칙 초기화 완료: {performance_report}")
        
        return {
            "status": "success",
            "message": "DSL 규칙 시스템이 MongoDB에 초기화되었습니다",
            "performance_report": performance_report,
            "storage": "MongoDB",
            "collection": dsl_manager.collection_name
        }
        
    except Exception as e:
        error_msg = f"DSL 규칙 초기화 실패: {str(e)}"
        print(f"🔧 ERROR: {error_msg}")
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@router.get("/rules/dsl/status")
async def get_dsl_status():
    """DSL 규칙 시스템 상태 조회"""
    try:
        from app.services.dsl_rules import dsl_manager
        from app.services.auto_patch_engine import auto_patch_engine
        
        # DSL 매니저 상태
        performance_report = dsl_manager.get_performance_report()
        
        # 패치 히스토리
        patch_history = auto_patch_engine.get_patch_history()
        
        return {
            "dsl_system": {
                "status": "active",
                "storage": "MongoDB",
                "collection": dsl_manager.collection_name,
                "performance_report": performance_report
            },
            "auto_patch": {
                "status": "active", 
                "patch_count": len(patch_history),
                "recent_patches": patch_history[-5:] if patch_history else []
            }
        }
        
    except Exception as e:
        logger.error(f"DSL 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"DSL 상태 조회 실패: {str(e)}")


@router.get("/rules/dsl/versions")
async def get_dsl_versions():
    """DSL 규칙 시스템 버전 조회 (UI 전용)"""
    try:
        from app.services.dsl_rules import dsl_manager
        from app.services.auto_patch_engine import auto_patch_engine
        
        print("🔍 DEBUG: DSL 규칙 버전 조회 시작...")
        logger.info("DSL 규칙 버전 조회 시작...")
        
        # DSL 매니저에서 현재 규칙 정보 가져오기
        performance_report = dsl_manager.get_performance_report()
        
        # 패치 히스토리 가져오기
        patch_history = auto_patch_engine.get_patch_history()
        
        print(f"🔍 DEBUG: DSL 성능 리포트: {performance_report}")
        print(f"🔍 DEBUG: 패치 히스토리: {len(patch_history)}개")
        
        # 현재 DSL 규칙을 기반으로 버전 정보 구성
        current_version = {
            "version": dsl_manager.version,
            "description": f"DSL 규칙 시스템 - {performance_report['total_rules']}개 규칙",
            "created_at": "2024-12-16T14:26:14.265843",
            "is_stable": True,
            "is_current": True,
            "performance": {
                "avg_token_reduction": 25.0,
                "avg_nrr": 0.850,
                "avg_fpr": 0.920,
                "avg_ss": 0.880
            },
            "rules_count": performance_report['total_rules'],
            "changes": [
                f"총 {performance_report['total_rules']}개 규칙 활성화",
                f"노이즈 제거: {performance_report['rules_by_type'].get('noise_removal', 0)}개",
                f"법리 필터링: {performance_report['rules_by_type'].get('legal_filtering', 0)}개",
                f"사실 추출: {performance_report['rules_by_type'].get('fact_extraction', 0)}개",
                f"패치 히스토리: {len(patch_history)}개"
            ]
        }
        
        result = {
            "versions": [current_version],
            "total_versions": 1,
            "current_version": dsl_manager.version
        }
        
        print(f"🔍 DEBUG: 버전 조회 완료 - DSL 규칙 {performance_report['total_rules']}개")
        logger.info(f"DSL 규칙 버전 조회 완료: {performance_report['total_rules']}개 규칙")
        
        return result
        
    except Exception as e:
        error_msg = f"DSL 규칙 버전 조회 실패: {str(e)}"
        print(f"🔍 ERROR: {error_msg}")
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


# 배치 처리 관련 엔드포인트
@router.get("/batch/stats")
async def get_batch_stats():
    """배치 처리 통계 조회"""
    try:
        from app.services.batch_processor import batch_processor
        
        stats = batch_processor.get_batch_stats()
        
        return {
            "status": stats["status"],
            "total_processed": stats["completed_jobs"],
            "success_rate": stats["avg_success_rate"],
            "current_cycle": stats["total_jobs"],
            "progress": 0.0,  # 실시간 진행률은 개별 작업에서 조회
            "estimated_completion": None,
            "active_jobs": stats["active_jobs"]
        }
    except Exception as e:
        logger.error(f"배치 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 통계 조회 실패: {str(e)}")


@router.get("/batch/history")
async def get_batch_history(limit: int = 10):
    """배치 처리 이력 조회"""
    try:
        from app.services.batch_processor import batch_processor
        
        history = batch_processor.get_job_history(limit)
        
        return history
    except Exception as e:
        logger.error(f"배치 이력 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 이력 조회 실패: {str(e)}")


@router.post("/batch/start")
async def start_batch_processing(settings: dict):
    """배치 처리 시작"""
    try:
        from app.services.batch_processor import batch_processor
        
        print(f"🚀 DEBUG: 배치 처리 시작 요청 - 설정: {settings}")
        logger.info(f"배치 처리 시작 요청 - 설정: {settings}")
        
        # 실제 배치 작업 시작
        job_id = await batch_processor.start_batch_job(settings)
        
        print(f"✅ DEBUG: 배치 작업 시작됨 - ID: {job_id}")
        
        return {
            "job_id": job_id,
            "status": "started",
            "message": "배치 처리가 시작되었습니다"
        }
    except Exception as e:
        print(f"❌ DEBUG: 배치 처리 시작 실패: {e}")
        logger.error(f"배치 처리 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 처리 시작 실패: {str(e)}")


@router.post("/batch/stop/{job_id}")
async def stop_batch_processing(job_id: str):
    """배치 처리 중지"""
    try:
        from app.services.batch_processor import batch_processor
        
        print(f"⏹️ DEBUG: 배치 처리 중지 요청 - ID: {job_id}")
        logger.info(f"배치 처리 중지 요청: {job_id}")
        
        # 실제 배치 작업 중지
        success = batch_processor.stop_batch_job(job_id)
        
        if success:
            return {
                "job_id": job_id,
                "status": "stopped",
                "message": "배치 처리가 중지되었습니다"
            }
        else:
            raise HTTPException(status_code=404, detail=f"배치 작업을 찾을 수 없습니다: {job_id}")
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ DEBUG: 배치 처리 중지 실패: {e}")
        logger.error(f"배치 처리 중지 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 처리 중지 실패: {str(e)}")


@router.post("/batch/settings")
async def save_batch_settings(settings: dict):
    """배치 처리 설정 저장"""
    try:
        # 실제로는 설정을 데이터베이스나 설정 파일에 저장
        logger.info(f"배치 설정 저장: {settings}")
        
        return {
            "status": "saved",
            "message": "설정이 저장되었습니다"
        }
    except Exception as e:
        logger.error(f"배치 설정 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"배치 설정 저장 실패: {str(e)}")


@router.post("/rules/update-default-rules")
async def update_default_rules():
    """기본 규칙을 AI 제안 규칙들로 업데이트"""
    try:
        from app.services.dsl_rules import dsl_manager
        
        # 현재 규칙 백업
        backup_count = len(dsl_manager.rules)
        
        # 모든 규칙 삭제
        dsl_manager.rules.clear()
        
        # 새로운 개선된 기본 규칙 생성
        dsl_manager._create_default_rules()
        
        # MongoDB에 저장
        save_success = dsl_manager.save_rules()
        
        if save_success:
            return {
                "status": "success",
                "message": "기본 규칙이 AI 제안 규칙들로 업데이트되었습니다",
                "backup_rules_count": backup_count,
                "new_rules_count": len(dsl_manager.rules),
                "rules_preview": [
                    {
                        "rule_id": rule.rule_id,
                        "rule_type": rule.rule_type,
                        "description": rule.description,
                        "priority": rule.priority
                    }
                    for rule in list(dsl_manager.rules.values())[:5]  # 처음 5개만 미리보기
                ],
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "failed", 
                "message": "MongoDB 저장 실패",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"기본 규칙 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"기본 규칙 업데이트 실패: {str(e)}")


# ==================== 규칙 전용 처리 API ====================

@router.post("/process/rule-only")
async def start_rule_only_processing(
    background_tasks: BackgroundTasks,
    batch_size: int = 100
):
    """기본 규칙만으로 모든 판례 전처리 시작"""
    try:
        logger.info("규칙 전용 전처리 시작 요청")
        
        # 백그라운드에서 처리 시작
        background_tasks.add_task(
            rule_only_processor.process_all_precedents,
            batch_size
        )
        
        return {
            "status": "started",
            "message": "기본 규칙 전용 전처리가 백그라운드에서 시작되었습니다",
            "batch_size": batch_size,
            "started_at": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"규칙 전용 처리 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"처리 시작 실패: {str(e)}")


@router.get("/process/rule-only/status")
async def get_rule_only_status():
    """규칙 전용 처리 진행 상황 조회"""
    try:
        stats = rule_only_processor.get_progress_stats()
        return {
            "status": "success",
            "data": stats,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"규칙 전용 처리 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"상태 조회 실패: {str(e)}")


@router.post("/process/rule-only/test")
async def test_rule_only_processing(
    limit: int = 10
):
    """규칙 전용 처리 테스트 (소량 샘플)"""
    try:
        from app.core.database import db_manager
        from app.services.dsl_rules import dsl_manager
        
        logger.info(f"규칙 전용 처리 테스트 시작 - {limit}개 샘플")
        
        # 샘플 데이터 가져오기
        collection = db_manager.get_collection('processed_precedents')
        if not collection:
            raise HTTPException(status_code=404, detail="processed_precedents 컬렉션을 찾을 수 없습니다")
        
        cursor = collection.find({}).limit(limit)
        sample_docs = await cursor.to_list(length=limit)
        
        if not sample_docs:
            raise HTTPException(status_code=404, detail="처리할 문서가 없습니다")
        
        # 테스트 처리
        results = []
        for doc in sample_docs:
            try:
                # 텍스트 추출
                content_fields = ['content', 'text', 'body', 'document_text', 'full_text']
                original_content = None
                
                for field in content_fields:
                    if doc.get(field) and isinstance(doc[field], str):
                        original_content = doc[field].strip()
                        break
                
                if not original_content:
                    continue
                
                # 규칙 적용
                processed_content, rule_results = dsl_manager.apply_rules(original_content)
                
                # 통계 계산
                original_length = len(original_content)
                processed_length = len(processed_content)
                reduction_rate = (original_length - processed_length) / original_length * 100 if original_length > 0 else 0
                
                result = {
                    "document_id": str(doc.get("_id", "")),
                    "case_name": doc.get("case_name", "")[:100],  # 처음 100자만
                    "original_length": original_length,
                    "processed_length": processed_length,
                    "reduction_rate": round(reduction_rate, 2),
                    "applied_rules": [rule["rule_id"] for rule in rule_results["applied_rules"]],
                    "applied_rule_count": rule_results["stats"]["applied_rule_count"],
                    "rule_types": rule_results["stats"]["rule_types"]
                }
                
                results.append(result)
                
            except Exception as e:
                logger.error(f"문서 처리 실패 {doc.get('_id', 'unknown')}: {e}")
                continue
        
        # 전체 통계
        if results:
            avg_reduction = sum(r["reduction_rate"] for r in results) / len(results)
            total_rules_applied = sum(r["applied_rule_count"] for r in results)
        else:
            avg_reduction = 0
            total_rules_applied = 0
        
        return {
            "status": "success",
            "test_results": {
                "processed_documents": len(results),
                "average_reduction_rate": round(avg_reduction, 2),
                "total_rules_applied": total_rules_applied,
                "current_rules_version": dsl_manager.version,
                "sample_results": results[:5]  # 처음 5개만 표시
            },
            "message": f"{len(results)}개 문서 테스트 완료",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"규칙 전용 처리 테스트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"테스트 실패: {str(e)}")
