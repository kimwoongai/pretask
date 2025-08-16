"""
판례 전처리 시스템 설정
"""

# 라벨 생성 가이드라인
LABEL_GENERATION_GUIDELINES = {
    "fact_categories": {
        "parties": {
            "description": "사건 당사자 정보",
            "keywords": ["원고", "피고", "신청인", "피신청인", "대표이사", "세무서장"],
            "examples": ["원고: 주식회사 ABC", "피고: 국세청장"]
        },
        "timeline": {
            "description": "사건 발생 시간순서",
            "keywords": ["년", "월", "일", "부터", "까지", "이후", "이전"],
            "examples": ["2022.01.15 계약 체결", "2023.03.10 처분 통지"]
        },
        "amounts": {
            "description": "금액 관련 정보",
            "keywords": ["원", "만원", "억원", "지급", "송금", "납부"],
            "examples": ["1,000,000원 지급", "종합부동산세 500만원"]
        },
        "actions": {
            "description": "핵심 행위 및 처분",
            "keywords": ["계약", "양도", "이전등록", "부과", "통지", "신청", "제기"],
            "examples": ["양도소득세 부과처분", "취소소송 제기"]
        },
        "legal_basis": {
            "description": "근거 법령",
            "keywords": ["법", "조", "항", "호", "규정", "시행령"],
            "examples": ["소득세법 제95조", "부가가치세법 시행령"]
        }
    },
    "quality_thresholds": {
        "min_fact_sentences": 3,
        "max_legal_reasoning": 0,
        "min_entities": 2,
        "target_length_min": 1000,
        "target_length_max": 1600,
        "compressed_length_min": 350,
        "compressed_length_max": 700
    },
    "exclusion_patterns": [
        "주문", "이유", "판단", "법리", "요지", "참조판례",
        "타당하다", "정당하다", "부당하다", "인정된다", "판단된다"
    ]
}
