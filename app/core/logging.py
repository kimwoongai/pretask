"""
로깅 시스템 설정
"""
import logging
import logging.handlers
from datetime import datetime
from typing import Dict, Any, Optional
import json
import os
from pathlib import Path

from app.core.config import settings


class JSONFormatter(logging.Formatter):
    """JSON 형식 로그 포매터"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # 추가 필드가 있으면 포함
        if hasattr(record, 'extra_fields'):
            log_entry.update(record.extra_fields)
        
        # 예외 정보가 있으면 포함
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        return json.dumps(log_entry, ensure_ascii=False)


class CustomLogger:
    """커스텀 로거"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, settings.log_level.upper()))
        
        # 핸들러가 이미 추가되었는지 확인
        if not self.logger.handlers:
            self._setup_handlers()
    
    def _setup_handlers(self):
        """로그 핸들러 설정"""
        
        # 파일 핸들러
        log_file = Path(settings.log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(JSONFormatter())
        self.logger.addHandler(file_handler)
        
        # 콘솔 핸들러 (개발 환경에서만)
        if settings.environment == "development":
            console_handler = logging.StreamHandler()
            console_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            console_handler.setFormatter(console_formatter)
            self.logger.addHandler(console_handler)
    
    def info(self, message: str, **kwargs):
        """정보 로그"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.info(message, extra=extra)
    
    def warning(self, message: str, **kwargs):
        """경고 로그"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.warning(message, extra=extra)
    
    def error(self, message: str, **kwargs):
        """오류 로그"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.error(message, extra=extra)
    
    def debug(self, message: str, **kwargs):
        """디버그 로그"""
        extra = {"extra_fields": kwargs} if kwargs else {}
        self.logger.debug(message, extra=extra)


def setup_logging():
    """로깅 시스템 초기화"""
    
    # 로그 디렉토리 생성
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # 루트 로거 설정
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, settings.log_level.upper()))
    
    # 기본 핸들러 제거
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # 애플리케이션 로거 설정
    app_logger = CustomLogger("app")
    
    return app_logger


# 글로벌 로거 인스턴스
logger = setup_logging()
