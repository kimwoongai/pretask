"""
환경 설정 및 토글 시스템
"""
import os
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    """애플리케이션 설정"""
    
    # Environment
    environment: str = Field(default="development", env="ENVIRONMENT")
    
    # Processing Modes (토글 시스템)
    single_run_mode: bool = Field(default=True, env="SINGLE_RUN_MODE")
    auto_patch: bool = Field(default=True, env="AUTO_PATCH")
    auto_advance: bool = Field(default=False, env="AUTO_ADVANCE")
    use_batch_api: bool = Field(default=False, env="USE_BATCH_API")
    
    # Quality Gates (합격선)
    min_nrr: float = Field(default=0.92, env="MIN_NRR")
    min_fpr: float = Field(default=0.985, env="MIN_FPR")
    min_ss: float = Field(default=0.90, env="MIN_SS")
    min_token_reduction: float = Field(default=20.0, env="MIN_TOKEN_REDUCTION")
    
    # Database - Render 환경에서는 환경 변수로 자동 설정됨
    mongodb_url: str = Field(default="mongodb://localhost:27017", env="MONGODB_URL")
    mongodb_db: str = Field(default="document_processor", env="MONGODB_DB")
    redis_url: str = Field(default="redis://localhost:6379", env="REDIS_URL")
    
    # OpenAI API
    openai_api_key: str = Field(default="", env="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-4-turbo-preview", env="OPENAI_MODEL")
    
    # Batch Processing
    max_batch_size: int = Field(default=1000, env="MAX_BATCH_SIZE")
    batch_timeout_seconds: int = Field(default=3600, env="BATCH_TIMEOUT_SECONDS")
    max_concurrent_batches: int = Field(default=5, env="MAX_CONCURRENT_BATCHES")
    
    # Safety Settings
    max_auto_patch_attempts: int = Field(default=3, env="MAX_AUTO_PATCH_ATTEMPTS")
    oscillation_prevention: bool = Field(default=True, env="OSCILLATION_PREVENTION")
    auto_rollback: bool = Field(default=True, env="AUTO_ROLLBACK")
    whitelist_dsl_only: bool = Field(default=True, env="WHITELIST_DSL_ONLY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    log_file: str = Field(default="logs/app.log", env="LOG_FILE")
    
    # Render 특정 설정
    port: int = Field(default=8000, env="PORT")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def is_production(self) -> bool:
        """프로덕션 환경인지 확인"""
        return self.environment.lower() == "production"
    
    def get_mongodb_connection_string(self) -> str:
        """MongoDB 연결 문자열 반환"""
        if self.is_production():
            # Render에서 제공하는 연결 문자열 사용
            return self.mongodb_url
        else:
            # 로컬 개발 환경
            return "mongodb://localhost:27017"


class ProcessingMode:
    """처리 모드 관리 클래스"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def is_single_run_mode(self) -> bool:
        """단건 점검 모드인지 확인"""
        return self.settings.single_run_mode
    
    def is_batch_mode(self) -> bool:
        """배치 모드인지 확인"""
        return not self.settings.single_run_mode and self.settings.use_batch_api
    
    def is_full_processing_mode(self) -> bool:
        """전량 처리 모드인지 확인"""
        return not self.settings.single_run_mode and not self.settings.use_batch_api
    
    def get_mode_name(self) -> str:
        """현재 모드명 반환"""
        if self.is_single_run_mode():
            return "단건 점검 모드 (Shakedown)"
        elif self.is_batch_mode():
            return "Batch API 반복 개선"
        else:
            return "전량 처리 모드"
    
    def get_mode_config(self) -> Dict[str, Any]:
        """현재 모드 설정 반환"""
        return {
            "mode": self.get_mode_name(),
            "single_run_mode": self.settings.single_run_mode,
            "auto_patch": self.settings.auto_patch,
            "auto_advance": self.settings.auto_advance,
            "use_batch_api": self.settings.use_batch_api,
            "quality_gates": {
                "min_nrr": self.settings.min_nrr,
                "min_fpr": self.settings.min_fpr,
                "min_ss": self.settings.min_ss,
                "min_token_reduction": self.settings.min_token_reduction
            }
        }


class QualityGates:
    """품질 게이트 관리 클래스"""
    
    def __init__(self, settings: Settings):
        self.settings = settings
    
    def check_quality_metrics(self, metrics: Dict[str, float]) -> Dict[str, bool]:
        """품질 지표 검사"""
        return {
            "nrr_pass": metrics.get("nrr", 0) >= self.settings.min_nrr,
            "fpr_pass": metrics.get("fpr", 0) >= self.settings.min_fpr,
            "ss_pass": metrics.get("ss", 0) >= self.settings.min_ss,
            "token_reduction_pass": metrics.get("token_reduction", 0) >= self.settings.min_token_reduction
        }
    
    def is_passing(self, metrics: Dict[str, float]) -> bool:
        """모든 품질 지표 통과 여부"""
        checks = self.check_quality_metrics(metrics)
        return all(checks.values())
    
    def get_failing_metrics(self, metrics: Dict[str, float]) -> Dict[str, float]:
        """실패한 지표들 반환"""
        checks = self.check_quality_metrics(metrics)
        failing = {}
        
        if not checks["nrr_pass"]:
            failing["nrr"] = {"actual": metrics.get("nrr", 0), "required": self.settings.min_nrr}
        if not checks["fpr_pass"]:
            failing["fpr"] = {"actual": metrics.get("fpr", 0), "required": self.settings.min_fpr}
        if not checks["ss_pass"]:
            failing["ss"] = {"actual": metrics.get("ss", 0), "required": self.settings.min_ss}
        if not checks["token_reduction_pass"]:
            failing["token_reduction"] = {
                "actual": metrics.get("token_reduction", 0), 
                "required": self.settings.min_token_reduction
            }
        
        return failing


# 글로벌 설정 인스턴스
settings = Settings()
processing_mode = ProcessingMode(settings)
quality_gates = QualityGates(settings)