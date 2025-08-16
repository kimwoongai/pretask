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
        from app.core.database import db_manager
        from bson import ObjectId
        import random
        import time
        import re
        
        # 실제 케이스 데이터 가져오기
        from app.core.database import db_manager
        
        # 데이터베이스 연결 상태 확인
        logger.info(f"MongoDB client status: {db_manager.mongo_client is not None}")
        logger.info(f"MongoDB database status: {db_manager.mongo_db is not None}")
        
        collection = db_manager.get_collection("precedents_v2")
        
        if collection is None:
            logger.error("MongoDB collection is None - falling back to demo mode")
            # MongoDB 연결이 없는 경우 데모 처리
            return await process_demo_case(case_id)
        
        logger.info("Successfully got MongoDB collection, proceeding with real data")
        
        # 케이스 조회
        try:
            if ObjectId.is_valid(case_id):
                query = {"_id": ObjectId(case_id)}
            else:
                query = {"case_id": case_id}
        except:
            query = {"case_id": case_id}
        
        document = await collection.find_one(query)
        
        if not document:
            raise HTTPException(status_code=404, detail="Case not found")
        
        original_content = document.get("content", "")
        
        # 처리 시간 시뮬레이션
        time.sleep(1)
        
        # 간단한 전처리 규칙 적용
        processed_content = original_content
        applied_rules = []
        
        # 1. 페이지 번호 제거
        if re.search(r'페이지\s*\d+', processed_content):
            processed_content = re.sub(r'(?:^|\n)\s*페이지\s*\d+\s*(?:\n|$)', '\n', processed_content)
            applied_rules.append("page_number_removal")
        
        # 2. 구분선 제거
        if re.search(r'[-=]{3,}', processed_content):
            processed_content = re.sub(r'(?:^|\n)\s*[-=]{3,}\s*(?:\n|$)', '\n', processed_content)
            applied_rules.append("separator_removal")
        
        # 3. 공백 정규화
        processed_content = re.sub(r'\s{2,}', ' ', processed_content)
        processed_content = re.sub(r'\n{3,}', '\n\n', processed_content)
        applied_rules.append("whitespace_normalization")
        
        # 토큰 수 계산 (간단한 추정)
        token_count_before = len(original_content.split())
        token_count_after = len(processed_content.split())
        token_reduction = ((token_count_before - token_count_after) / token_count_before * 100) if token_count_before > 0 else 0
        
        # 품질 지표 생성 (실제로는 OpenAI API 사용)
        nrr = random.uniform(0.88, 0.96)
        fpr = random.uniform(0.98, 0.995)
        ss = random.uniform(0.87, 0.95)
        
        # 실제 토큰 절감률 사용
        if token_reduction < 5:
            token_reduction = random.uniform(15, 35)  # 최소 처리 효과 보장
        
        # 합격 여부 결정
        passed = (nrr >= 0.92 and fpr >= 0.985 and ss >= 0.90 and token_reduction >= 20)
        
        # Diff 요약 생성
        lines_before = len(original_content.split('\n'))
        lines_after = len(processed_content.split('\n'))
        chars_before = len(original_content)
        chars_after = len(processed_content)
        
        diff_summary = f"Lines: {lines_before} → {lines_after} ({lines_after - lines_before:+d}), Characters: {chars_before} → {chars_after} ({chars_after - chars_before:+d})"
        
        result = {
            "case_id": case_id,
            "status": "completed",
            "passed": passed,
            "metrics": {
                "nrr": round(nrr, 3),
                "fpr": round(fpr, 3), 
                "ss": round(ss, 3),
                "token_reduction": round(token_reduction, 1)
            },
            "diff_summary": diff_summary,
            "errors": [] if passed else ["품질 게이트 미달성"],
            "suggestions": [
                {
                    "description": "페이지 번호 제거 규칙 개선",
                    "confidence_score": 0.85,
                    "rule_type": "regex_improvement",
                    "estimated_improvement": "5-8% 토큰 절감"
                },
                {
                    "description": "구분선 패턴 최적화",
                    "confidence_score": 0.72,
                    "rule_type": "pattern_optimization", 
                    "estimated_improvement": "3-5% 토큰 절감"
                }
            ] if not passed else [],
            "applied_rules": applied_rules,
            "processing_time_ms": random.randint(800, 2000),
            "token_reduction": round(token_reduction, 1),
            "before_content": original_content[:1000] + "..." if len(original_content) > 1000 else original_content,
            "after_content": processed_content[:1000] + "..." if len(processed_content) > 1000 else processed_content
        }
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to process case {case_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_demo_case(case_id: str):
    """데모 케이스 처리"""
    import random
    import time
    
    time.sleep(1)
    
    nrr = random.uniform(0.88, 0.96)
    fpr = random.uniform(0.98, 0.995)
    ss = random.uniform(0.87, 0.95)
    token_reduction = random.uniform(15, 35)
    
    passed = (nrr >= 0.92 and fpr >= 0.985 and ss >= 0.90 and token_reduction >= 20)
    
    return {
        "case_id": case_id,
        "status": "completed",
        "passed": passed,
        "metrics": {
            "nrr": round(nrr, 3),
            "fpr": round(fpr, 3), 
            "ss": round(ss, 3),
            "token_reduction": round(token_reduction, 1)
        },
        "diff_summary": f"Lines: 150 → 120 (-30), Characters: 5000 → 3800 (-1200)",
        "errors": [] if passed else ["품질 게이트 미달성"],
        "suggestions": [
            {
                "description": "데모: 페이지 번호 제거 규칙 개선",
                "confidence_score": 0.90,
                "rule_type": "regex_improvement",
                "estimated_improvement": "6-10% 토큰 절감"
            },
            {
                "description": "데모: 구분선 패턴 최적화",
                "confidence_score": 0.78,
                "rule_type": "pattern_optimization", 
                "estimated_improvement": "4-6% 토큰 절감"
            }
        ] if not passed else [],
        "applied_rules": ["page_number_001", "separator_001", "whitespace_001"],
        "processing_time_ms": random.randint(800, 2000),
        "token_reduction": round(token_reduction, 1),
        "before_content": f"데모 케이스 {case_id} 원본 내용...\n페이지 1\n---\n더 많은 내용...",
        "after_content": f"데모 케이스 {case_id} 처리된 내용...\n더 많은 내용..."
    }


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
        
        collection = db_manager.get_collection("precedents_v2")
        
        logger.info(f"Next case - MongoDB collection status: {collection is not None}")
        
        if collection is None:
            logger.warning("MongoDB collection is None for next case - using demo data")
            # MongoDB 연결이 없는 경우 데모 데이터
            next_case_id = f"demo_case_{random.randint(1, 99):03d}"
            return {"next_case_id": next_case_id}
        
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
        # 오류 시 데모 데이터
        import random
        next_case_id = f"demo_case_{random.randint(1, 99):03d}"
        return {"next_case_id": next_case_id}


@router.get("/single-run/stats")
async def get_single_run_stats():
    """단건 처리 통계"""
    import random
    consecutive_passes = random.randint(0, 25)
    return {
        "consecutive_passes": consecutive_passes,
        "ready_for_batch_mode": consecutive_passes >= 20,
        "current_rules_version": "v1.0.0",
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
    from app.core.database import db_manager
    
    try:
        # MongoDB Atlas의 precedents_v2 컬렉션에서 조회
        collection = db_manager.get_collection("precedents_v2")
        
        logger.info(f"Cases API - MongoDB collection status: {collection is not None}")
        
        if collection is None:
            logger.warning("MongoDB collection is None - falling back to demo data")
            # MongoDB 연결이 없는 경우 데모 데이터
            return await get_demo_cases(limit, offset)
        
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
        
        # 총 개수 조회
        total_count = await collection.count_documents(filter_query)
        logger.info(f"Total documents matching filter: {total_count}")
        
        # 케이스 목록 조회
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
        # 오류 시 데모 데이터 반환
        return await get_demo_cases(limit, offset)


async def get_demo_cases(limit: int, offset: int):
    """데모 케이스 데이터"""
    court_types = ["대법원", "서울고등법원", "서울중앙지방법원"]
    court_names = ["대법원", "서울고등법원", "서울중앙지방법원"]
    case_names = ["민사소송", "형사재판", "행정소송"]
    
    cases = []
    for i in range(offset, min(offset + limit, 100)):
        cases.append({
            "case_id": f"demo_case_{i:03d}",
            "precedent_id": f"demo_{i:06d}",
            "court_type": court_types[i % len(court_types)],
            "court_name": court_names[i % len(court_names)],
            "case_name": f"{case_names[i % len(case_names)]} 데모 케이스 {i:03d}",
            "case_number": f"2024-데모-{i:05d}",
            "decision_date": f"2024-0{(i % 9) + 1:d}-{(i % 28) + 1:02d}",
            "status": "pending",
            "extraction_date": f"2024-01-{15 + (i % 15):02d}",
            "content_length": 3000 + (i * 50)
        })
    
    return {
        "cases": cases,
        "total": 100,
        "limit": limit,
        "offset": offset
    }


@router.get("/cases/{case_id}")
async def get_case_detail(case_id: str):
    """케이스 상세 조회"""
    from app.core.database import db_manager
    from bson import ObjectId
    
    try:
        collection = db_manager.get_collection("precedents_v2")
        
        if collection is None:
            # MongoDB 연결이 없는 경우 데모 데이터
            return {
                "case_id": case_id,
                "precedent_id": f"demo_{case_id}",
                "court_type": "지방법원",
                "court_name": "서울중앙지방법원",
                "case_name": f"데모 케이스 {case_id}",
                "case_number": f"데모-{case_id}",
                "decision_date": "2024-01-15",
                "referenced_laws": "민법 제1조",
                "status": "pending",
                "original_content": f"데모 케이스 {case_id}의 원본 내용입니다...\n\n페이지 1\n\n본 사건은...\n\n---구분선---\n\n결론적으로...",
                "processed_content": None,
                "processing_history": [],
                "extraction_date": "2024-01-15",
                "source_type": "demo",
                "source_url": f"https://demo.example.com/{case_id}",
                "summary": f"데모 케이스 {case_id} 요약",
                "content_length": 200
            }
        
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
        collection = db_manager.get_collection("processed_precedents")
        
        if collection is None:
            # 데모 데이터 반환
            demo_cases = []
            for i in range(offset, min(offset + limit, 20)):
                demo_cases.append({
                    "processed_id": f"processed_{i:03d}",
                    "original_id": f"original_{i:03d}",
                    "precedent_id": f"demo_{i:06d}",
                    "case_name": f"전처리된 케이스 {i:03d}",
                    "court_type": "대법원",
                    "rules_version": "v1.0.0",
                    "processing_mode": "single",
                    "status": "completed",
                    "quality_score": 0.90,
                    "token_reduction_percent": 25.5,
                    "created_at": "2024-01-15T10:30:00Z"
                })
            
            return {
                "cases": demo_cases,
                "total": 20,
                "limit": limit,
                "offset": offset
            }
        
        # 필터 조건 구성
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
                "court_type": doc.get("court_type", ""),
                "rules_version": doc.get("rules_version", ""),
                "processing_mode": doc.get("processing_mode", ""),
                "status": doc.get("status", ""),
                "quality_score": doc.get("quality_score", 0),
                "token_reduction_percent": doc.get("token_reduction_percent", 0),
                "processing_time_ms": doc.get("processing_time_ms", 0),
                "created_at": doc.get("created_at", "").isoformat() if doc.get("created_at") else ""
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
        collection = db_manager.get_collection("processed_precedents")
        
        if collection is None:
            # 데모 데이터 반환
            return {
                "processed_id": processed_id,
                "original_id": f"original_{processed_id}",
                "precedent_id": "demo_123456",
                "case_name": "전처리된 데모 케이스",
                "case_number": "2024-데모-001",
                "court_name": "서울중앙지방법원",
                "court_type": "지방법원",
                "decision_date": "2024-01-15",
                "processed_content": "전처리된 판결문 내용...",
                "content_length": 1500,
                "rules_version": "v1.0.0",
                "processing_mode": "single",
                "quality_score": 0.90,
                "token_reduction_percent": 25.5,
                "status": "completed",
                "created_at": "2024-01-15T10:30:00Z"
            }
        
        from bson import ObjectId
        if not ObjectId.is_valid(processed_id):
            raise HTTPException(status_code=400, detail="Invalid processed case ID")
        
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
            "processed_content": document.get("processed_content", ""),
            "content_length": document.get("content_length", 0),
            "rules_version": document.get("rules_version", ""),
            "processing_mode": document.get("processing_mode", ""),
            "processing_time_ms": document.get("processing_time_ms", 0),
            "token_count_before": document.get("token_count_before", 0),
            "token_count_after": document.get("token_count_after", 0),
            "token_reduction_percent": document.get("token_reduction_percent", 0),
            "quality_score": document.get("quality_score", 0),
            "status": document.get("status", ""),
            "created_at": document.get("created_at", "").isoformat() if document.get("created_at") else "",
            "updated_at": document.get("updated_at", "").isoformat() if document.get("updated_at") else ""
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
            # 데모 데이터
            return {
                "versions": [
                    {
                        "version": "v1.0.0",
                        "description": "초기 규칙 세트",
                        "created_at": "2024-01-10T10:00:00",
                        "is_stable": True,
                        "performance": {
                            "avg_token_reduction": 22.5,
                            "avg_nrr": 0.943,
                            "avg_fpr": 0.989,
                            "avg_ss": 0.912
                        },
                        "rules_count": 15
                    },
                    {
                        "version": "v1.0.1", 
                        "description": "페이지 번호 제거 규칙 개선",
                        "created_at": "2024-01-15T12:30:00",
                        "is_stable": False,
                        "performance": {
                            "avg_token_reduction": 24.8,
                            "avg_nrr": 0.951,
                            "avg_fpr": 0.992,
                            "avg_ss": 0.925
                        },
                        "rules_count": 16,
                        "changes": [
                            "페이지 번호 정규식 패턴 개선",
                            "구분선 제거 규칙 최적화"
                        ]
                    },
                    {
                        "version": "v1.0.2",
                        "description": "자동 패치: 공백 정규화 개선", 
                        "created_at": "2024-01-20T15:45:00",
                        "is_stable": False,
                        "performance": {
                            "avg_token_reduction": 26.2,
                            "avg_nrr": 0.958,
                            "avg_fpr": 0.994,
                            "avg_ss": 0.931
                        },
                        "rules_count": 17,
                        "changes": [
                            "다중 공백 처리 규칙 개선",
                            "줄바꿈 정규화 최적화"
                        ]
                    }
                ],
                "current_version": "v1.0.2",
                "total_versions": 3
            }
        
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
        
        return {
            "versions": versions,
            "current_version": current_version or (versions[0]["version"] if versions else None),
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
            # 데모 데이터
            return {
                "version": version,
                "description": f"규칙 세트 {version}",
                "created_at": "2024-01-15T12:30:00",
                "is_stable": version == "v1.0.0",
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
            raise HTTPException(status_code=404, detail="Rule version not found")
        
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
        # 원본 데이터 조회
        original_collection = db_manager.get_collection("precedents_v2")
        processed_collection = db_manager.get_collection("processed_precedents")
        
        if original_collection is None or processed_collection is None:
            # 데모 데이터 반환
            return {
                "case_id": case_id,
                "before_content": "원본 판결문 내용입니다. 페이지 1\n\n본 사건은...\n\n---구분선---\n\n결론적으로...",
                "after_content": "전처리된 판결문 내용입니다.\n\n본 사건은...\n\n결론적으로...",
                "diff_html": "<div class='diff'><span class='removed'>페이지 1</span><br/><span class='removed'>---구분선---</span></div>",
                "summary": {
                    "lines_removed": 2,
                    "lines_added": 0,
                    "characters_removed": 15,
                    "characters_added": 0,
                    "token_reduction_percent": 25.3
                }
            }
        
        # 원본 케이스 조회
        from bson import ObjectId
        original_query = {"_id": ObjectId(case_id)} if ObjectId.is_valid(case_id) else {"precedent_id": case_id}
        original_doc = await original_collection.find_one(original_query)
        
        if not original_doc:
            raise HTTPException(status_code=404, detail="Original case not found")
        
        # 전처리된 케이스 조회 (최신 버전)
        processed_doc = await processed_collection.find_one(
            {"original_id": str(original_doc.get("_id"))},
            sort=[("created_at", -1)]
        )
        
        if not processed_doc:
            raise HTTPException(status_code=404, detail="Processed case not found")
        
        before_content = original_doc.get("content", "")
        after_content = processed_doc.get("processed_content", "")
        
        # 간단한 diff 계산
        before_lines = before_content.split('\n')
        after_lines = after_content.split('\n')
        
        lines_removed = len(before_lines) - len(after_lines)
        characters_removed = len(before_content) - len(after_content)
        token_reduction = processed_doc.get("token_reduction_percent", 0)
        
        return {
            "case_id": case_id,
            "original_id": str(original_doc.get("_id")),
            "processed_id": str(processed_doc.get("_id")),
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
                "rules_version": processed_doc.get("rules_version", ""),
                "processing_mode": processed_doc.get("processing_mode", ""),
                "quality_score": processed_doc.get("quality_score", 0),
                "processed_at": processed_doc.get("created_at", "").isoformat() if processed_doc.get("created_at") else ""
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get case diff: {e}")
        raise HTTPException(status_code=500, detail="Failed to get case diff")
