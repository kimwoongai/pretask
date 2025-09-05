"""
규칙 전용 처리기 - AI 평가 없이 기본 규칙만으로 전처리
"""
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from app.services.dsl_rules import dsl_manager
from app.core.database import db_manager

logger = logging.getLogger(__name__)


class RuleOnlyProcessor:
    """규칙 전용 처리기 - AI 평가 없이 기본 규칙만 사용"""
    
    def __init__(self):
        self.processed_count = 0
        self.error_count = 0
        self.start_time = None
        
    async def process_all_precedents(self, batch_size: int = 100) -> Dict[str, Any]:
        """모든 판례를 기본 규칙만으로 전처리"""
        try:
            self.start_time = datetime.now()
            print(f"🚀 기본 규칙 전용 전처리 시작 - 배치 크기: {batch_size}")
            
            # MongoDB 컬렉션 연결
            source_collection = db_manager.get_collection('precedents_v2')
            target_collection = db_manager.get_collection('processed_cases')
            
            if not source_collection:
                raise Exception("precedents_v2 컬렉션을 찾을 수 없습니다")
            
            # 전체 문서 수 확인
            total_count = await source_collection.count_documents({})
            print(f"📊 전체 판례 수: {total_count:,}개")
            
            # 배치 단위로 처리
            processed = 0
            skip = 0
            
            while processed < total_count:
                print(f"📋 배치 처리 중: {processed:,}/{total_count:,} ({processed/total_count*100:.1f}%)")
                
                # 배치 데이터 가져오기
                cursor = source_collection.find({}).skip(skip).limit(batch_size)
                batch_docs = await cursor.to_list(length=batch_size)
                
                if not batch_docs:
                    break
                
                # 배치 처리
                batch_results = await self._process_batch(batch_docs)
                
                # 결과 저장
                if batch_results:
                    await target_collection.insert_many(batch_results)
                    print(f"✅ 배치 저장 완료: {len(batch_results)}개")
                
                processed += len(batch_docs)
                skip += batch_size
                
                # 진행 상황 출력
                if processed % 1000 == 0:
                    elapsed = (datetime.now() - self.start_time).total_seconds()
                    rate = processed / elapsed if elapsed > 0 else 0
                    remaining = (total_count - processed) / rate if rate > 0 else 0
                    print(f"⏱️ 처리 속도: {rate:.1f}건/초, 예상 남은 시간: {remaining/60:.1f}분")
            
            # 최종 결과
            end_time = datetime.now()
            total_time = (end_time - self.start_time).total_seconds()
            
            return {
                "status": "completed",
                "total_processed": self.processed_count,
                "total_errors": self.error_count,
                "processing_time_seconds": total_time,
                "average_rate": self.processed_count / total_time if total_time > 0 else 0,
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
        except Exception as e:
            logger.error(f"전체 처리 실패: {e}")
            return {
                "status": "failed",
                "error": str(e),
                "processed_count": self.processed_count,
                "error_count": self.error_count
            }
    
    async def _process_batch(self, batch_docs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """배치 문서들을 처리"""
        results = []
        
        for doc in batch_docs:
            try:
                result = await self._process_single_document(doc)
                if result:
                    results.append(result)
                    self.processed_count += 1
            except Exception as e:
                self.error_count += 1
                logger.error(f"문서 처리 실패 {doc.get('_id', 'unknown')}: {e}")
        
        return results
    
    async def _process_single_document(self, doc: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """단일 문서 처리"""
        try:
            # 텍스트 내용 추출
            original_content = self._extract_content(doc)
            if not original_content or len(original_content) < 50:
                return None
            
            # 기본 규칙 적용
            processed_content, rule_results = dsl_manager.apply_rules(original_content)
            
            # 처리 통계
            original_length = len(original_content)
            processed_length = len(processed_content)
            reduction_rate = (original_length - processed_length) / original_length * 100 if original_length > 0 else 0
            
            # 결과 구성
            result = {
                "original_id": str(doc.get("_id", "")),
                "precedent_id": doc.get("precedent_id", ""),
                "case_name": doc.get("case_name", ""),
                "case_number": doc.get("case_number", ""),
                "court_name": doc.get("court_name", ""),
                "court_type": doc.get("court_type", ""),
                "decision_date": doc.get("decision_date", ""),
                "original_content": original_content,
                "processed_content": processed_content,
                "processing_mode": "rule_only",
                "rules_version": dsl_manager.version,
                "original_length": original_length,
                "processed_length": processed_length,
                "reduction_rate": round(reduction_rate, 2),
                "applied_rules": [rule["rule_id"] for rule in rule_results["applied_rules"]],
                "applied_rule_count": rule_results["stats"]["applied_rule_count"],
                "rule_types_used": rule_results["stats"]["rule_types"],
                "processed_at": datetime.now().isoformat(),
                "status": "completed"
            }
            
            return result
            
        except Exception as e:
            logger.error(f"단일 문서 처리 실패: {e}")
            return None
    
    def _extract_content(self, doc: Dict[str, Any]) -> Optional[str]:
        """문서에서 텍스트 내용 추출"""
        # 다양한 필드명 시도
        content_fields = ['content', 'text', 'body', 'document_text', 'full_text']
        
        for field in content_fields:
            content = doc.get(field)
            if content and isinstance(content, str) and len(content.strip()) > 0:
                return content.strip()
        
        return None
    
    def get_progress_stats(self) -> Dict[str, Any]:
        """진행 상황 통계"""
        if self.start_time:
            elapsed = (datetime.now() - self.start_time).total_seconds()
            rate = self.processed_count / elapsed if elapsed > 0 else 0
        else:
            elapsed = 0
            rate = 0
        
        return {
            "processed_count": self.processed_count,
            "error_count": self.error_count,
            "elapsed_seconds": elapsed,
            "processing_rate": round(rate, 2),
            "status": "running" if self.start_time else "idle"
        }


# 전역 인스턴스
rule_only_processor = RuleOnlyProcessor()
