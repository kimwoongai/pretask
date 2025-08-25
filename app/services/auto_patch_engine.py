"""
자동 패치 엔진
AI 제안을 DSL 규칙 패치로 변환하고 적용
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging
from dataclasses import dataclass

from app.services.dsl_rules import DSLRule, dsl_manager
from app.services.openai_service import OpenAIService

logger = logging.getLogger(__name__)

@dataclass
class PatchSuggestion:
    """패치 제안 데이터 구조"""
    suggestion_id: str
    description: str
    confidence_score: float
    rule_type: str  # 'regex_improvement', 'new_pattern', 'filter_enhancement'
    estimated_improvement: str
    applicable_cases: List[str]
    pattern_before: Optional[str] = None
    pattern_after: Optional[str] = None
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class AutoPatchEngine:
    """자동 패치 엔진"""
    
    def __init__(self):
        self.openai_service = None
        self.patch_history: List[Dict[str, Any]] = []
        self.performance_threshold = 0.5  # 최소 신뢰도 점수 (AI 제안 모두 신뢰)
        
    def _init_openai_service(self):
        """OpenAI 서비스 초기화 (지연 로딩)"""
        if self.openai_service is None:
            try:
                self.openai_service = OpenAIService()
            except Exception as e:
                logger.error(f"OpenAI 서비스 초기화 실패: {e}")
                raise
    
    def analyze_suggestions(self, suggestions: List[Dict[str, Any]], 
                          quality_metrics: Dict[str, float],
                          case_content: str) -> List[PatchSuggestion]:
        """AI 제안을 분석하여 패치 제안으로 변환"""
        patch_suggestions = []
        
        for i, suggestion in enumerate(suggestions):
            try:
                # 기본 정보 추출
                description = suggestion.get('description', '')
                confidence = suggestion.get('confidence_score', 0.5)
                rule_type = suggestion.get('rule_type', 'regex_improvement')
                estimated_improvement = suggestion.get('estimated_improvement', '')
                applicable_cases = suggestion.get('applicable_cases', ['general'])
                pattern_before = suggestion.get('pattern_before', '')
                pattern_after = suggestion.get('pattern_after', '')
                
                # 중복 규칙 확인 (추가된 부분)
                if self._is_duplicate_pattern(pattern_before, rule_type):
                    print(f"🔧 DEBUG: 패치 제안 제외: 중복 패턴 발견 - {description}")
                    logger.info(f"패치 제안 제외: 중복 패턴 - {description}")
                    continue
                
                # 패치 제안 생성
                patch = PatchSuggestion(
                    suggestion_id=f"patch_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}",
                    description=description,
                    confidence_score=confidence,
                    rule_type=rule_type,
                    estimated_improvement=estimated_improvement,
                    applicable_cases=applicable_cases,
                    pattern_before=pattern_before,
                    pattern_after=pattern_after
                )
                
                # 신뢰도 기준 필터링
                if confidence >= self.performance_threshold:
                    patch_suggestions.append(patch)
                    print(f"🔧 DEBUG: 패치 제안 생성: {patch.suggestion_id} (신뢰도: {confidence})")
                    logger.info(f"패치 제안 생성: {patch.suggestion_id} (신뢰도: {confidence})")
                else:
                    print(f"🔧 DEBUG: 패치 제안 제외: 신뢰도 부족 ({confidence} < {self.performance_threshold})")
                    logger.debug(f"패치 제안 제외: 신뢰도 부족 ({confidence} < {self.performance_threshold})")
                    
            except Exception as e:
                logger.error(f"패치 제안 분석 오류: {e}")
        
        return patch_suggestions
    
    def _is_duplicate_pattern(self, pattern: str, rule_type: str) -> bool:
        """제안된 패턴이 기존 규칙과 중복되는지 확인"""
        try:
            from app.services.dsl_rules import dsl_manager
            
            # 현재 활성화된 규칙들 가져오기
            existing_rules = dsl_manager.get_sorted_rules()
            
            for existing_rule in existing_rules:
                # 동일한 규칙 타입만 비교
                if existing_rule.rule_type != rule_type:
                    continue
                
                # 패턴 유사도 확인
                if self._calculate_pattern_similarity(pattern, existing_rule.pattern) > 0.8:
                    print(f"🔧 DEBUG: 중복 패턴 발견 - 기존: {existing_rule.rule_id}")
                    print(f"🔧 DEBUG: 기존 패턴: {existing_rule.pattern[:100]}...")
                    print(f"🔧 DEBUG: 새 패턴: {pattern[:100]}...")
                    return True
            
            return False
            
        except Exception as e:
            logger.warning(f"중복 패턴 확인 실패: {e}")
            return False
    
    def _calculate_pattern_similarity(self, pattern1: str, pattern2: str) -> float:
        """두 정규식 패턴의 유사도를 계산 (0.0 ~ 1.0)"""
        try:
            # 정규식 특수문자 제거하고 핵심 키워드 추출
            import re
            
            # 기본적인 정규식 메타문자 제거
            clean_pattern1 = re.sub(r'[(){}[\]\\^$.*+?|]', ' ', pattern1.lower())
            clean_pattern2 = re.sub(r'[(){}[\]\\^$.*+?|]', ' ', pattern2.lower())
            
            # 공백으로 분할하여 키워드 추출
            keywords1 = set(word for word in clean_pattern1.split() if len(word) > 1)
            keywords2 = set(word for word in clean_pattern2.split() if len(word) > 1)
            
            if not keywords1 or not keywords2:
                return 0.0
            
            # Jaccard 유사도 계산
            intersection = len(keywords1.intersection(keywords2))
            union = len(keywords1.union(keywords2))
            
            similarity = intersection / union if union > 0 else 0.0
            
            print(f"🔧 DEBUG: 패턴 유사도 계산 - {similarity:.2f}")
            print(f"🔧 DEBUG: 키워드1: {keywords1}")
            print(f"🔧 DEBUG: 키워드2: {keywords2}")
            
            return similarity
            
        except Exception as e:
            logger.warning(f"패턴 유사도 계산 실패: {e}")
            return 0.0
    
    def generate_enhanced_suggestions(self, original_content: str, 
                                    processed_content: str,
                                    quality_metrics: Dict[str, float]) -> List[PatchSuggestion]:
        """AI를 사용하여 고급 패치 제안 생성"""
        try:
            self._init_openai_service()
            
            # 고급 제안 요청 프롬프트
            enhancement_prompt = self._create_enhancement_prompt(
                original_content, processed_content, quality_metrics
            )
            
            # OpenAI API 호출
            response = self.openai_service._make_api_call(enhancement_prompt)
            
            # 응답 파싱
            suggestions_data = self._parse_enhancement_response(response)
            
            # 패치 제안으로 변환
            patch_suggestions = []
            for suggestion in suggestions_data:
                patch = PatchSuggestion(
                    suggestion_id=f"enhanced_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(patch_suggestions)}",
                    description=suggestion.get('description', ''),
                    confidence_score=suggestion.get('confidence', 0.8),
                    rule_type=suggestion.get('type', 'regex_improvement'),
                    estimated_improvement=suggestion.get('improvement', ''),
                    applicable_cases=suggestion.get('cases', ['general']),
                    pattern_before=suggestion.get('before', ''),
                    pattern_after=suggestion.get('after', '')
                )
                patch_suggestions.append(patch)
            
            logger.info(f"고급 패치 제안 생성 완료: {len(patch_suggestions)}개")
            return patch_suggestions
            
        except Exception as e:
            logger.error(f"고급 패치 제안 생성 실패: {e}")
            return []
    
    def _create_enhancement_prompt(self, original: str, processed: str, 
                                 metrics: Dict[str, float]) -> str:
        """고급 제안 생성을 위한 프롬프트 생성"""
        return f"""
