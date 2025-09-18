"""
문서 처리 관련 데이터 모델
"""
from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum


class ProcessingStatus(str, Enum):
    """처리 상태"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ProcessingMode(str, Enum):
    """처리 모드"""
    SINGLE_RUN = "single_run"
    BATCH_IMPROVEMENT = "batch_improvement"
    FULL_PROCESSING = "full_processing"


class QualityMetrics(BaseModel):
    """품질 지표"""
    nrr: float = Field(description="Noise Reduction Rate")
    fpr: float = Field(description="False Positive Rate")
    ss: float = Field(description="Semantic Similarity")
    token_reduction: float = Field(description="토큰 절감률 (%)")
    parsing_errors: int = Field(default=0, description="파싱 오류 수")


class DocumentCase(BaseModel):
    """문서 케이스"""
    case_id: str = Field(description="케이스 ID")
    court_type: str = Field(description="법원 유형")
    case_type: str = Field(description="사건 유형")
    year: int = Field(description="연도")
    format_type: str = Field(description="포맷 유형")
    original_content: str = Field(description="원본 내용")
    processed_content: Optional[str] = Field(default=None, description="처리된 내용")
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: Optional[datetime] = None


class ProcessedPrecedent(BaseModel):
    """전처리된 판례 데이터"""
    original_id: str = Field(description="원본 processed_precedents의 _id")
    precedent_id: str = Field(description="판례 ID")
    case_name: str = Field(description="사건명")
    case_number: str = Field(description="사건번호")
    court_name: str = Field(description="법원명")
    court_type: str = Field(description="법원 유형")
    decision_date: Optional[str] = Field(description="판결일")
    
    # 전처리된 내용
    processed_content: str = Field(description="전처리된 내용")
    content_length: int = Field(description="전처리된 내용 길이")
    
    # 처리 정보
    rules_version: str = Field(description="사용된 규칙 버전")
    processing_mode: str = Field(description="처리 모드 (single/batch/full)")
    processing_time_ms: int = Field(description="처리 시간")
    token_count_before: int = Field(description="처리 전 토큰 수")
    token_count_after: int = Field(description="처리 후 토큰 수")
    token_reduction_percent: float = Field(description="토큰 감소율")
    
    # 품질 정보
    quality_score: float = Field(description="품질 점수")
    status: str = Field(description="처리 상태", default="completed")
    
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProcessingResult(BaseModel):
    """처리 결과 (메트릭 및 분석용)"""
    case_id: str
    original_id: str = Field(description="원본 processed_precedents의 _id")
    rules_version: str = Field(description="사용된 규칙 버전")
    metrics: QualityMetrics
    before_content: str
    after_content: str
    diff_summary: str
    processing_time_ms: int
    token_count_before: int
    token_count_after: int
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)


class RulePatch(BaseModel):
    """규칙 패치"""
    patch_id: str
    rule_type: str = Field(description="규칙 유형")
    description: str = Field(description="패치 설명")
    before_rule: str = Field(description="기존 규칙")
    after_rule: str = Field(description="수정된 규칙")
    confidence_score: float = Field(description="신뢰도 점수")
    applicable_cases: List[str] = Field(description="적용 가능한 케이스들")
    created_at: datetime = Field(default_factory=datetime.now)


class BatchJob(BaseModel):
    """배치 작업"""
    job_id: str
    mode: ProcessingMode
    sample_size: int
    stratification_criteria: Dict[str, Any] = Field(description="층화 기준")
    rules_version: str
    status: ProcessingStatus = Field(default=ProcessingStatus.PENDING)
    progress: int = Field(default=0, description="진행률 (0-100)")
    total_cases: int
    processed_cases: int = Field(default=0)
    failed_cases: int = Field(default=0)
    success_rate: float = Field(default=0.0)
    average_metrics: Optional[QualityMetrics] = None
    estimated_cost: float = Field(default=0.0, description="예상 비용 (USD)")
    actual_cost: float = Field(default=0.0, description="실제 비용 (USD)")
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.now)


class FailureCluster(BaseModel):
    """실패 클러스터"""
    cluster_id: str
    pattern_type: str = Field(description="패턴 유형 (예: 페이지번호, 구분선, 참조조문)")
    failure_count: int
    sample_cases: List[str] = Field(description="샘플 케이스들")
    error_pattern: str = Field(description="오류 패턴")
    suggested_patch: Optional[RulePatch] = None
    created_at: datetime = Field(default_factory=datetime.now)


class RulesVersion(BaseModel):
    """규칙 버전"""
    version: str = Field(description="버전 (예: v1.2.3)")
    description: str
    rules_content: str = Field(description="DSL 규칙 내용")
    parent_version: Optional[str] = None
    patches_applied: List[str] = Field(default_factory=list)
    test_results: Optional[Dict[str, Any]] = None
    is_stable: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.now)


class SafetyGate(BaseModel):
    """안전 게이트"""
    gate_type: str = Field(description="게이트 유형 (unit/regression/holdout)")
    version: str = Field(description="테스트된 규칙 버전")
    passed: bool
    test_results: Dict[str, Any]
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
