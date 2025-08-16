"""
OpenAI API 서비스
"""
import asyncio
import json
from typing import Dict, List, Any, Optional, Tuple
import openai
from app.core.config import settings
from app.models.document import QualityMetrics
import logging

logger = logging.getLogger(__name__)


class OpenAIService:
    """OpenAI API 서비스"""
    
    def __init__(self):
        self.client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
    
    async def evaluate_single_case(
        self, 
        before_content: str, 
        after_content: str, 
        case_metadata: Dict[str, Any]
    ) -> Tuple[QualityMetrics, List[str], str]:
        """단일 케이스 평가"""
        
        prompt = self._create_evaluation_prompt(before_content, after_content, case_metadata)
        
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 법률 문서 전처리 품질을 평가하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            result_text = response.choices[0].message.content
            logger.info(f"OpenAI raw response: {result_text}")
            return self._parse_evaluation_result(result_text, before_content, after_content)
            
        except Exception as e:
            logger.error(f"Failed to evaluate case: {e}")
            logger.error(f"OpenAI API key (first 20 chars): {settings.openai_api_key[:20] if settings.openai_api_key else 'None'}")
            logger.error(f"OpenAI model: {self.model}")
            import traceback
            logger.error(f"Full traceback: {traceback.format_exc()}")
            raise
    
    async def evaluate_batch_cases(
        self, 
        cases: List[Dict[str, Any]]
    ) -> List[Tuple[str, QualityMetrics, List[str], str]]:
        """배치 케이스 평가"""
        
        batch_requests = []
        
        for i, case in enumerate(cases):
            prompt = self._create_evaluation_prompt(
                case["before_content"], 
                case["after_content"], 
                case.get("metadata", {})
            )
            
            batch_requests.append({
                "custom_id": f"eval_{case['case_id']}_{i}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": "당신은 법률 문서 전처리 품질을 평가하는 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.1,
                    "max_tokens": 2000
                }
            })
        
        try:
            # Batch API 요청 생성
            batch_file = await self._create_batch_file(batch_requests)
            
            # Batch 작업 시작
            batch = await self.client.batches.create(
                input_file_id=batch_file.id,
                endpoint="/v1/chat/completions",
                completion_window="24h"
            )
            
            # 완료 대기
            batch_result = await self._wait_for_batch_completion(batch.id)
            
            # 결과 파싱
            return await self._parse_batch_results(batch_result, cases)
            
        except Exception as e:
            logger.error(f"Failed to evaluate batch cases: {e}")
            raise
    
    async def generate_improvement_suggestions(
        self, 
        failure_patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """개선 제안 생성"""
        
        suggestions = []
        
        for pattern in failure_patterns:
            prompt = self._create_improvement_prompt(pattern)
            
            try:
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "당신은 문서 전처리 규칙 개선 전문가입니다."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                
                suggestion_text = response.choices[0].message.content
                suggestion = self._parse_improvement_suggestion(suggestion_text, pattern)
                
                if suggestion:
                    suggestions.append(suggestion)
                    
            except Exception as e:
                logger.warning(f"Failed to generate suggestion for pattern: {e}")
                continue
        
        return suggestions
    
    def _create_evaluation_prompt(
        self, 
        before_content: str, 
        after_content: str, 
        metadata: Dict[str, Any]
    ) -> str:
        """평가 프롬프트 생성"""
        
        return f"""
다음 법률 문서의 전처리 결과를 평가해주세요.

**문서 정보:**
- 법원 유형: {metadata.get('court_type', 'N/A')}
- 사건 유형: {metadata.get('case_type', 'N/A')}
- 연도: {metadata.get('year', 'N/A')}

**전처리 전 내용 (처음 500자):**
{before_content[:500]}...

**전처리 후 내용 (처음 500자):**
{after_content[:500]}...

**평가 기준:**
1. NRR (Noise Reduction Rate): 불필요한 내용 제거 정도 (0-1)
2. FPR (False Positive Rate): 중요한 내용 보존 정도 (0-1)
3. SS (Semantic Similarity): 의미 유사성 유지 정도 (0-1)
4. 토큰 절감률: 토큰 수 감소 비율 (%)

다음 JSON 형식으로 응답해주세요:
{{
    "metrics": {{
        "nrr": 0.95,
        "fpr": 0.98,
        "ss": 0.92,
        "token_reduction": 25.5,
        "parsing_errors": 0
    }},
    "errors": ["오류1", "오류2"],
    "suggestions": [
        {{
            "description": "개선 제안 1",
            "confidence_score": 0.85,
            "rule_type": "regex_improvement",
            "estimated_improvement": "5-8% 토큰 절감",
            "applicable_cases": ["민사", "형사"],
            "pattern_before": "현재 패턴",
            "pattern_after": "개선된 패턴"
        }}
    ]
}}
"""
    
    def _create_improvement_prompt(self, pattern: Dict[str, Any]) -> str:
        """개선 제안 프롬프트 생성"""
        
        return f"""
다음 실패 패턴을 분석하고 개선 방안을 제안해주세요.

**실패 패턴:**
- 오류 메시지: {pattern['_id']}
- 발생 횟수: {pattern['count']}
- 샘플 케이스: {pattern.get('sample_cases', [])[:3]}

**요구사항:**
1. 오류의 근본 원인 분석
2. 정규식 패턴 개선 제안
3. 적용 우선순위 및 신뢰도

다음 JSON 형식으로 응답해주세요:
{{
    "rule_type": "page_number_removal",
    "description": "개선 설명",
    "pattern": "정규식 패턴",
    "replacement": "대체 문자열",
    "confidence_score": 0.85,
    "priority": 100
}}
"""
    
    def _parse_evaluation_result(
        self, 
        result_text: str, 
        before_content: str, 
        after_content: str
    ) -> Tuple[QualityMetrics, List[str], str]:
        """평가 결과 파싱"""
        
        try:
            result_data = json.loads(result_text)
            
            metrics = QualityMetrics(
                nrr=result_data["metrics"]["nrr"],
                fpr=result_data["metrics"]["fpr"],
                ss=result_data["metrics"]["ss"],
                token_reduction=result_data["metrics"]["token_reduction"],
                parsing_errors=result_data["metrics"].get("parsing_errors", 0)
            )
            
            errors = result_data.get("errors", [])
            suggestions = result_data.get("suggestions", [])
            
            return metrics, errors, suggestions
            
        except Exception as e:
            logger.error(f"Failed to parse evaluation result: {e}")
            logger.error(f"Raw result text: {result_text}")
            # 기본값 반환
            metrics = QualityMetrics(nrr=0.0, fpr=0.0, ss=0.0, token_reduction=0.0)
            return metrics, [f"파싱 오류: {str(e)}"], []
    
    def _parse_improvement_suggestion(
        self, 
        suggestion_text: str, 
        pattern: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """개선 제안 파싱"""
        
        try:
            suggestion_data = json.loads(suggestion_text)
            
            return {
                "patch_id": f"ai_suggestion_{pattern['_id'][:10]}",
                "rule_type": suggestion_data.get("rule_type"),
                "description": suggestion_data.get("description"),
                "pattern": suggestion_data.get("pattern"),
                "replacement": suggestion_data.get("replacement", ""),
                "confidence_score": suggestion_data.get("confidence_score", 0.5),
                "priority": suggestion_data.get("priority", 50),
                "applicable_cases": pattern.get("sample_cases", [])[:5]
            }
            
        except Exception as e:
            logger.warning(f"Failed to parse improvement suggestion: {e}")
            return None
    
    async def _create_batch_file(self, requests: List[Dict[str, Any]]) -> Any:
        """배치 파일 생성"""
        
        # JSONL 형식으로 변환
        jsonl_content = "\n".join(json.dumps(req) for req in requests)
        
        # 파일 업로드
        file_response = await self.client.files.create(
            file=jsonl_content.encode(),
            purpose="batch"
        )
        
        return file_response
    
    async def _wait_for_batch_completion(self, batch_id: str, max_wait_time: int = 3600) -> Any:
        """배치 완료 대기"""
        
        wait_time = 0
        while wait_time < max_wait_time:
            batch = await self.client.batches.retrieve(batch_id)
            
            if batch.status == "completed":
                return batch
            elif batch.status == "failed":
                raise Exception(f"Batch job failed: {batch.errors}")
            
            await asyncio.sleep(30)  # 30초 대기
            wait_time += 30
        
        raise Exception("Batch job timeout")
    
    async def _parse_batch_results(
        self, 
        batch_result: Any, 
        original_cases: List[Dict[str, Any]]
    ) -> List[Tuple[str, QualityMetrics, List[str], str]]:
        """배치 결과 파싱"""
        
        results = []
        
        # 결과 파일 다운로드
        if batch_result.output_file_id:
            output_file = await self.client.files.content(batch_result.output_file_id)
            output_content = output_file.read().decode()
            
            for line in output_content.strip().split('\n'):
                try:
                    result_data = json.loads(line)
                    custom_id = result_data["custom_id"]
                    
                    # case_id 추출
                    case_id = custom_id.split('_')[1]
                    
                    # 원본 케이스 찾기
                    original_case = next(
                        (case for case in original_cases if case["case_id"] == case_id), 
                        None
                    )
                    
                    if original_case:
                        response_content = result_data["response"]["body"]["choices"][0]["message"]["content"]
                        
                        metrics, errors, suggestions = self._parse_evaluation_result(
                            response_content,
                            original_case["before_content"],
                            original_case["after_content"]
                        )
                        
                        results.append((case_id, metrics, errors, suggestions))
                        
                except Exception as e:
                    logger.warning(f"Failed to parse batch result line: {e}")
                    continue
        
        return results
    
    def calculate_token_count(self, text: str) -> int:
        """토큰 수 계산 (근사치)"""
        # 간단한 토큰 수 추정 (실제로는 tiktoken 등을 사용)
        return len(text.split()) * 1.3  # 한국어 특성 고려
    
    async def estimate_batch_cost(self, cases: List[Dict[str, Any]]) -> float:
        """배치 비용 추정"""
        
        total_tokens = 0
        
        for case in cases:
            prompt = self._create_evaluation_prompt(
                case["before_content"], 
                case["after_content"], 
                case.get("metadata", {})
            )
            total_tokens += self.calculate_token_count(prompt)
        
        # GPT-4 Turbo 가격 기준 (input: $0.01/1K tokens, output: $0.03/1K tokens)
        input_cost = (total_tokens / 1000) * 0.01
        output_cost = (len(cases) * 500 / 1000) * 0.03  # 평균 500 토큰 출력 가정
        
        return input_cost + output_cost
