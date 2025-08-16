"""
배치 처리 서비스
"""
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging
from app.core.database import db_manager
from app.services.openai_service import OpenAIService
from app.services.dsl_rules import dsl_manager
from app.services.auto_patch_engine import auto_patch_engine

logger = logging.getLogger(__name__)


class BatchJob:
    """배치 작업 클래스"""
    
    def __init__(self, job_id: str, settings: Dict[str, Any]):
        self.job_id = job_id
        self.settings = settings
        self.status = "pending"
        self.created_at = datetime.now()
        self.started_at = None
        self.completed_at = None
        self.total_cases = 0
        self.processed_cases = 0
        self.success_rate = 0.0
        self.errors = []
        self.results = []
        
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            "job_id": self.job_id,
            "status": self.status,
            "settings": self.settings,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_cases": self.total_cases,
            "processed_cases": self.processed_cases,
            "success_rate": self.success_rate,
            "errors": self.errors,
            "results_count": len(self.results)
        }


class BatchProcessor:
    """배치 처리기"""
    
    def __init__(self):
        self.openai_service = OpenAIService()
        self.active_jobs: Dict[str, BatchJob] = {}
        self.job_history: List[BatchJob] = []
        
    async def start_batch_job(self, settings: Dict[str, Any]) -> str:
        """배치 작업 시작"""
        job_id = f"batch_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        job = BatchJob(job_id, settings)
        self.active_jobs[job_id] = job
        
        logger.info(f"배치 작업 시작: {job_id}, 설정: {settings}")
        print(f"🚀 DEBUG: 배치 작업 시작 - ID: {job_id}")
        
        # 백그라운드에서 배치 처리 실행
        asyncio.create_task(self._process_batch_job(job))
        
        return job_id
        
    async def _process_batch_job(self, job: BatchJob):
        """배치 작업 처리"""
        try:
            job.status = "running"
            job.started_at = datetime.now()
            
            print(f"🔄 DEBUG: 배치 작업 실행 시작 - {job.job_id}")
            
            # 1. 샘플 선정
            await self._update_job_status(job, "sampling", "샘플 선정 중...")
            sample_cases = await self._select_sample_cases(job.settings)
            job.total_cases = len(sample_cases)
            
            print(f"📊 DEBUG: 샘플 선정 완료 - {job.total_cases}개 케이스")
            
            # 2. 배치 전처리 및 평가
            await self._update_job_status(job, "processing", "배치 전처리 및 평가 중...")
            
            if job.settings.get('use_batch_api', True):
                # OpenAI Batch API 사용
                print(f"🤖 DEBUG: OpenAI Batch API 사용")
                batch_results = await self.openai_service.evaluate_batch_cases(sample_cases)
            else:
                # 순차 처리
                print(f"🔄 DEBUG: 순차 처리 사용")
                batch_results = await self._process_sequential(sample_cases, job)
            
            job.results = batch_results
            job.processed_cases = len(batch_results)
            
            print(f"✅ DEBUG: 배치 처리 완료 - {job.processed_cases}개 처리됨")
            
            # 3. 결과 분석 및 패치 적용
            await self._update_job_status(job, "analyzing", "결과 분석 및 패치 적용 중...")
            await self._analyze_and_apply_patches(job, batch_results)
            
            # 4. 완료 처리
            job.status = "completed"
            job.completed_at = datetime.now()
            job.success_rate = job.processed_cases / job.total_cases if job.total_cases > 0 else 0
            
            print(f"🎉 DEBUG: 배치 작업 완료 - {job.job_id}")
            logger.info(f"배치 작업 완료: {job.job_id}, 성공률: {job.success_rate:.2%}")
            
        except Exception as e:
            job.status = "failed"
            job.errors.append(str(e))
            print(f"❌ DEBUG: 배치 작업 실패 - {job.job_id}: {e}")
            logger.error(f"배치 작업 실패: {job.job_id}: {e}")
        finally:
            # 활성 작업에서 제거하고 히스토리에 추가
            if job.job_id in self.active_jobs:
                del self.active_jobs[job.job_id]
            self.job_history.append(job)
            
    async def _select_sample_cases(self, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
        """샘플 케이스 선정"""
        sample_size = settings.get('sample_size', 10)
        
        print(f"📋 DEBUG: 샘플 선정 시작 - 크기: {sample_size}")
        
        try:
            # MongoDB에서 케이스 조회
            print(f"🔍 DEBUG: MongoDB 컬렉션 가져오기 시도...")
            print(f"🔍 DEBUG: db_manager 객체: {type(db_manager)}")
            print(f"🔍 DEBUG: db_manager 상태: {hasattr(db_manager, 'get_collection')}")
            
            collection = db_manager.get_collection('cases')
            print(f"🔍 DEBUG: 컬렉션 객체: {type(collection)}")
            print(f"🔍 DEBUG: 컬렉션 None 여부: {collection is None}")
            
            if collection is None:
                raise Exception("cases 컬렉션을 찾을 수 없습니다")
            
            print(f"✅ DEBUG: cases 컬렉션 연결 성공")
            
            # 층화 샘플링 (간단한 버전)
            pipeline = [
                {"$match": {"content": {"$exists": True, "$ne": ""}}},
                {"$sample": {"size": sample_size}}
            ]
            
            print(f"🔍 DEBUG: 집계 파이프라인 실행 중...")
            cursor = collection.aggregate(pipeline)
            cases = await cursor.to_list(length=sample_size)
            
            print(f"✅ DEBUG: MongoDB에서 {len(cases)}개 케이스 조회 완료")
            
            # 케이스 데이터 변환
            sample_cases = []
            for case in cases:
                case_data = {
                    "case_id": str(case.get("_id")),
                    "before_content": case.get("content", ""),
                    "after_content": "",  # 전처리 후 채워짐
                    "metadata": {
                        "court_type": case.get("court_type", ""),
                        "case_type": case.get("case_type", ""),
                        "year": case.get("year", "")
                    }
                }
                
                # DSL 규칙 적용하여 전처리
                processed_content, rule_results = dsl_manager.apply_rules(
                    case_data["before_content"], 
                    rule_types=None
                )
                case_data["after_content"] = processed_content
                
                sample_cases.append(case_data)
            
            print(f"✅ DEBUG: 샘플 선정 완료 - {len(sample_cases)}개 케이스")
            return sample_cases
            
        except Exception as e:
            print(f"❌ DEBUG: 샘플 선정 실패: {e}")
            print(f"❌ DEBUG: 오류 타입: {type(e)}")
            print(f"❌ DEBUG: 오류 상세: {str(e)}")
            logger.error(f"샘플 선정 실패: {e}")
            raise
    
    async def _process_sequential(self, cases: List[Dict[str, Any]], job: BatchJob) -> List[Any]:
        """순차 처리 (Batch API 대신)"""
        results = []
        
        for i, case in enumerate(cases):
            try:
                print(f"🔄 DEBUG: 순차 처리 {i+1}/{len(cases)} - {case['case_id']}")
                
                # 단일 케이스 평가
                metrics, errors, suggestions_json = await self.openai_service.evaluate_single_case(
                    case["before_content"],
                    case["after_content"], 
                    case["metadata"]
                )
                
                results.append((case["case_id"], metrics, errors, suggestions_json))
                job.processed_cases = i + 1
                
            except Exception as e:
                print(f"❌ DEBUG: 순차 처리 실패 - {case['case_id']}: {e}")
                job.errors.append(f"케이스 {case['case_id']} 처리 실패: {str(e)}")
        
        return results
    
    async def _analyze_and_apply_patches(self, job: BatchJob, results: List[Any]):
        """결과 분석 및 패치 적용"""
        print(f"🔍 DEBUG: 결과 분석 및 패치 적용 시작")
        
        try:
            all_suggestions = []
            
            # 모든 결과에서 제안 수집
            for result in results:
                case_id, metrics, errors, suggestions_json = result
                
                if suggestions_json:
                    try:
                        import json
                        suggestions_data = json.loads(suggestions_json)
                        suggestions = suggestions_data.get("suggestions", [])
                        
                        for suggestion in suggestions:
                            # PatchSuggestion 객체로 변환
                            from app.services.auto_patch_engine import PatchSuggestion
                            patch = PatchSuggestion(
                                suggestion_id=f"{case_id}_{len(all_suggestions)}",
                                rule_type=suggestion.get("rule_type", "noise_removal"),
                                description=suggestion.get("description", ""),
                                pattern_before=suggestion.get("pattern_before", ""),
                                pattern_after=suggestion.get("pattern_after", ""),
                                confidence_score=suggestion.get("confidence_score", 0.8),
                                estimated_improvement=suggestion.get("estimated_improvement", ""),
                                applicable_cases=suggestion.get("applicable_cases", [])
                            )
                            all_suggestions.append(patch)
                            
                    except Exception as e:
                        print(f"⚠️ DEBUG: 제안 파싱 실패 - {case_id}: {e}")
            
            print(f"📈 DEBUG: 총 {len(all_suggestions)}개 제안 수집됨")
            
            # 자동 패치 적용
            if all_suggestions:
                patch_results = auto_patch_engine.auto_apply_patches(
                    all_suggestions,
                    auto_apply_threshold=0.5  # 모든 제안 적용
                )
                
                print(f"🔧 DEBUG: 패치 적용 결과 - 자동 적용: {patch_results['auto_applied']}개")
                
        except Exception as e:
            print(f"❌ DEBUG: 결과 분석 실패: {e}")
            logger.error(f"결과 분석 실패: {e}")
    
    async def _update_job_status(self, job: BatchJob, status: str, message: str):
        """작업 상태 업데이트"""
        job.status = status
        print(f"📊 DEBUG: 작업 상태 업데이트 - {job.job_id}: {status} - {message}")
        logger.info(f"배치 작업 상태 업데이트: {job.job_id} - {status}")
        
    def stop_batch_job(self, job_id: str) -> bool:
        """배치 작업 중지"""
        if job_id in self.active_jobs:
            job = self.active_jobs[job_id]
            job.status = "cancelled"
            job.completed_at = datetime.now()
            
            # 히스토리로 이동
            del self.active_jobs[job_id]
            self.job_history.append(job)
            
            print(f"⏹️ DEBUG: 배치 작업 중지 - {job_id}")
            logger.info(f"배치 작업 중지: {job_id}")
            return True
        return False
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """작업 상태 조회"""
        # 활성 작업에서 찾기
        if job_id in self.active_jobs:
            return self.active_jobs[job_id].to_dict()
        
        # 히스토리에서 찾기
        for job in self.job_history:
            if job.job_id == job_id:
                return job.to_dict()
        
        return None
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """배치 통계 조회"""
        active_count = len(self.active_jobs)
        total_jobs = len(self.job_history) + active_count
        
        # 최근 완료된 작업들의 성공률 계산
        completed_jobs = [job for job in self.job_history if job.status == "completed"]
        avg_success_rate = 0.0
        if completed_jobs:
            avg_success_rate = sum(job.success_rate for job in completed_jobs) / len(completed_jobs)
        
        return {
            "active_jobs": active_count,
            "total_jobs": total_jobs,
            "completed_jobs": len(completed_jobs),
            "avg_success_rate": avg_success_rate,
            "status": "running" if active_count > 0 else "idle"
        }
    
    def get_job_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """작업 히스토리 조회"""
        # 최신 순으로 정렬
        sorted_history = sorted(self.job_history, key=lambda x: x.created_at, reverse=True)
        return [job.to_dict() for job in sorted_history[:limit]]


# 전역 배치 프로세서 인스턴스
batch_processor = BatchProcessor()