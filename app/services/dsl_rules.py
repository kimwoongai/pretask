"""
DSL 규칙 파일 관리 시스템
동적으로 전처리 규칙을 관리하고 업데이트
"""

import re
import json
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class DSLRule:
    """단일 DSL 규칙"""
    
    def __init__(self, rule_id: str, rule_type: str, pattern: str, 
                 replacement: str = "", priority: int = 0, enabled: bool = True,
                 description: str = "", performance_score: float = 0.0):
        self.rule_id = rule_id
        self.rule_type = rule_type  # 'noise_removal', 'fact_extraction', 'legal_filtering'
        self.pattern = pattern
        self.replacement = replacement
        self.priority = priority  # 높을수록 먼저 실행
        self.enabled = enabled
        self.description = description
        self.performance_score = performance_score
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.usage_count = 0
        self.success_rate = 0.0
    
    def apply(self, text: str) -> Tuple[str, bool]:
        """규칙을 텍스트에 적용"""
        if not self.enabled:
            return text, False
        
        try:
            if self.rule_type == 'noise_removal':
                # 노이즈 제거 규칙
                new_text = re.sub(self.pattern, self.replacement, text, flags=re.DOTALL | re.IGNORECASE)
                applied = new_text != text
            elif self.rule_type == 'fact_extraction':
                # 사실 추출 규칙 (매치되는 부분만 추출)
                matches = re.findall(self.pattern, text, flags=re.DOTALL | re.IGNORECASE)
                if matches:
                    new_text = ' '.join(matches)
                    applied = True
                else:
                    new_text = text
                    applied = False
            elif self.rule_type == 'legal_filtering':
                # 법리 문장 필터링 (매치되는 문장 제거)
                sentences = re.split(r'[.!?]\s+', text)
                filtered_sentences = []
                applied = False
                for sentence in sentences:
                    if not re.search(self.pattern, sentence, flags=re.IGNORECASE):
                        filtered_sentences.append(sentence)
                    else:
                        applied = True
                new_text = '. '.join(filtered_sentences)
            else:
                # 기본 치환 규칙
                new_text = re.sub(self.pattern, self.replacement, text, flags=re.DOTALL | re.IGNORECASE)
                applied = new_text != text
            
            if applied:
                self.usage_count += 1
                self.updated_at = datetime.now().isoformat()
            
            return new_text, applied
        except Exception as e:
            logger.error(f"규칙 적용 오류 {self.rule_id}: {e}")
            return text, False
    
    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'rule_id': self.rule_id,
            'rule_type': self.rule_type,
            'pattern': self.pattern,
            'replacement': self.replacement,
            'priority': self.priority,
            'enabled': self.enabled,
            'description': self.description,
            'performance_score': self.performance_score,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'usage_count': self.usage_count,
            'success_rate': self.success_rate
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DSLRule':
        """딕셔너리에서 생성"""
        rule = cls(
            rule_id=data['rule_id'],
            rule_type=data['rule_type'],
            pattern=data['pattern'],
            replacement=data.get('replacement', ''),
            priority=data.get('priority', 0),
            enabled=data.get('enabled', True),
            description=data.get('description', ''),
            performance_score=data.get('performance_score', 0.0)
        )
        rule.created_at = data.get('created_at', rule.created_at)
        rule.updated_at = data.get('updated_at', rule.updated_at)
        rule.usage_count = data.get('usage_count', 0)
        rule.success_rate = data.get('success_rate', 0.0)
        return rule


