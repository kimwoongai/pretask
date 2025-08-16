"""
단건 점검 모드 (Shakedown) 처리기
"""
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

from app.models.document import (
    DocumentCase, ProcessingResult, QualityMetrics, 
    ProcessingStatus, RulePatch
)
from app.core.config import settings, processing_mode, quality_gates
from app.core.database import document_repo, result_repo, cache_manager
from app.services.rules_engine import DSLEngine, AutoPatcher, RulesVersionManager
from app.services.openai_service import OpenAIService
from app.services.safety_gates import safety_gate_manager

logger = logging.getLogger(__name__)


class SingleRunProcessor:
    """단건 점검 처리기"""
    
    def __init__(self):
        self.dsl_engine = DSLEngine()
        self.auto_patcher = AutoPatcher(self.dsl_engine)
        self.openai_service = OpenAIService()
        self.version_manager = RulesVersionManager()
        self.consecutive_passes = 0
        self.current_rules_version = "v1.0.0"
    
    async def process_single_case(self, case_id: str) -> Dict[str, Any]:
        """단일 케이스 처리"""
        try:
            logger.info(f"Starting single case processing for case_id: {case_id}")
            
            # 케이스 로드
            case_data = await document_repo.get_case(case_id)
            if not case_data:
                raise ValueError(f"Case {case_id} not found")
            
            # 케이스 상태 업데이트
            await document_repo.update_case(case_id, {
                "status": ProcessingStatus.IN_PROGRESS.value,
                "updated_at": datetime.now()
            })
            
            # 캐시 확인
            cached_result = await cache_manager.get_evaluation_cache(
                case_id, self.current_rules_version
            )
            
            if cached_result:
                logger.info(f"Using cached result for case {case_id}")
                return cached_result
            
            # 전처리 실행
            processing_result = await self._execute_preprocessing(case_data)
            
            # GPT-5 평가
            evaluation_result = await self._evaluate_with_gpt(processing_result)
            
            # 품질 게이트 확인
            gate_result = await self._check_quality_gates(evaluation_result)
            
            # 결과 처리
            final_result = await self._handle_processing_result(
                case_id, processing_result, evaluation_result, gate_result
            )
            
            # 캐시 저장
            await cache_manager.set_evaluation_cache(
                case_id, self.current_rules_version, final_result
            )
            
            logger.info(f"Completed single case processing for case_id: {case_id}")
            return final_result
            
        except Exception as e:
            logger.error(f"Failed to process case {case_id}: {e}")
            
            # 실패 상태 업데이트
            await document_repo.update_case(case_id, {
                "status": ProcessingStatus.FAILED.value,
                "updated_at": datetime.now()
            })
            
            raise
    
    async def _execute_preprocessing(self, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """전처리 실행"""
        start_time = datetime.now()
        
        # 현재 규칙 로드
        latest_rules = await self._get_current_rules()
        self.dsl_engine.load_rules_from_dsl(latest_rules["rules_content"])
        
        # 케이스 메타데이터 준비
        metadata = {
            "court_type": case_data.get("court_type"),
            "case_type": case_data.get("case_type"),
            "year": case_data.get("year"),
            "format_type": case_data.get("format_type")
        }
        
        # 규칙 적용
        original_content = case_data["original_content"]
        processed_content, applied_rules = self.dsl_engine.apply_rules(
            original_content, metadata
        )
        
        end_time = datetime.now()
        processing_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # 토큰 수 계산
        token_count_before = self.openai_service.calculate_token_count(original_content)
        token_count_after = self.openai_service.calculate_token_count(processed_content)
        
        return {
            "case_id": case_data["case_id"],
            "rules_version": self.current_rules_version,
            "before_content": original_content,
            "after_content": processed_content,
            "applied_rules": applied_rules,
            "processing_time_ms": processing_time_ms,
            "token_count_before": int(token_count_before),
            "token_count_after": int(token_count_after),
            "metadata": metadata
        }
    
    async def _evaluate_with_gpt(self, processing_result: Dict[str, Any]) -> Dict[str, Any]:
        """GPT-5 평가"""
        logger.info(f"Evaluating case {processing_result['case_id']} with GPT")
        
        metrics, errors, suggestions = await self.openai_service.evaluate_single_case(
            processing_result["before_content"],
            processing_result["after_content"],
            processing_result["metadata"]
        )
        
        # Diff 요약 생성
        diff_summary = self._generate_diff_summary(
            processing_result["before_content"],
            processing_result["after_content"]
        )
        
        return {
            **processing_result,
            "metrics": metrics,
            "errors": errors,
            "suggestions": suggestions,
            "diff_summary": diff_summary
        }
    
    async def _check_quality_gates(self, evaluation_result: Dict[str, Any]) -> Dict[str, Any]:
        """품질 게이트 확인"""
        metrics = evaluation_result["metrics"]
        
        # 품질 지표 확인
        quality_check = quality_gates.check_quality_metrics(metrics.dict())
        is_passing = quality_gates.is_passing(metrics.dict())
        
        if not is_passing:
            failing_metrics = quality_gates.get_failing_metrics(metrics.dict())
            logger.warning(f"Quality gate failed for case {evaluation_result['case_id']}: {failing_metrics}")
        
        return {
            "passed": is_passing,
            "quality_checks": quality_check,
            "failing_metrics": failing_metrics if not is_passing else {}
        }
    
    async def _handle_processing_result(
        self, 
        case_id: str, 
        processing_result: Dict[str, Any], 
        evaluation_result: Dict[str, Any],
        gate_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """처리 결과 핸들링"""
        
        # 결과 저장
        result_data = ProcessingResult(
            case_id=case_id,
            rules_version=self.current_rules_version,
            metrics=evaluation_result["metrics"],
            before_content=processing_result["before_content"],
            after_content=processing_result["after_content"],
            diff_summary=evaluation_result["diff_summary"],
            processing_time_ms=processing_result["processing_time_ms"],
            token_count_before=processing_result["token_count_before"],
            token_count_after=processing_result["token_count_after"],
            errors=evaluation_result["errors"],
            warnings=[]
        )
        
        await result_repo.save_result(result_data.dict())
        
        # 결과에 따른 처리
        if gate_result["passed"]:
            await self._handle_success(case_id, evaluation_result)
        else:
            await self._handle_failure(case_id, evaluation_result, gate_result)
        
        return {
            "case_id": case_id,
            "status": "completed",
            "passed": gate_result["passed"],
            "metrics": evaluation_result["metrics"].dict(),
            "diff_summary": evaluation_result["diff_summary"],
            "errors": evaluation_result["errors"],
            "suggestions": evaluation_result["suggestions"],
            "quality_gates": gate_result,
            "applied_rules": processing_result["applied_rules"],
            "processing_time_ms": processing_result["processing_time_ms"],
            "token_reduction": self._calculate_token_reduction(
                processing_result["token_count_before"],
                processing_result["token_count_after"]
            )
        }
    
    async def _handle_success(self, case_id: str, evaluation_result: Dict[str, Any]):
        """성공 처리"""
        self.consecutive_passes += 1
        
        # 케이스 상태 업데이트
        await document_repo.update_case(case_id, {
            "status": ProcessingStatus.COMPLETED.value,
            "processed_content": evaluation_result["after_content"],
            "updated_at": datetime.now()
        })
        
        logger.info(f"Case {case_id} passed quality gates. Consecutive passes: {self.consecutive_passes}")
        
        # 연속 20건 합격 시 Batch 모드로 승급 제안
        if self.consecutive_passes >= 20:
            logger.info("20 consecutive passes achieved. Ready for Batch mode upgrade.")
            # 실제로는 알림 시스템이나 상태 플래그 설정
    
    async def _handle_failure(
        self, 
        case_id: str, 
        evaluation_result: Dict[str, Any], 
        gate_result: Dict[str, Any]
    ):
        """실패 처리"""
        self.consecutive_passes = 0  # 연속 통과 카운터 리셋
        
        # 케이스 상태 업데이트
        await document_repo.update_case(case_id, {
            "status": ProcessingStatus.FAILED.value,
            "updated_at": datetime.now()
        })
        
        # 실패 스니펫을 회귀 테스트 세트에 추가
        await self._add_to_regression_test_set(case_id, evaluation_result)
        
        # 자동 패치가 활성화된 경우 패치 제안 생성
        if settings.auto_patch:
            await self._generate_auto_patch(case_id, evaluation_result)
    
    async def _add_to_regression_test_set(self, case_id: str, evaluation_result: Dict[str, Any]):
        """회귀 테스트 세트에 추가"""
        regression_case = {
            "case_id": case_id,
            "failure_type": "quality_gate_failure",
            "errors": evaluation_result["errors"],
            "metrics": evaluation_result["metrics"].dict(),
            "content_snippet": evaluation_result["after_content"][:500],
            "added_at": datetime.now()
        }
        
        # 회귀 테스트 컬렉션에 저장 (실제 구현에서)
        logger.info(f"Added case {case_id} to regression test set")
    
    async def _generate_auto_patch(self, case_id: str, evaluation_result: Dict[str, Any]):
        """자동 패치 생성"""
        try:
            # 실패 패턴 분석
            failure_patterns = [{
                "_id": f"failure_{case_id}",
                "count": 1,
                "sample_cases": [case_id],
                "errors": evaluation_result["errors"]
            }]
            
            # 패치 제안 생성
            patch_suggestions = await self.auto_patcher.analyze_failures(failure_patterns)
            
            for suggestion in patch_suggestions:
                # 오실레이션 검사
                rule_area = suggestion.get("rule_type", "unknown")
                if self.auto_patcher.check_oscillation(rule_area):
                    logger.warning(f"Skipping patch for {rule_area} due to oscillation prevention")
                    continue
                
                # 패치 적용
                await self._apply_patch_suggestion(suggestion)
                
        except Exception as e:
            logger.error(f"Failed to generate auto patch for case {case_id}: {e}")
    
    async def _apply_patch_suggestion(self, suggestion: Dict[str, Any]):
        """패치 제안 적용"""
        try:
            # 현재 규칙 가져오기
            current_rules = await self._get_current_rules()
            
            # 패치 적용
            updated_rules = self.auto_patcher.apply_patch(
                suggestion, current_rules["rules_content"]
            )
            
            # 안전 게이트 실행
            gate_results = await safety_gate_manager.run_all_gates(
                self.current_rules_version, updated_rules
            )
            
            all_gates_passed = all(result.passed for result in gate_results)
            
            if all_gates_passed:
                # 새 버전 생성
                new_version = self.version_manager.increment_version("patch")
                
                # 규칙 저장
                version_data = self.version_manager.create_version_tag(
                    updated_rules,
                    f"Auto patch: {suggestion['description']}"
                )
                
                # 데이터베이스에 저장 (실제 구현에서)
                self.current_rules_version = new_version
                
                logger.info(f"Applied patch {suggestion['patch_id']}, new version: {new_version}")
            else:
                logger.warning(f"Patch {suggestion['patch_id']} failed safety gates")
                
        except Exception as e:
            logger.error(f"Failed to apply patch suggestion: {e}")
    
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
                },
                {
                    "rule_id": "whitespace_001",
                    "rule_type": "whitespace_normalization",
                    "pattern": r"\s{2,}",
                    "replacement": " ",
                    "description": "공백 정규화",
                    "priority": 80,
                    "enabled": True
                }
            ]
        }
        
        import json
        return json.dumps(default_rules, indent=2, ensure_ascii=False)
    
    def _generate_diff_summary(self, before: str, after: str) -> str:
        """Diff 요약 생성"""
        before_lines = len(before.split('\n'))
        after_lines = len(after.split('\n'))
        
        before_chars = len(before)
        after_chars = len(after)
        
        return f"Lines: {before_lines} → {after_lines} ({after_lines - before_lines:+d}), " \
               f"Characters: {before_chars} → {after_chars} ({after_chars - before_chars:+d})"
    
    def _calculate_token_reduction(self, before_tokens: int, after_tokens: int) -> float:
        """토큰 절감률 계산"""
        if before_tokens == 0:
            return 0.0
        
        reduction = (before_tokens - after_tokens) / before_tokens * 100
        return round(reduction, 2)
    
    async def get_next_case_suggestion(self) -> Optional[str]:
        """다음 케이스 제안"""
        if not processing_mode.is_single_run_mode():
            return None
        
        # 처리되지 않은 케이스 중에서 다양성을 고려하여 선택
        # 실제로는 층화 샘플링 로직 구현
        return "next_case_id"
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """처리 통계"""
        return {
            "consecutive_passes": self.consecutive_passes,
            "current_rules_version": self.current_rules_version,
            "ready_for_batch_mode": self.consecutive_passes >= 20,
            "mode": "단건 점검 모드 (Shakedown)"
        }
