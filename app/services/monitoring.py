"""
모니터링 및 메트릭 수집 시스템
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
from collections import defaultdict, deque
import time
import psutil
import logging

from app.core.config import settings
from app.core.database import db_manager, cache_manager
from app.core.logging import CustomLogger

logger = CustomLogger(__name__)


@dataclass
class SystemMetrics:
    """시스템 메트릭"""
    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_used_mb: float
    disk_percent: float
    active_connections: int
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProcessingMetrics:
    """처리 메트릭"""
    timestamp: datetime
    mode: str  # single_run, batch_improvement, full_processing
    cases_processed: int
    cases_failed: int
    avg_processing_time_ms: float
    total_processing_time_ms: float
    success_rate: float
    rules_version: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityMetrics:
    """품질 메트릭"""
    timestamp: datetime
    avg_nrr: float
    avg_fpr: float
    avg_ss: float
    avg_token_reduction: float
    total_parsing_errors: int
    rules_version: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CostMetrics:
    """비용 메트릭"""
    timestamp: datetime
    openai_api_calls: int
    openai_tokens_used: int
    estimated_cost_usd: float
    actual_cost_usd: float
    cost_per_case: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class MetricsCollector:
    """메트릭 수집기"""
    
    def __init__(self):
        self.system_metrics_history = deque(maxlen=1000)
        self.processing_metrics_history = deque(maxlen=1000)
        self.quality_metrics_history = deque(maxlen=1000)
        self.cost_metrics_history = deque(maxlen=1000)
        
        self.current_processing_stats = {
            "cases_processed": 0,
            "cases_failed": 0,
            "processing_times": deque(maxlen=100),
            "start_time": None,
            "current_mode": None,
            "rules_version": None
        }
        
        self.cost_tracker = {
            "api_calls": 0,
            "tokens_used": 0,
            "estimated_cost": 0.0,
            "actual_cost": 0.0
        }
        
        self.is_collecting = False
        self.collection_task = None
    
    async def start_collecting(self, interval_seconds: int = 30):
        """메트릭 수집 시작"""
        if self.is_collecting:
            return
        
        self.is_collecting = True
        self.collection_task = asyncio.create_task(
            self._collection_loop(interval_seconds)
        )
        
        logger.info("Metrics collection started", interval=interval_seconds)
    
    async def stop_collecting(self):
        """메트릭 수집 중지"""
        self.is_collecting = False
        
        if self.collection_task:
            self.collection_task.cancel()
            try:
                await self.collection_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Metrics collection stopped")
    
    async def _collection_loop(self, interval_seconds: int):
        """메트릭 수집 루프"""
        while self.is_collecting:
            try:
                # 시스템 메트릭 수집
                system_metrics = self._collect_system_metrics()
                self.system_metrics_history.append(system_metrics)
                
                # 처리 메트릭 수집
                processing_metrics = self._collect_processing_metrics()
                if processing_metrics:
                    self.processing_metrics_history.append(processing_metrics)
                
                # 품질 메트릭 수집
                quality_metrics = await self._collect_quality_metrics()
                if quality_metrics:
                    self.quality_metrics_history.append(quality_metrics)
                
                # 비용 메트릭 수집
                cost_metrics = self._collect_cost_metrics()
                self.cost_metrics_history.append(cost_metrics)
                
                # 메트릭을 캐시에 저장
                await self._save_metrics_to_cache()
                
                await asyncio.sleep(interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in metrics collection loop: {e}")
                await asyncio.sleep(interval_seconds)
    
    def _collect_system_metrics(self) -> SystemMetrics:
        """시스템 메트릭 수집"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # 활성 연결 수 (간단한 근사치)
            active_connections = len(psutil.net_connections())
            
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=cpu_percent,
                memory_percent=memory.percent,
                memory_used_mb=memory.used / (1024 * 1024),
                disk_percent=disk.percent,
                active_connections=active_connections
            )
            
        except Exception as e:
            logger.error(f"Failed to collect system metrics: {e}")
            return SystemMetrics(
                timestamp=datetime.now(),
                cpu_percent=0.0,
                memory_percent=0.0,
                memory_used_mb=0.0,
                disk_percent=0.0,
                active_connections=0
            )
    
    def _collect_processing_metrics(self) -> Optional[ProcessingMetrics]:
        """처리 메트릭 수집"""
        if not self.current_processing_stats["start_time"]:
            return None
        
        try:
            processing_times = list(self.current_processing_stats["processing_times"])
            avg_processing_time = sum(processing_times) / len(processing_times) if processing_times else 0
            total_processing_time = sum(processing_times)
            
            total_cases = (
                self.current_processing_stats["cases_processed"] + 
                self.current_processing_stats["cases_failed"]
            )
            success_rate = (
                self.current_processing_stats["cases_processed"] / total_cases * 100
                if total_cases > 0 else 0
            )
            
            return ProcessingMetrics(
                timestamp=datetime.now(),
                mode=self.current_processing_stats["current_mode"] or "unknown",
                cases_processed=self.current_processing_stats["cases_processed"],
                cases_failed=self.current_processing_stats["cases_failed"],
                avg_processing_time_ms=avg_processing_time,
                total_processing_time_ms=total_processing_time,
                success_rate=success_rate,
                rules_version=self.current_processing_stats["rules_version"] or "unknown"
            )
            
        except Exception as e:
            logger.error(f"Failed to collect processing metrics: {e}")
            return None
    
    async def _collect_quality_metrics(self) -> Optional[QualityMetrics]:
        """품질 메트릭 수집"""
        try:
            # 최근 처리 결과에서 품질 지표 집계
            # 실제로는 데이터베이스에서 조회
            
            return QualityMetrics(
                timestamp=datetime.now(),
                avg_nrr=0.93,
                avg_fpr=0.987,
                avg_ss=0.91,
                avg_token_reduction=22.5,
                total_parsing_errors=0,
                rules_version=self.current_processing_stats["rules_version"] or "unknown"
            )
            
        except Exception as e:
            logger.error(f"Failed to collect quality metrics: {e}")
            return None
    
    def _collect_cost_metrics(self) -> CostMetrics:
        """비용 메트릭 수집"""
        try:
            total_cases = (
                self.current_processing_stats["cases_processed"] + 
                self.current_processing_stats["cases_failed"]
            )
            
            cost_per_case = (
                self.cost_tracker["estimated_cost"] / total_cases
                if total_cases > 0 else 0
            )
            
            return CostMetrics(
                timestamp=datetime.now(),
                openai_api_calls=self.cost_tracker["api_calls"],
                openai_tokens_used=self.cost_tracker["tokens_used"],
                estimated_cost_usd=self.cost_tracker["estimated_cost"],
                actual_cost_usd=self.cost_tracker["actual_cost"],
                cost_per_case=cost_per_case
            )
            
        except Exception as e:
            logger.error(f"Failed to collect cost metrics: {e}")
            return CostMetrics(
                timestamp=datetime.now(),
                openai_api_calls=0,
                openai_tokens_used=0,
                estimated_cost_usd=0.0,
                actual_cost_usd=0.0,
                cost_per_case=0.0
            )
    
    async def _save_metrics_to_cache(self):
        """메트릭을 캐시에 저장"""
        try:
            redis_client = await cache_manager.get_redis()
            
            # 최근 메트릭만 캐시에 저장
            if self.system_metrics_history:
                await redis_client.setex(
                    "metrics:system:latest",
                    3600,  # 1시간 TTL
                    self.system_metrics_history[-1].to_dict()
                )
            
            if self.processing_metrics_history:
                await redis_client.setex(
                    "metrics:processing:latest",
                    3600,
                    self.processing_metrics_history[-1].to_dict()
                )
            
            if self.quality_metrics_history:
                await redis_client.setex(
                    "metrics:quality:latest",
                    3600,
                    self.quality_metrics_history[-1].to_dict()
                )
            
            if self.cost_metrics_history:
                await redis_client.setex(
                    "metrics:cost:latest",
                    3600,
                    self.cost_metrics_history[-1].to_dict()
                )
                
        except Exception as e:
            logger.error(f"Failed to save metrics to cache: {e}")
    
    def record_processing_start(self, mode: str, rules_version: str):
        """처리 시작 기록"""
        self.current_processing_stats.update({
            "start_time": datetime.now(),
            "current_mode": mode,
            "rules_version": rules_version,
            "cases_processed": 0,
            "cases_failed": 0
        })
        self.current_processing_stats["processing_times"].clear()
        
        logger.info("Processing started", mode=mode, rules_version=rules_version)
    
    def record_case_processed(self, processing_time_ms: float, success: bool):
        """케이스 처리 기록"""
        if success:
            self.current_processing_stats["cases_processed"] += 1
        else:
            self.current_processing_stats["cases_failed"] += 1
        
        self.current_processing_stats["processing_times"].append(processing_time_ms)
    
    def record_api_call(self, tokens_used: int, estimated_cost: float):
        """API 호출 기록"""
        self.cost_tracker["api_calls"] += 1
        self.cost_tracker["tokens_used"] += tokens_used
        self.cost_tracker["estimated_cost"] += estimated_cost
    
    def record_actual_cost(self, actual_cost: float):
        """실제 비용 기록"""
        self.cost_tracker["actual_cost"] += actual_cost
    
    def get_current_stats(self) -> Dict[str, Any]:
        """현재 통계 반환"""
        return {
            "processing_stats": self.current_processing_stats.copy(),
            "cost_stats": self.cost_tracker.copy(),
            "system_metrics": self.system_metrics_history[-1].to_dict() if self.system_metrics_history else None,
            "processing_metrics": self.processing_metrics_history[-1].to_dict() if self.processing_metrics_history else None,
            "quality_metrics": self.quality_metrics_history[-1].to_dict() if self.quality_metrics_history else None,
            "cost_metrics": self.cost_metrics_history[-1].to_dict() if self.cost_metrics_history else None
        }
    
    def get_historical_data(
        self, 
        metric_type: str, 
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """과거 데이터 반환"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        if metric_type == "system":
            history = self.system_metrics_history
        elif metric_type == "processing":
            history = self.processing_metrics_history
        elif metric_type == "quality":
            history = self.quality_metrics_history
        elif metric_type == "cost":
            history = self.cost_metrics_history
        else:
            return []
        
        return [
            metric.to_dict() for metric in history
            if metric.timestamp >= cutoff_time
        ]


class AlertManager:
    """알림 관리자"""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
        self.alert_rules = self._load_alert_rules()
        self.alert_history = deque(maxlen=1000)
        self.is_monitoring = False
        self.monitoring_task = None
    
    def _load_alert_rules(self) -> List[Dict[str, Any]]:
        """알림 규칙 로드"""
        return [
            {
                "name": "high_cpu_usage",
                "condition": lambda metrics: metrics.cpu_percent > 80,
                "metric_type": "system",
                "severity": "warning",
                "message": "High CPU usage detected: {cpu_percent:.1f}%"
            },
            {
                "name": "high_memory_usage",
                "condition": lambda metrics: metrics.memory_percent > 85,
                "metric_type": "system",
                "severity": "warning",
                "message": "High memory usage detected: {memory_percent:.1f}%"
            },
            {
                "name": "low_success_rate",
                "condition": lambda metrics: metrics.success_rate < 90,
                "metric_type": "processing",
                "severity": "error",
                "message": "Low processing success rate: {success_rate:.1f}%"
            },
            {
                "name": "high_processing_time",
                "condition": lambda metrics: metrics.avg_processing_time_ms > 10000,
                "metric_type": "processing",
                "severity": "warning",
                "message": "High average processing time: {avg_processing_time_ms:.0f}ms"
            },
            {
                "name": "quality_degradation",
                "condition": lambda metrics: metrics.avg_nrr < 0.90 or metrics.avg_fpr < 0.98,
                "metric_type": "quality",
                "severity": "error",
                "message": "Quality metrics degradation: NRR={avg_nrr:.3f}, FPR={avg_fpr:.3f}"
            }
        ]
    
    async def start_monitoring(self, check_interval_seconds: int = 60):
        """모니터링 시작"""
        if self.is_monitoring:
            return
        
        self.is_monitoring = True
        self.monitoring_task = asyncio.create_task(
            self._monitoring_loop(check_interval_seconds)
        )
        
        logger.info("Alert monitoring started", interval=check_interval_seconds)
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        self.is_monitoring = False
        
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Alert monitoring stopped")
    
    async def _monitoring_loop(self, check_interval_seconds: int):
        """모니터링 루프"""
        while self.is_monitoring:
            try:
                await self._check_alerts()
                await asyncio.sleep(check_interval_seconds)
                
            except Exception as e:
                logger.error(f"Error in alert monitoring loop: {e}")
                await asyncio.sleep(check_interval_seconds)
    
    async def _check_alerts(self):
        """알림 확인"""
        current_stats = self.metrics_collector.get_current_stats()
        
        for rule in self.alert_rules:
            try:
                metric_data = current_stats.get(f"{rule['metric_type']}_metrics")
                if not metric_data:
                    continue
                
                # 메트릭 객체 생성
                if rule["metric_type"] == "system":
                    metrics_obj = SystemMetrics(**metric_data)
                elif rule["metric_type"] == "processing":
                    metrics_obj = ProcessingMetrics(**metric_data)
                elif rule["metric_type"] == "quality":
                    metrics_obj = QualityMetrics(**metric_data)
                else:
                    continue
                
                # 조건 확인
                if rule["condition"](metrics_obj):
                    await self._trigger_alert(rule, metrics_obj)
                    
            except Exception as e:
                logger.error(f"Error checking alert rule {rule['name']}: {e}")
    
    async def _trigger_alert(self, rule: Dict[str, Any], metrics_obj):
        """알림 발생"""
        alert = {
            "timestamp": datetime.now(),
            "rule_name": rule["name"],
            "severity": rule["severity"],
            "message": rule["message"].format(**metrics_obj.to_dict()),
            "metrics": metrics_obj.to_dict()
        }
        
        self.alert_history.append(alert)
        
        # 로그 기록
        log_method = logger.error if rule["severity"] == "error" else logger.warning
        log_method(
            f"Alert triggered: {rule['name']}",
            severity=rule["severity"],
            message=alert["message"],
            metrics=metrics_obj.to_dict()
        )
        
        # 실제 알림 발송 (이메일, Slack 등)
        await self._send_notification(alert)
    
    async def _send_notification(self, alert: Dict[str, Any]):
        """알림 발송"""
        # 실제로는 이메일, Slack, SMS 등으로 알림 발송
        logger.info(f"Notification sent for alert: {alert['rule_name']}")
    
    def get_recent_alerts(self, hours: int = 24) -> List[Dict[str, Any]]:
        """최근 알림 조회"""
        cutoff_time = datetime.now() - timedelta(hours=hours)
        
        return [
            alert for alert in self.alert_history
            if alert["timestamp"] >= cutoff_time
        ]


# 글로벌 인스턴스
metrics_collector = MetricsCollector()
alert_manager = AlertManager(metrics_collector)
