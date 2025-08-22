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
        
        print("🔍 DEBUG: OpenAI evaluate_single_case called")
        prompt = self._create_evaluation_prompt(before_content, after_content, case_metadata)
        print(f"🔍 DEBUG: Prompt created, length: {len(prompt)}")
        
        try:
            print("🔍 DEBUG: Making OpenAI API call...")
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "당신은 법률 문서 전처리 품질을 평가하는 전문가입니다."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            print("🔍 DEBUG: OpenAI API call successful")
            result_text = response.choices[0].message.content
            print(f"🔍 DEBUG: OpenAI raw response length: {len(result_text) if result_text else 0}")
            print(f"🔍 DEBUG: OpenAI raw response: {result_text}")
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
다음 법률 문서의 전처리 결과를 평가하고 구체적인 개선 제안을 제공해주세요.

**문서 정보:**
- 법원 유형: {metadata.get('court_type', 'N/A')}
- 사건 유형: {metadata.get('case_type', 'N/A')}
- 연도: {metadata.get('year', 'N/A')}

**전처리 전 내용 (처음 800자):**
{before_content[:800]}...

**전처리 후 내용 (처음 800자):**
{after_content[:800]}...

**평가 작업:**
1. 전처리 품질을 정량적으로 평가하세요
2. 발견된 문제점들을 errors 배열에 나열하세요
3. **전처리된 텍스트를 분석하여 개선 가능한 패턴을 찾아 제안하세요**

**개선 제안 생성 (보수적이고 안전한 노이즈 제거):**
- **확실한 노이즈만 제거하는 구체적이고 안전한 패턴을 제안하세요**
- **목표: 사실관계는 절대 건드리지 않고 명확한 노이즈만 제거**
- **중요: 광범위한 정규식(.*?) 사용을 피하고 라인 단위 매칭(^패턴$)을 선호하세요**

**안전하게 제거 가능한 노이즈:**
  * UI 요소: "저장 인쇄 보관" (정확한 문구만)
  * 시스템 메뉴: "PDF로 보기" (정확한 문구만)
  * 페이지 번호: "페이지 123" (구체적 패턴만)
  * 구분선: "-----" (정확한 패턴만)
  * 소송비용: "소송비용은...부담한다." (구체적 문장만)
  * 섹션 제목: "【주 문】" (제목만, 내용은 보존)

**보존해야 할 사실관계:**
  * 당사자 정보 (누가)
  * 사건 발생 경위 (언제, 어디서, 무엇을)
  * 구체적 행위나 사건 (어떻게)
  * 객관적 사실이나 증거

**평가 기준:**
1. NRR (Noise Reduction Rate): 불필요한 문구 제거율 (0-1)
2. ICR (Important Content Retention): 중요한 사실 보존율 (0-1)
3. SS (Semantic Similarity): 의미 유사성 유지 정도 (0-1)
4. 토큰 절감률: 전처리로 인한 토큰 수 감소 비율 (%)
5. parsing_errors: 파싱 과정에서 발생한 오류 개수

**중요: suggestions 배열에는 발견한 모든 개선 제안을 포함하세요. 빈 배열로 두지 마세요.**

반드시 다음 JSON 형식으로만 응답하세요:

