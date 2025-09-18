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
            logger.info(f"규칙전용처리 시작 - 배치크기: {batch_size}")
            
            # MongoDB 컬렉션 연결
            print("🔍 DEBUG: MongoDB 컬렉션 연결 시도...")
            source_collection = db_manager.get_collection('processed_precedents')
            target_collection = db_manager.get_collection('cases')
            print(f"🔍 DEBUG: source_collection: {source_collection is not None}")
            print(f"🔍 DEBUG: target_collection: {target_collection is not None}")
            
            if source_collection is None:
                print("❌ DEBUG: source_collection이 None입니다")
                raise Exception("processed_precedents 컬렉션을 찾을 수 없습니다")
            
            if target_collection is None:
                print("❌ DEBUG: target_collection이 None입니다")
                raise Exception("cases 컬렉션을 찾을 수 없습니다")
            
            print("✅ DEBUG: 컬렉션 검증 완료")
            
            # 전체 문서 수 확인
            print("🔍 DEBUG: count_documents 호출 시작...")
            logger.info("count_documents 호출 시작")
            try:
                # 타임아웃을 설정하여 무한 대기 방지
                import asyncio
                total_count = await asyncio.wait_for(
                    source_collection.count_documents({}), 
                    timeout=30.0  # 30초 타임아웃
                )
                print(f"📊 전체 판례 수: {total_count:,}개")
            except asyncio.TimeoutError:
                print("❌ DEBUG: count_documents 타임아웃 (30초 초과)")
                logger.error("count_documents 타임아웃")
                # 대체 방법: estimated_document_count 사용
                try:
                    print("🔍 DEBUG: estimated_document_count 시도...")
                    total_count = await source_collection.estimated_document_count()
                    print(f"📊 추정 판례 수: {total_count:,}개 (estimated)")
                except Exception as est_error:
                    print(f"❌ DEBUG: estimated_document_count도 실패: {est_error}")
                    # 최후의 수단: find().limit(1) 테스트
                    print("🔍 DEBUG: 단일 문서 조회 테스트...")
                    test_doc = await source_collection.find_one({})
                    if test_doc:
                        print("✅ DEBUG: 최소 1개 문서는 조회 가능")
                        total_count = 100  # 테스트용으로 작은 수로 시작
                    else:
                        print("❌ DEBUG: 문서 조회 불가능")
                        total_count = 0
            except Exception as count_error:
                print(f"❌ DEBUG: count_documents 실패: {count_error}")
                logger.error(f"count_documents 실패: {count_error}")
                raise
            
            # 데이터가 없으면 종료
            if total_count == 0:
                print("⚠️ processed_precedents 컬렉션에 데이터가 없습니다.")
                return {
                    "status": "completed",
                    "total_processed": 0,
                    "total_errors": 0,
                    "message": "processed_precedents 컬렉션이 비어있습니다.",
                    "start_time": self.start_time.isoformat() if self.start_time else None,
                    "end_time": datetime.now().isoformat()
                }
            
            # 큰 컬렉션의 경우 처리량 제한
            if total_count > 1000:
                print(f"⚠️ 큰 컬렉션 감지 ({total_count:,}개). 테스트를 위해 처음 1000개만 처리합니다.")
                total_count = min(total_count, 1000)
            
            # 배치 단위로 처리
            processed = 0
            skip = 0
            
            while processed < total_count:
                print(f"📋 배치 처리 중: {processed:,}/{total_count:,} ({processed/total_count*100:.1f}%)")
                logger.info(f"배치 처리 진행: {processed}/{total_count}")
                
                # 배치 데이터 가져오기
                try:
                    print(f"🔍 DEBUG: 배치 데이터 조회 - skip: {skip}, limit: {batch_size}")
                    cursor = source_collection.find({}).skip(skip).limit(batch_size)
                    batch_docs = await cursor.to_list(length=batch_size)
                    print(f"🔍 DEBUG: 조회된 문서 수: {len(batch_docs)}")
                except Exception as fetch_error:
                    print(f"❌ DEBUG: 배치 데이터 조회 실패: {fetch_error}")
                    logger.error(f"배치 데이터 조회 실패: {fetch_error}")
                    break
                
                if not batch_docs:
                    print("🔍 DEBUG: 더 이상 처리할 문서가 없음")
                    break
                
                # 배치 처리
                try:
                    print(f"🔍 DEBUG: 배치 처리 시작 - {len(batch_docs)}개 문서")
                    batch_results = await self._process_batch(batch_docs)
                    print(f"🔍 DEBUG: 배치 처리 완료 - {len(batch_results) if batch_results else 0}개 결과")
                except Exception as process_error:
                    print(f"❌ DEBUG: 배치 처리 실패: {process_error}")
                    logger.error(f"배치 처리 실패: {process_error}")
                    self.error_count += len(batch_docs)
                    batch_results = []
                
                # 결과 저장
                if batch_results:
                    try:
                        await target_collection.insert_many(batch_results)
                        print(f"✅ 배치 저장 완료: {len(batch_results)}개")
                        self.processed_count += len(batch_results)
                    except Exception as save_error:
                        print(f"❌ DEBUG: 배치 저장 실패: {save_error}")
                        logger.error(f"배치 저장 실패: {save_error}")
                        self.error_count += len(batch_results)
                
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
            print(f"❌ DEBUG: 전체 처리 실패: {e}")
            print(f"❌ DEBUG: 예외 타입: {type(e)}")
            print(f"❌ DEBUG: 예외 위치: {e.__traceback__.tb_lineno if e.__traceback__ else 'unknown'}")
            logger.error(f"전체 처리 실패: {e}", exc_info=True)
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
            print(f"🔍 DEBUG: DSL 규칙 적용 시작 - 원본 길이: {len(original_content)}자")
            print(f"🔍 DEBUG: 로드된 규칙 수: {len(dsl_manager.rules)}")
            print(f"🔍 DEBUG: 활성화된 규칙 수: {len([r for r in dsl_manager.rules.values() if r.enabled])}")
            
            processed_content, rule_results = dsl_manager.apply_rules(original_content)
            
            print(f"🔍 DEBUG: 규칙 적용 완료 - 처리 후 길이: {len(processed_content)}자")
            print(f"🔍 DEBUG: 적용된 규칙 수: {rule_results['stats']['applied_rule_count']}")
            print(f"🔍 DEBUG: 적용된 규칙들: {[rule['rule_id'] for rule in rule_results['applied_rules']]}")
            
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
    
    async def test_processing(self, limit: int = 10) -> Dict[str, Any]:
        """테스트용 소량 처리"""
        try:
            start_time = datetime.now()
            print(f"🧪 규칙 전용 테스트 처리 시작 - {limit}개 문서")
            
            # MongoDB 컬렉션 연결
            source_collection = db_manager.get_collection('processed_precedents')
            target_collection = db_manager.get_collection('cases')
            
            if source_collection is None:
                raise Exception("processed_precedents 컬렉션을 찾을 수 없습니다")
            
            if target_collection is None:
                raise Exception("cases 컬렉션을 찾을 수 없습니다")
            
            # 테스트용 문서 가져오기 (랜덤 샘플)
            pipeline = [
                {"$sample": {"size": limit}},
                {"$project": {
                    "_id": 1,
                    "precedent_id": 1,
                    "case_name": 1,
                    "case_number": 1,
                    "court_name": 1,
                    "court_type": 1,
                    "decision_date": 1,
                    "content": 1,
                    "text": 1,
                    "body": 1,
                    "document_text": 1,
                    "full_text": 1
                }}
            ]
            
            test_docs = await source_collection.aggregate(pipeline).to_list(limit)
            
            if not test_docs:
                return {
                    "processed_count": 0,
                    "avg_reduction_rate": 0.0,
                    "total_rules_applied": 0,
                    "rules_version": dsl_manager.version,
                    "processing_time_ms": 0,
                    "sample_results": [],
                    "error": "테스트 문서를 찾을 수 없습니다"
                }
            
            # 테스트 문서들 처리
            results = []
            saved_results = []  # cases 컬렉션에 저장할 결과들
            total_reduction = 0.0
            total_rules_applied = 0
            
            for doc in test_docs:
                try:
                    result = await self._process_single_document(doc)
                    if result:
                        # 테스트 결과 요약 (API 응답용)
                        results.append({
                            "case_name": result["case_name"],
                            "original_length": result["original_length"],
                            "processed_length": result["processed_length"],
                            "reduction_rate": result["reduction_rate"],
                            "applied_rule_count": result["applied_rule_count"],
                            "applied_rules": result["applied_rules"][:5]  # 처음 5개만
                        })
                        
                        # cases 컬렉션 저장용 (전체 데이터)
                        test_result = result.copy()
                        test_result["processing_mode"] = "rule_only_test"  # 테스트임을 표시
                        saved_results.append(test_result)
                        
                        total_reduction += result["reduction_rate"]
                        total_rules_applied += result["applied_rule_count"]
                except Exception as e:
                    logger.error(f"테스트 문서 처리 실패: {e}")
                    continue
            
            # 테스트 결과를 cases 컬렉션에 저장
            if saved_results:
                try:
                    # 기존 테스트 결과와 중복 방지를 위해 upsert 사용
                    for result in saved_results:
                        await target_collection.update_one(
                            {
                                "original_id": result["original_id"],
                                "processing_mode": "rule_only_test"
                            },
                            {"$set": result},
                            upsert=True
                        )
                    print(f"✅ 테스트 결과 저장 완료: {len(saved_results)}개 → cases 컬렉션")
                except Exception as save_error:
                    print(f"❌ 테스트 결과 저장 실패: {save_error}")
                    logger.error(f"테스트 결과 저장 실패: {save_error}")
            
            # 통계 계산
            processed_count = len(results)
            avg_reduction_rate = total_reduction / processed_count if processed_count > 0 else 0.0
            processing_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
            
            print(f"✅ 테스트 완료: {processed_count}개 처리, 평균 압축률: {avg_reduction_rate:.1f}%")
            
            return {
                "processed_count": processed_count,
                "avg_reduction_rate": round(avg_reduction_rate, 1),
                "total_rules_applied": total_rules_applied,
                "rules_version": dsl_manager.version,
                "processing_time_ms": processing_time_ms,
                "sample_results": results
            }
            
        except Exception as e:
            logger.error(f"테스트 처리 실패: {e}")
            return {
                "processed_count": 0,
                "avg_reduction_rate": 0.0,
                "total_rules_applied": 0,
                "rules_version": "error",
                "processing_time_ms": 0,
                "sample_results": [],
                "error": str(e)
            }
    
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
