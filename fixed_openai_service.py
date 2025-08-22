"""
수정된 OpenAI 서비스 - 안전한 규칙 생성
"""

def _create_evaluation_prompt_FIXED(
    self, 
    before_content: str, 
    after_content: str, 
    metadata: Dict[str, Any]
) -> str:
    """수정된 평가 프롬프트 생성 - 보수적 접근"""
    
    return f"""
다음 법률 문서의 전처리 결과를 평가하고 **보수적이고 안전한** 개선 제안을 제공해주세요.

**문서 정보:**
- 법원 유형: {metadata.get('court_type', 'N/A')}
- 사건 유형: {metadata.get('case_type', 'N/A')}
- 연도: {metadata.get('year', 'N/A')}

**전처리 전 내용 (처음 800자):**
{before_content[:800]}...

**전처리 후 내용 (처음 800자):**
{after_content[:800]}...

**⚠️ 중요한 제약사항:**
1. **사실관계는 절대 건드리지 마세요**
2. **확실한 노이즈만 제거하세요**
3. **광범위한 정규식(.*?) 사용을 피하세요**
4. **라인 단위 매칭(^패턴$)을 선호하세요**

**안전하게 제거 가능한 노이즈:**
  * UI 요소: "저장 인쇄 보관" (정확한 문구만)
  * 시스템 메뉴: "PDF로 보기" (정확한 문구만)
  * 페이지 번호: "페이지 123" (구체적 패턴만)
  * 구분선: "-----" (정확한 패턴만)
  * 소송비용: "소송비용은...부담한다." (구체적 문장만)

**절대 건드리면 안 되는 것들:**
  * 당사자 정보와 행위 설명
  * 사건 발생 경위와 사실관계
  * 구체적 날짜, 장소, 금액
  * 계약 내용이나 약정 사항
  * 객관적 사실이나 증거

**예시 - 안전한 패턴들:**
- ✅ 좋은 예: "^페이지 \\d+$" (라인 단위)
- ✅ 좋은 예: "소송비용은.*?부담한다\\." (구체적 문장)
- ❌ 나쁜 예: "【.*?】" (모든 대괄호 삭제)
- ❌ 나쁜 예: "따라서.*?판단한다" (사실관계 포함 가능)

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
        "제거되지 않은 UI 요소 발견"
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
        }}
    ]
}}
"""