다음 법률 문서 전처리 결과를 분석하고 개선 방안을 제시해주세요.

**현재 성능 지표:**
- NRR (노이즈 제거율): {metrics.get('nrr', 0):.2f}
- ICR (중요 내용 보존율): {metrics.get('icr', 0):.2f}  
- SS (의미 유사성): {metrics.get('ss', 0):.2f}
- 토큰 절감률: {metrics.get('token_reduction', 0):.1f}%

**원본 문서 (처음 1000자):**
{original[:1000]}...

**전처리 결과 (처음 1000자):**
{processed[:1000]}...

**개선 방향:**
1. NRR < 0.8인 경우: 더 많은 노이즈 패턴 식별 필요
2. ICR < 0.9인 경우: 중요 사실 보존 규칙 강화 필요  
3. 토큰 절감률 < 20%인 경우: 더 공격적인 압축 필요

다음 JSON 형식으로 구체적인 개선 제안을 해주세요:

{{
  "suggestions": [
    {{
      "description": "구체적인 개선 내용",
      "type": "noise_removal|fact_extraction|legal_filtering",
      "confidence": 0.85,
      "improvement": "예상 개선 효과",
      "cases": ["민사", "형사", "행정"],
      "before": "현재 패턴 (정규식)",
      "after": "개선된 패턴 (정규식)"
    }}
  ]
}}
"""
    
    def _parse_enhancement_response(self, response: str) -> List[Dict[str, Any]]:
        """고급 제안 응답 파싱"""
        try:
            # JSON 추출
            json_text = response
            if "```json" in response:
                start = response.find("```json") + 7
                end = response.find("```", start)
                if end != -1:
                    json_text = response[start:end].strip()
            elif "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_text = response[start:end].strip()
            
            data = json.loads(json_text)
            return data.get('suggestions', [])
            
        except Exception as e:
            logger.error(f"고급 제안 응답 파싱 실패: {e}")
            return []
    
    def apply_patch(self, patch: PatchSuggestion) -> Tuple[bool, str]:
        """패치를 DSL 규칙으로 적용"""
        try:
            print(f"🔧 DEBUG: 패치 적용 시도 - ID: {patch.suggestion_id}, Type: {patch.rule_type}")
            print(f"🔧 DEBUG: Pattern Before: {patch.pattern_before}")
            print(f"🔧 DEBUG: Pattern After: {patch.pattern_after}")
            
            # 패치 타입에 따른 규칙 생성
            if patch.rule_type == 'regex_improvement':
                success = self._apply_regex_improvement(patch)
            elif patch.rule_type == 'new_pattern':
                success = self._apply_new_pattern(patch)
            elif patch.rule_type == 'filter_enhancement':
                success = self._apply_filter_enhancement(patch)
            elif patch.rule_type in ['legal_filtering', 'noise_removal', 'redundancy_removal']:
                success = self._apply_ai_rule(patch)
            else:
                success = self._apply_generic_patch(patch)
            
            if success:
                # 패치 히스토리 기록
                self.patch_history.append({
                    'patch_id': patch.suggestion_id,
                    'description': patch.description,
                    'applied_at': datetime.now().isoformat(),
                    'confidence': patch.confidence_score,
                    'rule_type': patch.rule_type
                })
                
                message = f"패치 적용 성공: {patch.suggestion_id}"
                logger.info(message)
                return True, message
            else:
                message = f"패치 적용 실패: {patch.suggestion_id}"
                logger.error(message)
                return False, message
                
        except Exception as e:
            message = f"패치 적용 중 오류: {str(e)}"
            logger.error(message)
            return False, message
    
    def _apply_regex_improvement(self, patch: PatchSuggestion) -> bool:
        """정규식 개선 패치 적용"""
        try:
            # 기존 규칙 찾기 (패턴 기반)
            existing_rule = None
            for rule in dsl_manager.rules.values():
                if rule.pattern == patch.pattern_before:
                    existing_rule = rule
                    break
            
            if existing_rule:
                # 기존 규칙 업데이트
                return dsl_manager.update_rule(
                    existing_rule.rule_id,
                    pattern=patch.pattern_after,
                    description=f"{existing_rule.description} (AI 개선)",
                    performance_score=patch.confidence_score
                )
            else:
                # 새 규칙 생성
                new_rule = DSLRule(
                    rule_id=f"ai_improved_{patch.suggestion_id}",
                    rule_type="noise_removal",
                    pattern=patch.pattern_after,
                    replacement="",
                    priority=60,
                    description=f"AI 제안: {patch.description}",
                    performance_score=patch.confidence_score
                )
                return dsl_manager.add_rule(new_rule)
                
        except Exception as e:
            logger.error(f"정규식 개선 패치 적용 오류: {e}")
            return False
    
    def _apply_new_pattern(self, patch: PatchSuggestion) -> bool:
        """새 패턴 패치 적용"""
        try:
            new_rule = DSLRule(
                rule_id=f"ai_new_{patch.suggestion_id}",
                rule_type="noise_removal",
                pattern=patch.pattern_after,
                replacement="",
                priority=50,
                description=f"AI 신규: {patch.description}",
                performance_score=patch.confidence_score
            )
            return dsl_manager.add_rule(new_rule)
            
        except Exception as e:
            logger.error(f"새 패턴 패치 적용 오류: {e}")
            return False
    
    def _apply_filter_enhancement(self, patch: PatchSuggestion) -> bool:
        """필터 강화 패치 적용"""
        try:
            new_rule = DSLRule(
                rule_id=f"ai_filter_{patch.suggestion_id}",
                rule_type="legal_filtering",
                pattern=patch.pattern_after,
                replacement="",
                priority=70,
                description=f"AI 필터: {patch.description}",
                performance_score=patch.confidence_score
            )
            return dsl_manager.add_rule(new_rule)
            
        except Exception as e:
            logger.error(f"필터 강화 패치 적용 오류: {e}")
            return False
    
    def _apply_generic_patch(self, patch: PatchSuggestion) -> bool:
        """일반 패치 적용"""
        try:
            new_rule = DSLRule(
                rule_id=f"ai_generic_{patch.suggestion_id}",
                rule_type="noise_removal",
                pattern=patch.pattern_after if patch.pattern_after else patch.pattern_before,
                replacement="",
                priority=40,
                description=f"AI 일반: {patch.description}",
                performance_score=patch.confidence_score
            )
            return dsl_manager.add_rule(new_rule)
            
        except Exception as e:
            logger.error(f"일반 패치 적용 오류: {e}")
            return False
    
    def _apply_ai_rule(self, patch: PatchSuggestion) -> bool:
        """AI 제안 규칙 적용"""
        try:
            print(f"🔧 DEBUG: AI 규칙 적용 - {patch.description}")
            
            # AI 제안에 맞는 DSL 규칙 생성
            new_rule = DSLRule(
                rule_id=f"ai_{patch.rule_type}_{patch.suggestion_id}",
                rule_type=patch.rule_type,
                pattern=patch.pattern_before,  # AI가 제거하려는 패턴
                replacement=patch.pattern_after,  # 대체할 내용 (보통 빈 문자열)
                priority=80,  # 높은 우선순위
                description=f"AI 제안: {patch.description}",
                performance_score=patch.confidence_score
            )
            
            result = dsl_manager.add_rule(new_rule)
            print(f"🔧 DEBUG: DSL 규칙 추가 결과: {result}")
            return result
            
        except Exception as e:
            print(f"🔧 ERROR: AI 규칙 적용 오류: {e}")
            logger.error(f"AI 규칙 적용 오류: {e}")
            return False
    
    def auto_apply_patches(self, patches: List[PatchSuggestion], 
                          auto_apply_threshold: float = 0.5) -> Dict[str, Any]:
        """자동 패치 적용 (신뢰도 기준)"""
        results = {
            'total_patches': len(patches),
            'auto_applied': 0,
            'manual_review': 0,
            'failed': 0,
            'applied_patches': [],
            'review_required': [],
            'failed_patches': []
        }
        
        for patch in patches:
            if patch.confidence_score >= auto_apply_threshold:
                # 자동 적용
                success, message = self.apply_patch(patch)
                if success:
                    results['auto_applied'] += 1
                    results['applied_patches'].append({
                        'patch_id': patch.suggestion_id,
                        'description': patch.description,
                        'confidence': patch.confidence_score
                    })
                else:
                    results['failed'] += 1
                    results['failed_patches'].append({
                        'patch_id': patch.suggestion_id,
                        'error': message
                    })
            else:
                # 수동 검토 필요
                results['manual_review'] += 1
                results['review_required'].append({
                    'patch_id': patch.suggestion_id,
                    'description': patch.description,
                    'confidence': patch.confidence_score,
                    'reason': f'신뢰도 부족 ({patch.confidence_score} < {auto_apply_threshold})'
                })
        
        logger.info(f"자동 패치 적용 완료: 적용 {results['auto_applied']}개, "
                   f"검토 {results['manual_review']}개, 실패 {results['failed']}개")
        
        return results
    
    def rollback_patch(self, patch_id: str) -> Tuple[bool, str]:
        """패치 롤백"""
        try:
            # 패치 히스토리에서 찾기
            patch_record = None
            for record in self.patch_history:
                if record['patch_id'] == patch_id:
                    patch_record = record
                    break
            
            if not patch_record:
                return False, f"패치 기록을 찾을 수 없습니다: {patch_id}"
            
            # 관련 규칙 찾기 및 비활성화
            rule_id = f"ai_{patch_record['rule_type']}_{patch_id}"
            if rule_id in dsl_manager.rules:
                success = dsl_manager.disable_rule(rule_id)
                if success:
                    message = f"패치 롤백 성공: {patch_id}"
                    logger.info(message)
                    return True, message
                else:
                    return False, f"규칙 비활성화 실패: {rule_id}"
            else:
                return False, f"관련 규칙을 찾을 수 없습니다: {rule_id}"
                
        except Exception as e:
            message = f"패치 롤백 오류: {str(e)}"
            logger.error(message)
            return False, message
    
    def get_patch_history(self) -> List[Dict[str, Any]]:
        """패치 히스토리 조회"""
        return self.patch_history.copy()
    
    def get_performance_impact(self, patch_id: str) -> Dict[str, Any]:
        """패치 성능 영향 분석"""
        # 실제 구현에서는 A/B 테스트 결과를 분석
        return {
            'patch_id': patch_id,
            'before_metrics': {},
            'after_metrics': {},
            'improvement': {},
            'status': 'monitoring'
        }


# 전역 인스턴스
auto_patch_engine = AutoPatchEngine()