{{
    "metrics": {{
        "nrr": 0.85,
        "icr": 0.92,
        "ss": 0.88,
        "token_reduction": 22.3,
        "parsing_errors": 0
    }},
    "errors": [
        "제거되지 않은 페이지 번호 패턴 발견",
        "중요한 날짜 정보가 과도하게 축약됨"
    ],
    "suggestions": [
        {{
            "description": "페이지 번호 제거",
            "confidence_score": 0.95,
            "rule_type": "noise_removal",
            "estimated_improvement": "페이지 번호 제거로 3-5% 간소화",
            "applicable_cases": ["모든 문서"],
            "pattern_before": "^페이지 \\d+$",
            "pattern_after": ""
        }},
        {{
            "description": "소송비용 부담 문구 제거",
            "confidence_score": 0.90,
            "rule_type": "noise_removal",
            "estimated_improvement": "비용 부담 문구 제거",
            "applicable_cases": ["모든 문서"],
            "pattern_before": "소송비용은.*?부담한다\\.",
            "pattern_after": ""
        }},
        {{
            "description": "UI 요소 제거",
            "confidence_score": 0.88,
            "rule_type": "noise_removal",
            "estimated_improvement": "UI 노이즈 제거로 3-5% 간소화",
            "applicable_cases": ["모든 문서"],
            "pattern_before": "저장 인쇄 보관 전자팩스 공유 화면내 검색 조회 닫기",
            "pattern_after": ""
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
            print(f"🔍 DEBUG: Attempting to parse JSON: {result_text}")
            
            # JSON 부분만 추출 (```json과 ``` 사이의 내용)
            json_text = result_text
            if "```json" in result_text:
                start = result_text.find("```json") + 7
                end = result_text.find("```", start)
                if end != -1:
                    json_text = result_text[start:end].strip()
                    print(f"🔍 DEBUG: Extracted JSON: {json_text}")
            elif "{" in result_text and "}" in result_text:
                # JSON 마커가 없는 경우, 첫 번째 { 부터 마지막 } 까지 추출
                start = result_text.find("{")
                end = result_text.rfind("}") + 1
                json_text = result_text[start:end].strip()
                print(f"🔍 DEBUG: Extracted JSON (fallback): {json_text}")
            
            # 정규식 패턴의 이스케이프 문자 처리
            try:
                result_data = json.loads(json_text)
            except json.JSONDecodeError as json_error:
                print(f"🔍 DEBUG: JSON 파싱 오류, 이스케이프 문자 처리 시도: {json_error}")
                # 정규식 패턴에서 백슬래시를 이중 백슬래시로 변환
                fixed_json_text = json_text
                # pattern_before와 pattern_after 필드에서 이스케이프 문자 수정
                import re as regex_module
                pattern_fields = regex_module.findall(r'"pattern_before":\s*"([^"]*)"', fixed_json_text)
                for pattern in pattern_fields:
                    if '\\' in pattern and not '\\\\' in pattern:
                        # 단일 백슬래시를 이중 백슬래시로 변경
                        fixed_pattern = pattern.replace('\\', '\\\\')
                        fixed_json_text = fixed_json_text.replace(f'"pattern_before": "{pattern}"', f'"pattern_before": "{fixed_pattern}"')
                
                pattern_after_fields = regex_module.findall(r'"pattern_after":\s*"([^"]*)"', fixed_json_text)
                for pattern in pattern_after_fields:
                    if '\\' in pattern and not '\\\\' in pattern:
                        # 단일 백슬래시를 이중 백슬래시로 변경
                        fixed_pattern = pattern.replace('\\', '\\\\')
                        fixed_json_text = fixed_json_text.replace(f'"pattern_after": "{pattern}"', f'"pattern_after": "{fixed_pattern}"')
                
                print(f"🔍 DEBUG: 수정된 JSON: {fixed_json_text[:500]}...")
                result_data = json.loads(fixed_json_text)
            
            metrics = QualityMetrics(
                nrr=result_data["metrics"]["nrr"],
                fpr=result_data["metrics"]["icr"],  # ICR을 fpr 필드에 저장 (기존 호환성)
                ss=result_data["metrics"]["ss"],
                token_reduction=result_data["metrics"]["token_reduction"],
                parsing_errors=result_data["metrics"].get("parsing_errors", 0)
            )
            
            errors = result_data.get("errors", [])
            suggestions = result_data.get("suggestions", [])
            
            print(f"🔍 DEBUG: AI 응답 상세 분석:")
            print(f"  - 메트릭스: NRR={metrics.nrr}, ICR/FPR={metrics.fpr}, SS={metrics.ss}, Token reduction={metrics.token_reduction}%")
            print(f"  - 오류 개수: {len(errors)}")
            print(f"  - 제안 개수: {len(suggestions)}")
            if suggestions:
                print(f"  - 제안 내용: {suggestions}")
            else:
                print(f"  - ⚠️ AI가 제안을 생성하지 않았습니다!")
                print(f"  - 원본 suggestions 데이터: {result_data.get('suggestions', 'KEY_NOT_FOUND')}")
            
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
        import io
        
        print(f"🔍 DEBUG: 배치 파일 생성 시작 - {len(requests)}개 요청")
        
        # JSONL 형식으로 변환
        jsonl_content = "\n".join(json.dumps(req) for req in requests)
        
        print(f"🔍 DEBUG: JSONL 콘텐츠 생성 완료 - {len(jsonl_content)} 문자")
        
        # BytesIO 객체로 파일 생성
        file_obj = io.BytesIO(jsonl_content.encode('utf-8'))
        file_obj.name = 'batch_requests.jsonl'  # 파일명 설정
        
        print(f"🔍 DEBUG: 파일 객체 생성 완료 - {file_obj.name}")
        
        # 파일 업로드
        try:
            file_response = await self.client.files.create(
                file=file_obj,
                purpose="batch"
            )
            
            print(f"✅ DEBUG: 배치 파일 업로드 성공 - ID: {file_response.id}")
            return file_response
            
        except Exception as e:
            print(f"❌ DEBUG: 배치 파일 업로드 실패: {e}")
            raise
    
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