class DSLRuleManager:
    """DSL 규칙 관리자 - MongoDB 전용"""
    
    def __init__(self):
        self.rules: Dict[str, DSLRule] = {}
        self.version = "1.0.0"
        self.collection_name = "dsl_rules"
        self.load_rules()
    
    def load_rules(self):
        """MongoDB에서 규칙 로드"""
        try:
            # MongoDB에서 로드 시도
            if self._load_from_mongodb():
                logger.info(f"DSL 규칙 MongoDB 로드 완료: {len(self.rules)}개 규칙 (버전 {self.version})")
                return
            else:
                logger.info("MongoDB에 기존 규칙 없음, 기본 규칙 생성...")
                # 기본 규칙 생성
                self._create_default_rules()
                self.save_rules()
                logger.info("기본 DSL 규칙 생성 완료")
        except Exception as e:
            logger.error(f"DSL 규칙 로드 실패: {e}")
            self._create_default_rules()
    
    def _load_from_mongodb(self) -> bool:
        """MongoDB에서 규칙 로드"""
        try:
            from app.core.database import db_manager
            
            collection = db_manager.get_collection(self.collection_name)
            if collection is None:
                return False
            
            # 최신 버전의 규칙 조회
            import asyncio
            
            async def load_async():
                cursor = collection.find().sort("updated_at", -1).limit(1)
                documents = await cursor.to_list(length=1)
                return documents
            
            # 동기 함수에서 비동기 호출
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            documents = loop.run_until_complete(load_async())
            
            if documents:
                data = documents[0]
                self.version = data.get('version', '1.0.0')
                rules_data = data.get('rules', [])
                
                self.rules.clear()
                for rule_data in rules_data:
                    rule = DSLRule.from_dict(rule_data)
                    self.rules[rule.rule_id] = rule
                
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"MongoDB에서 규칙 로드 실패: {e}")
            return False
    
    def _create_default_rules(self):
        """기본 규칙 생성"""
        default_rules = [
            # 노이즈 제거 규칙
            DSLRule(
                rule_id="ui_noise_removal",
                rule_type="noise_removal",
                pattern=r'판례상세\s*저장\s*인쇄\s*보관\s*전자팩스\s*공유\s*화면내\s*검색\s*조회\s*닫기',
                replacement="",
                priority=100,
                description="UI 메뉴 노이즈 제거"
            ),
            DSLRule(
                rule_id="case_info_noise_removal",
                rule_type="noise_removal",
                pattern=r'재판경과\s*.*?\s*참조판례\s*\d+\s*건\s*인용판례\s*\d+\s*건',
                replacement="",
                priority=95,
                description="재판경과 메타데이터 제거"
            ),
            DSLRule(
                rule_id="similar_docs_removal",
                rule_type="noise_removal",
                pattern=r'유사문서\s*\d+\s*건.*?태그\s*클라우드.*?닫기',
                replacement="",
                priority=90,
                description="유사문서 섹션 제거"
            ),
            DSLRule(
                rule_id="tags_removal",
                rule_type="noise_removal",
                pattern=r'#\w+(?:\s*#\w+)*',
                replacement="",
                priority=85,
                description="태그 제거"
            ),
            
            # 법리 필터링 규칙
            DSLRule(
                rule_id="judgment_expressions_filter",
                rule_type="legal_filtering",
                pattern=r'타당하다|정당하다|부당하다|볼\s*수\s*없다|보아야\s*한다|인정된다|판단된다|라\s*할\s*것',
                replacement="",
                priority=80,
                description="판단 표현 필터링"
            ),
            DSLRule(
                rule_id="legal_reasoning_filter",
                rule_type="legal_filtering",
                pattern=r'관련\s*법리|법리|대법원.*선고.*판결|판시',
                replacement="",
                priority=75,
                description="법리 관련 문장 필터링"
            ),
            DSLRule(
                rule_id="conclusion_filter",
                rule_type="legal_filtering",
                pattern=r'^주\s*문|^이유|^판단|청구.*(?:기각|인용|각하)',
                replacement="",
                priority=70,
                description="결론 섹션 필터링"
            ),
            
            # 사실 추출 규칙
            DSLRule(
                rule_id="date_extraction",
                rule_type="fact_extraction",
                pattern=r'\d{4}[.\-/년]\s*\d{1,2}[.\-/월]\s*\d{1,2}[.\-/일]?[^.]*[.]',
                replacement="",
                priority=60,
                description="날짜 포함 문장 추출"
            ),
            DSLRule(
                rule_id="amount_extraction",
                rule_type="fact_extraction",
                pattern=r'[^.]*\d{1,3}(?:,\d{3})*(?:원|만원|억원)[^.]*[.]',
                replacement="",
                priority=55,
                description="금액 포함 문장 추출"
            ),
            DSLRule(
                rule_id="party_action_extraction",
                rule_type="fact_extraction",
                pattern=r'[^.]*(?:원고|피고|신청인|피신청인).*?(?:계약|출원|등록|양도|부과|통지|제기)[^.]*[.]',
                replacement="",
                priority=50,
                description="당사자 행위 문장 추출"
            )
        ]
        
        for rule in default_rules:
            self.rules[rule.rule_id] = rule
    
    def save_rules(self):
        """MongoDB에 규칙 저장"""
        try:
            # 데이터 구성
            data = {
                'version': self.version,
                'updated_at': datetime.now().isoformat(),
                'rules': [rule.to_dict() for rule in self.rules.values()]
            }
            
            # MongoDB에 저장
            if self._save_to_mongodb(data):
                logger.info(f"DSL 규칙 MongoDB 저장 완료: {len(self.rules)}개 규칙")
                return True
            else:
                logger.error("MongoDB 저장 실패!")
                return False
            
        except Exception as e:
            logger.error(f"DSL 규칙 저장 실패: {e}")
            return False
    
    def _save_to_mongodb(self, data: Dict[str, Any] = None) -> bool:
        """MongoDB에 규칙 저장"""
        try:
            from app.core.database import db_manager
            
            collection = db_manager.get_collection(self.collection_name)
            if collection is None:
                return False
            
            if data is None:
                data = {
                    'version': self.version,
                    'updated_at': datetime.now().isoformat(),
                    'rules': [rule.to_dict() for rule in self.rules.values()]
                }
            
            # 비동기 저장
            import asyncio
            
            async def save_async():
                # 기존 규칙 삭제 후 새로 저장 (upsert)
                await collection.delete_many({})  # 기존 규칙 모두 삭제
                result = await collection.insert_one(data)
                return result.inserted_id is not None
            
            # 동기 함수에서 비동기 호출
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            success = loop.run_until_complete(save_async())
            return success
            
        except Exception as e:
            logger.error(f"MongoDB에 규칙 저장 실패: {e}")
            return False
    
    def add_rule(self, rule: DSLRule) -> bool:
        """규칙 추가"""
        try:
            print(f"🔧 DEBUG: DSL 규칙 추가 시도 - ID: {rule.rule_id}")
            print(f"🔧 DEBUG: 규칙 패턴: {rule.pattern}")
            print(f"🔧 DEBUG: 규칙 타입: {rule.rule_type}")
            
            self.rules[rule.rule_id] = rule
            print(f"🔧 DEBUG: 메모리에 규칙 추가 완료, 총 {len(self.rules)}개 규칙")
            
            save_result = self.save_rules()
            print(f"🔧 DEBUG: MongoDB 저장 결과: {save_result}")
            
            if save_result:
                logger.info(f"규칙 추가: {rule.rule_id}")
                return True
            else:
                print(f"🔧 ERROR: MongoDB 저장 실패, 메모리에서 규칙 제거")
                del self.rules[rule.rule_id]  # 저장 실패시 메모리에서도 제거
                return False
        except Exception as e:
            print(f"🔧 ERROR: 규칙 추가 실패 - {rule.rule_id}: {e}")
            logger.error(f"규칙 추가 실패 {rule.rule_id}: {e}")
            return False
    
    def update_rule(self, rule_id: str, **kwargs) -> bool:
        """규칙 업데이트"""
        try:
            if rule_id in self.rules:
                rule = self.rules[rule_id]
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                rule.updated_at = datetime.now().isoformat()
                self.save_rules()
                logger.info(f"규칙 업데이트: {rule_id}")
                return True
            else:
                logger.warning(f"규칙 없음: {rule_id}")
                return False
        except Exception as e:
            logger.error(f"규칙 업데이트 실패 {rule_id}: {e}")
            return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """규칙 비활성화"""
        return self.update_rule(rule_id, enabled=False)
    
    def enable_rule(self, rule_id: str) -> bool:
        """규칙 활성화"""
        return self.update_rule(rule_id, enabled=True)
    
    def get_rules_by_type(self, rule_type: str) -> List[DSLRule]:
        """타입별 규칙 조회"""
        return [rule for rule in self.rules.values() 
                if rule.rule_type == rule_type and rule.enabled]
    
    def get_sorted_rules(self) -> List[DSLRule]:
        """우선순위 순으로 정렬된 규칙 조회"""
        return sorted([rule for rule in self.rules.values() if rule.enabled],
                     key=lambda x: x.priority, reverse=True)
    
    def apply_rules(self, text: str, rule_types: Optional[List[str]] = None) -> Tuple[str, Dict[str, Any]]:
        """규칙들을 텍스트에 적용"""
        result_text = text
        applied_rules = []
        stats = {
            'original_length': len(text),
            'applied_rule_count': 0,
            'rule_types': {}
        }
        
        # 적용할 규칙 필터링
        if rule_types:
            rules_to_apply = []
            for rule_type in rule_types:
                rules_to_apply.extend(self.get_rules_by_type(rule_type))
            rules_to_apply.sort(key=lambda x: x.priority, reverse=True)
        else:
            rules_to_apply = self.get_sorted_rules()
        
        # 규칙 적용
        for rule in rules_to_apply:
            try:
                new_text, applied = rule.apply(result_text)
                if applied:
                    applied_rules.append({
                        'rule_id': rule.rule_id,
                        'rule_type': rule.rule_type,
                        'description': rule.description,
                        'length_before': len(result_text),
                        'length_after': len(new_text)
                    })
                    result_text = new_text
                    stats['applied_rule_count'] += 1
                    
                    # 타입별 통계
                    if rule.rule_type not in stats['rule_types']:
                        stats['rule_types'][rule.rule_type] = 0
                    stats['rule_types'][rule.rule_type] += 1
                    
            except Exception as e:
                logger.error(f"규칙 적용 오류 {rule.rule_id}: {e}")
        
        stats['final_length'] = len(result_text)
        stats['reduction_rate'] = (stats['original_length'] - stats['final_length']) / stats['original_length']
        
        return result_text, {
            'applied_rules': applied_rules,
            'stats': stats
        }
    
    def get_performance_report(self) -> Dict[str, Any]:
        """성능 리포트 생성"""
        total_rules = len(self.rules)
        enabled_rules = len([r for r in self.rules.values() if r.enabled])
        disabled_rules = total_rules - enabled_rules
        
        # 규칙 유형별 개수 계산 (UI에서 기대하는 형식)
        rules_by_type = {}
        type_stats = {}
        
        for rule in self.rules.values():
            rule_type = rule.rule_type
            
            # 단순 개수 (UI용)
            if rule_type not in rules_by_type:
                rules_by_type[rule_type] = 0
            rules_by_type[rule_type] += 1
            
            # 상세 통계 (분석용)
            if rule_type not in type_stats:
                type_stats[rule_type] = {
                    'count': 0,
                    'enabled': 0,
                    'avg_usage': 0,
                    'avg_performance': 0
                }
            type_stats[rule_type]['count'] += 1
            if rule.enabled:
                type_stats[rule_type]['enabled'] += 1
            type_stats[rule_type]['avg_usage'] += rule.usage_count
            type_stats[rule_type]['avg_performance'] += rule.performance_score
        
        # 평균 계산
        for stats in type_stats.values():
            if stats['count'] > 0:
                stats['avg_usage'] /= stats['count']
                stats['avg_performance'] /= stats['count']
        
        return {
            'version': self.version,
            'total_rules': total_rules,
            'enabled_rules': enabled_rules,
            'disabled_rules': disabled_rules,
            'rules_by_type': rules_by_type,  # UI에서 사용
            'type_stats': type_stats,        # 상세 분석용
            'updated_at': datetime.now().isoformat()
        }


# 전역 인스턴스
dsl_manager = DSLRuleManager()
