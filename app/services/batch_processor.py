"""
Batch API 반복 개선 시스템
"""
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging

from app.models.document import (
    BatchJob, DocumentCase, ProcessingResult, QualityMetrics,
    ProcessingStatus, ProcessingMode, FailureCluster
)
from app.core.config import settings, processing_mode, quality_gates
from app.core.database import document_repo, result_repo, cache_manager
from app.services.rules_engine import DSLEngine, AutoPatcher, RulesVersionManager
from app.services.openai_service import OpenAIService
from app.services.safety_gates import safety_gate_manager, oscillation_prevention

logger = logging.getLogger(__name__)


class BatchProcessor:
    """배치 처리기"""
    
    def __init__(self):
        self.dsl_engine = DSLEngine()
        self.auto_patcher = AutoPatcher(self.dsl_engine)
        self.openai_service = OpenAIService()
        self.version_manager = RulesVersionManager()
        self.current_rules_version = "v1.0.0"
        self.improvement_cycles = 0
        self.no_improvement_count = 0
    
    async def start_batch_improvement_cycle(
        self, 
        sample_size: int = 200,
        stratification_criteria: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """배치 개선 사이클 시작"""
        
        try:
            logger.info(f"Starting batch improvement cycle with sample size: {sample_size}")
            
            # 배치 작업 생성
            batch_job = await self._create_batch_job(sample_size, stratification_criteria)
            
            # 사이클 실행
            cycle_result = await self._execute_improvement_cycle(batch_job)
            
            # 결과 분석 및 다음 단계 결정
            next_action = await self._analyze_cycle_result(cycle_result)
            
            return {
                "batch_job_id": batch_job.job_id,
                "cycle_result": cycle_result,
                "next_action": next_action,
                "improvement_cycles": self.improvement_cycles
            }
            
        except Exception as e:
            logger.error(f"Batch improvement cycle failed: {e}")
            raise
    
    async def _create_batch_job(
        self, 
        sample_size: int, 
        stratification_criteria: Optional[Dict[str, Any]]
    ) -> BatchJob:
        """배치 작업 생성"""
        
        job_id = f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # 기본 층화 기준
        if not stratification_criteria:
            stratification_criteria = {
                "court_types": ["고등법원", "지방법원", "행정법원"],
                "case_types": ["민사", "형사", "행정"],
                "years": list(range(2020, 2025)),
                "format_types": ["pdf", "hwp", "doc"]
            }
        
        batch_job = BatchJob(
            job_id=job_id,
            mode=ProcessingMode.BATCH_IMPROVEMENT,
            sample_size=sample_size,
            stratification_criteria=stratification_criteria,
            rules_version=self.current_rules_version,
            total_cases=sample_size
        )
        
        return batch_job
    
    async def _execute_improvement_cycle(self, batch_job: BatchJob) -> Dict[str, Any]:
        """개선 사이클 실행"""
        
        cycle_steps = []
        
        try:
            # 1. 샘플 선정
            step_result = await self._execute_sample_selection(batch_job)
            cycle_steps.append(step_result)
            
            # 2. 전처리 실행
            step_result = await self._execute_preprocessing_batch(batch_job)
            cycle_steps.append(step_result)
            
            # 3. Batch 평가
            step_result = await self._execute_batch_evaluation(batch_job)
            cycle_steps.append(step_result)
            
            # 4. 실패 클러스터링
            step_result = await self._execute_failure_clustering(batch_job)
            cycle_steps.append(step_result)
            
            # 5. 자동 패치
            step_result = await self._execute_auto_patching(batch_job)
            cycle_steps.append(step_result)
            
            # 6. 게이트 검사
            step_result = await self._execute_safety_gates(batch_job)
            cycle_steps.append(step_result)
            
            # 7. 재실행 (조건부)
            if step_result.get("gates_passed", False):
                step_result = await self._execute_revalidation(batch_job)
                cycle_steps.append(step_result)
            
            return {
                "job_id": batch_job.job_id,
                "status": "completed",
                "steps": cycle_steps,
                "total_duration_ms": sum(step.get("duration_ms", 0) for step in cycle_steps),
                "final_metrics": cycle_steps[-1].get("metrics") if cycle_steps else None
            }
            
        except Exception as e:
            logger.error(f"Improvement cycle failed: {e}")
            return {
                "job_id": batch_job.job_id,
                "status": "failed",
                "error": str(e),
                "steps": cycle_steps
            }
    
    async def _execute_sample_selection(self, batch_job: BatchJob) -> Dict[str, Any]:
        """샘플 선정 실행"""
        start_time = datetime.now()
        
        try:
            # 층화 샘플링 실행
            selected_cases = await document_repo.get_stratified_sample(
                batch_job.stratification_criteria,
                batch_job.sample_size
            )
            
            # 다양성 검증
            diversity_score = self._calculate_sample_diversity(selected_cases)
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "step": "sample_selection",
                "status": "completed",
                "selected_count": len(selected_cases),
                "diversity_score": diversity_score,
                "duration_ms": duration_ms,
                "sample_distribution": self._analyze_sample_distribution(selected_cases)
            }
            
        except Exception as e:
            logger.error(f"Sample selection failed: {e}")
            return {
                "step": "sample_selection",
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_preprocessing_batch(self, batch_job: BatchJob) -> Dict[str, Any]:
        """배치 전처리 실행"""
        start_time = datetime.now()
        
        try:
            # 현재 규칙으로 전량 처리
            processed_cases = []
            failed_cases = []
            
            # 샘플 케이스들 가져오기
            sample_cases = await document_repo.get_stratified_sample(
                batch_job.stratification_criteria,
                batch_job.sample_size
            )
            
            # 병렬 처리
            semaphore = asyncio.Semaphore(settings.max_concurrent_batches)
            tasks = [
                self._process_single_case_batch(case, semaphore)
                for case in sample_cases
            ]
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    failed_cases.append({
                        "case_id": sample_cases[i]["case_id"],
                        "error": str(result)
                    })
                else:
                    processed_cases.append(result)
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "step": "preprocessing_batch",
                "status": "completed",
                "processed_count": len(processed_cases),
                "failed_count": len(failed_cases),
                "success_rate": len(processed_cases) / len(sample_cases) if sample_cases else 0,
                "duration_ms": duration_ms,
                "processed_cases": processed_cases,
                "failed_cases": failed_cases
            }
            
        except Exception as e:
            logger.error(f"Batch preprocessing failed: {e}")
            return {
                "step": "preprocessing_batch",
                "status": "failed",
                "error": str(e)
            }
    
    async def _process_single_case_batch(
        self, 
        case_data: Dict[str, Any], 
        semaphore: asyncio.Semaphore
    ) -> Dict[str, Any]:
        """단일 케이스 배치 처리"""
        async with semaphore:
            try:
                # 규칙 적용
                metadata = {
                    "court_type": case_data.get("court_type"),
                    "case_type": case_data.get("case_type"),
                    "year": case_data.get("year"),
                    "format_type": case_data.get("format_type")
                }
                
                processed_content, applied_rules = self.dsl_engine.apply_rules(
                    case_data["original_content"], metadata
                )
                
                return {
                    "case_id": case_data["case_id"],
                    "before_content": case_data["original_content"],
                    "after_content": processed_content,
                    "applied_rules": applied_rules,
                    "metadata": metadata
                }
                
            except Exception as e:
                logger.error(f"Failed to process case {case_data['case_id']}: {e}")
                raise
    
    async def _execute_batch_evaluation(self, batch_job: BatchJob) -> Dict[str, Any]:
        """배치 평가 실행"""
        start_time = datetime.now()
        
        try:
            # 이전 단계에서 처리된 케이스들 가져오기 (실제로는 상태 관리 필요)
            processed_cases = []  # 실제 구현에서는 배치 상태에서 가져옴
            
            # 비용 추정
            estimated_cost = await self.openai_service.estimate_batch_cost(processed_cases)
            
            logger.info(f"Starting batch evaluation for {len(processed_cases)} cases, estimated cost: ${estimated_cost:.2f}")
            
            # Batch API로 평가 실행
            evaluation_results = await self.openai_service.evaluate_batch_cases(processed_cases)
            
            # 결과 집계
            metrics_summary = self._aggregate_batch_metrics(evaluation_results)
            failure_analysis = self._analyze_batch_failures(evaluation_results)
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "step": "batch_evaluation",
                "status": "completed",
                "evaluated_count": len(evaluation_results),
                "estimated_cost": estimated_cost,
                "metrics_summary": metrics_summary,
                "failure_analysis": failure_analysis,
                "duration_ms": duration_ms,
                "evaluation_results": evaluation_results
            }
            
        except Exception as e:
            logger.error(f"Batch evaluation failed: {e}")
            return {
                "step": "batch_evaluation",
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_failure_clustering(self, batch_job: BatchJob) -> Dict[str, Any]:
        """실패 클러스터링 실행"""
        start_time = datetime.now()
        
        try:
            # 실패 패턴 수집
            failure_patterns = await result_repo.get_failure_patterns(self.current_rules_version)
            
            # 클러스터링 실행
            clusters = self._cluster_failure_patterns(failure_patterns)
            
            # 클러스터별 우선순위 계산
            prioritized_clusters = self._prioritize_clusters(clusters)
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "step": "failure_clustering",
                "status": "completed",
                "total_failures": len(failure_patterns),
                "cluster_count": len(clusters),
                "top_clusters": prioritized_clusters[:5],
                "duration_ms": duration_ms,
                "clusters": clusters
            }
            
        except Exception as e:
            logger.error(f"Failure clustering failed: {e}")
            return {
                "step": "failure_clustering",
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_auto_patching(self, batch_job: BatchJob) -> Dict[str, Any]:
        """자동 패치 실행"""
        start_time = datetime.now()
        
        try:
            # 이전 단계의 클러스터 정보 가져오기
            clusters = []  # 실제로는 이전 단계 결과에서 가져옴
            
            applied_patches = []
            skipped_patches = []
            
            for cluster in clusters[:3]:  # 상위 3개 클러스터만 처리
                # 오실레이션 검사
                rule_area = cluster.get("pattern_type", "unknown")
                if oscillation_prevention.check_oscillation(rule_area):
                    skipped_patches.append({
                        "cluster_id": cluster["cluster_id"],
                        "reason": "oscillation_prevention"
                    })
                    continue
                
                # 패치 제안 생성
                patch_suggestions = await self.auto_patcher.analyze_failures([cluster])
                
                for suggestion in patch_suggestions:
                    if suggestion.get("confidence_score", 0) >= 0.7:  # 높은 신뢰도만
                        # 패치 적용
                        await self._apply_patch_with_validation(suggestion)
                        applied_patches.append(suggestion)
                        
                        # 오실레이션 추적
                        oscillation_prevention.track_change(rule_area)
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "step": "auto_patching",
                "status": "completed",
                "applied_patches": len(applied_patches),
                "skipped_patches": len(skipped_patches),
                "patch_details": applied_patches,
                "skipped_details": skipped_patches,
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            logger.error(f"Auto patching failed: {e}")
            return {
                "step": "auto_patching",
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_safety_gates(self, batch_job: BatchJob) -> Dict[str, Any]:
        """안전 게이트 실행"""
        start_time = datetime.now()
        
        try:
            # 현재 규칙으로 게이트 실행
            current_rules = await self._get_current_rules()
            gate_results = await safety_gate_manager.run_all_gates(
                self.current_rules_version,
                current_rules["rules_content"]
            )
            
            all_gates_passed = all(result.passed for result in gate_results)
            
            # 게이트 결과 저장
            await safety_gate_manager.save_gate_results(self.current_rules_version, gate_results)
            
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            return {
                "step": "safety_gates",
                "status": "completed",
                "gates_passed": all_gates_passed,
                "gate_results": [
                    {
                        "gate_type": result.gate_type.value,
                        "passed": result.passed,
                        "score": result.score,
                        "error": result.error_message
                    }
                    for result in gate_results
                ],
                "duration_ms": duration_ms
            }
            
        except Exception as e:
            logger.error(f"Safety gates execution failed: {e}")
            return {
                "step": "safety_gates",
                "status": "failed",
                "error": str(e)
            }
    
    async def _execute_revalidation(self, batch_job: BatchJob) -> Dict[str, Any]:
        """재검증 실행"""
        start_time = datetime.now()
        
        try:
            # 동일한 샘플로 재검증
            revalidation_result = await self._execute_preprocessing_batch(batch_job)
            
            if revalidation_result["status"] == "completed":
                # 개선 정도 측정
                improvement_metrics = self._calculate_improvement_metrics(
                    revalidation_result.get("processed_cases", [])
                )
                
                # 유의미한 개선인지 확인
                is_significant_improvement = self._is_significant_improvement(improvement_metrics)
                
                if is_significant_improvement:
                    self.no_improvement_count = 0
                    next_sample_size = min(batch_job.sample_size * 2, 5000)  # 다음 규모로 확대
                else:
                    self.no_improvement_count += 1
                    next_sample_size = batch_job.sample_size
                
                end_time = datetime.now()
                duration_ms = int((end_time - start_time).total_seconds() * 1000)
                
                return {
                    "step": "revalidation",
                    "status": "completed",
                    "improvement_metrics": improvement_metrics,
                    "is_significant_improvement": is_significant_improvement,
                    "next_sample_size": next_sample_size,
                    "no_improvement_count": self.no_improvement_count,
                    "duration_ms": duration_ms
                }
            else:
                return revalidation_result
                
        except Exception as e:
            logger.error(f"Revalidation failed: {e}")
            return {
                "step": "revalidation",
                "status": "failed",
                "error": str(e)
            }
    
    async def _analyze_cycle_result(self, cycle_result: Dict[str, Any]) -> Dict[str, str]:
        """사이클 결과 분석 및 다음 액션 결정"""
        
        if cycle_result["status"] == "failed":
            return {"action": "retry", "reason": "cycle_failed"}
        
        # 재검증 결과 확인
        revalidation = next(
            (step for step in cycle_result["steps"] if step.get("step") == "revalidation"),
            None
        )
        
        if not revalidation:
            return {"action": "retry", "reason": "revalidation_missing"}
        
        # 연속 개선 없음 확인
        if self.no_improvement_count >= 3:
            return {
                "action": "stabilized",
                "reason": f"no_significant_improvement_for_{self.no_improvement_count}_cycles"
            }
        
        # 다음 규모로 확대
        if revalidation.get("is_significant_improvement", False):
            return {
                "action": "scale_up",
                "reason": "significant_improvement_detected",
                "next_sample_size": revalidation.get("next_sample_size", 1000)
            }
        
        # 동일 규모로 재시도
        return {
            "action": "retry_same_scale",
            "reason": "minor_improvement_continue_optimization"
        }
    
    def _calculate_sample_diversity(self, cases: List[Dict[str, Any]]) -> float:
        """샘플 다양성 계산"""
        if not cases:
            return 0.0
        
        # 간단한 다양성 점수 (실제로는 더 복잡한 계산)
        court_types = set(case.get("court_type") for case in cases)
        case_types = set(case.get("case_type") for case in cases)
        years = set(case.get("year") for case in cases)
        
        diversity_score = (len(court_types) + len(case_types) + len(years)) / 15  # 정규화
        return min(diversity_score, 1.0)
    
    def _analyze_sample_distribution(self, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """샘플 분포 분석"""
        from collections import Counter
        
        return {
            "court_types": dict(Counter(case.get("court_type") for case in cases)),
            "case_types": dict(Counter(case.get("case_type") for case in cases)),
            "years": dict(Counter(case.get("year") for case in cases)),
            "total_cases": len(cases)
        }
    
    def _aggregate_batch_metrics(self, evaluation_results: List[Tuple]) -> Dict[str, float]:
        """배치 메트릭 집계"""
        if not evaluation_results:
            return {}
        
        metrics_list = [result[1] for result in evaluation_results]  # QualityMetrics 객체들
        
        return {
            "avg_nrr": sum(m.nrr for m in metrics_list) / len(metrics_list),
            "avg_fpr": sum(m.fpr for m in metrics_list) / len(metrics_list),
            "avg_ss": sum(m.ss for m in metrics_list) / len(metrics_list),
            "avg_token_reduction": sum(m.token_reduction for m in metrics_list) / len(metrics_list),
            "total_parsing_errors": sum(m.parsing_errors for m in metrics_list)
        }
    
    def _analyze_batch_failures(self, evaluation_results: List[Tuple]) -> Dict[str, Any]:
        """배치 실패 분석"""
        failure_count = 0
        error_patterns = {}
        
        for case_id, metrics, errors, suggestions in evaluation_results:
            if errors:
                failure_count += 1
                for error in errors:
                    error_patterns[error] = error_patterns.get(error, 0) + 1
        
        return {
            "failure_count": failure_count,
            "failure_rate": failure_count / len(evaluation_results) if evaluation_results else 0,
            "top_error_patterns": dict(sorted(error_patterns.items(), key=lambda x: x[1], reverse=True)[:5])
        }
    
    def _cluster_failure_patterns(self, failure_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """실패 패턴 클러스터링"""
        # 간단한 클러스터링 (실제로는 더 정교한 알고리즘 사용)
        clusters = []
        
        for i, pattern in enumerate(failure_patterns):
            cluster = FailureCluster(
                cluster_id=f"cluster_{i}",
                pattern_type=self._classify_pattern_type(pattern["_id"]),
                failure_count=pattern["count"],
                sample_cases=pattern.get("sample_cases", []),
                error_pattern=pattern["_id"]
            )
            clusters.append(cluster.dict())
        
        return clusters
    
    def _classify_pattern_type(self, error_message: str) -> str:
        """패턴 유형 분류"""
        if "페이지" in error_message or "page" in error_message:
            return "page_number"
        elif "구분선" in error_message or "separator" in error_message:
            return "separator"
        elif "참조" in error_message or "reference" in error_message:
            return "reference"
        elif "공백" in error_message or "whitespace" in error_message:
            return "whitespace"
        else:
            return "unknown"
    
    def _prioritize_clusters(self, clusters: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """클러스터 우선순위 계산"""
        # 실패 횟수 기준으로 정렬
        return sorted(clusters, key=lambda x: x["failure_count"], reverse=True)
    
    async def _apply_patch_with_validation(self, suggestion: Dict[str, Any]):
        """검증과 함께 패치 적용"""
        try:
            # 현재 규칙 가져오기
            current_rules = await self._get_current_rules()
            
            # 패치 적용
            updated_rules = self.auto_patcher.apply_patch(
                suggestion, current_rules["rules_content"]
            )
            
            # 새 버전 생성
            new_version = self.version_manager.increment_version("patch")
            self.current_rules_version = new_version
            
            # DSL 엔진 업데이트
            self.dsl_engine.load_rules_from_dsl(updated_rules)
            
            logger.info(f"Applied patch {suggestion['patch_id']}, new version: {new_version}")
            
        except Exception as e:
            logger.error(f"Failed to apply patch with validation: {e}")
            raise
    
    async def _get_current_rules(self) -> Dict[str, Any]:
        """현재 규칙 가져오기"""
        # 실제로는 데이터베이스에서 로드
        return {
            "version": self.current_rules_version,
            "rules_content": self._get_default_rules()
        }
    
    def _get_default_rules(self) -> str:
        """기본 규칙 반환"""
        default_rules = {
            "rules": [
                {
                    "rule_id": "page_number_001",
                    "rule_type": "page_number_removal",
                    "pattern": r"(?:^|\n)\s*(?:페이지|page)\s*\d+\s*(?:\n|$)",
                    "replacement": "\n",
                    "description": "페이지번호 제거",
                    "priority": 100,
                    "enabled": True
                },
                {
                    "rule_id": "separator_001",
                    "rule_type": "separator_removal", 
                    "pattern": r"(?:^|\n)\s*[-=]{3,}\s*(?:\n|$)",
                    "replacement": "\n",
                    "description": "구분선 제거",
                    "priority": 90,
                    "enabled": True
                }
            ]
        }
        
        import json
        return json.dumps(default_rules, indent=2, ensure_ascii=False)
    
    def _calculate_improvement_metrics(self, processed_cases: List[Dict[str, Any]]) -> Dict[str, float]:
        """개선 지표 계산"""
        # 간단한 개선 지표 (실제로는 이전 버전과 비교)
        return {
            "quality_improvement": 0.05,  # 5% 개선
            "error_reduction": 0.10,      # 10% 오류 감소
            "processing_speed_improvement": 0.02  # 2% 속도 개선
        }
    
    def _is_significant_improvement(self, improvement_metrics: Dict[str, float]) -> bool:
        """유의미한 개선인지 확인"""
        # 임계값 기준으로 판단
        return (
            improvement_metrics.get("quality_improvement", 0) >= 0.03 or
            improvement_metrics.get("error_reduction", 0) >= 0.05
        )
