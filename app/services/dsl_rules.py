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
                # 사실 추출 규칙 (2단계에서 사용 예정 - 현재는 비활성화)
                # matches = re.findall(self.pattern, text, flags=re.DOTALL | re.IGNORECASE)
                # if matches:
                #     new_text = ' '.join(matches)
                #     applied = True
                # else:
                #     new_text = text
                #     applied = False
                # 1단계에서는 사실 추출 규칙 적용하지 않음
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
        """MongoDB에서 규칙 로드 (동기식 클라이언트 사용)"""
        try:
            print(f"🔧 DEBUG: MongoDB 기본 규칙 로드 시작...")
            
            # 동기식 pymongo 클라이언트 사용
            import pymongo
            import os
            
            mongodb_url = os.getenv('MONGODB_URL')
            if not mongodb_url:
                print(f"🔧 ERROR: MONGODB_URL 환경변수가 없음")
                return False
            
            print(f"🔧 DEBUG: 동기식 MongoDB 클라이언트 연결 시도...")
            
            # 동기식 클라이언트로 직접 연결
            client = pymongo.MongoClient(mongodb_url)
            db = client[os.getenv('MONGODB_DB', 'legal_db')]
            collection = db[self.collection_name]
            
            print(f"🔧 DEBUG: 기본 규칙 컬렉션 연결 성공: {self.collection_name}")
            
            # 최신 버전의 규칙 조회
            documents = list(collection.find().sort("updated_at", -1).limit(1))
            
            print(f"🔧 DEBUG: 기본 규칙 문서 조회 결과: {len(documents)}개")
            
            if documents:
                data = documents[0]
                self.version = data.get('version', '1.0.0')
                rules_data = data.get('rules', [])
                
                self.rules.clear()
                for rule_data in rules_data:
                    rule = DSLRule.from_dict(rule_data)
                    self.rules[rule.rule_id] = rule
                
                print(f"🔧 DEBUG: 기본 규칙 로드 완료: {len(self.rules)}개")
                
                # 개별 규칙들도 로드
                individual_count = self._load_individual_rules_from_mongodb()
                print(f"🔧 DEBUG: 개별 규칙 로드 완료: {individual_count}개")
                
                # 연결 종료
                client.close()
                return True
            else:
                print(f"🔧 DEBUG: 기본 규칙 문서 없음")
                # 기본 규칙이 없어도 개별 규칙은 로드 시도
                individual_count = self._load_individual_rules_from_mongodb()
                print(f"🔧 DEBUG: 기본 규칙 없음, 개별 규칙만 로드: {individual_count}개")
                
                # 연결 종료
                client.close()
                return individual_count > 0
            
        except Exception as e:
            print(f"🔧 ERROR: MongoDB 기본 규칙 로드 실패: {e}")
            logger.error(f"MongoDB에서 규칙 로드 실패: {e}")
            return False
    
    def _create_default_rules(self):
        """기본 규칙 생성 (AI 제안 규칙들 통합)"""
        default_rules = [
            # 최고 우선순위: UI 요소 제거
            DSLRule(
                rule_id="ui_elements_removal",
                rule_type="noise_removal",
                pattern=r'판례상세 저장 인쇄 보관 전자팩스 공유 화면내 검색 조회 닫기|PDF로 보기|Tip[0-9]+\.',
                replacement="",
                priority=100,
                description="UI 요소와 시스템 메뉴 제거"
            ),
            
            # 법적 판단 및 결론 제거 (legal_filtering)
            DSLRule(
                rule_id="legal_judgment_removal",
                rule_type="legal_filtering", 
                pattern=r'따라서.*?판단한다|그러므로.*?인정된다|결론적으로.*?본다',
                replacement="",
                priority=97,
                description="법적 판단 결론 제거"
            ),
            DSLRule(
                rule_id="legal_sections_removal",
                rule_type="legal_filtering",
                pattern=r'【판결요지】.*?【판례내용】|【주 문】.*?【이 유】|【판시사항】.*?【판결요지】',
                replacement="",
                priority=99,
                description="법적 판단 섹션 제거"
            ),
            DSLRule(
                rule_id="legal_reasoning_removal",
                rule_type="legal_filtering",
                pattern=r'법리상.*?해석|법적으로.*?판단|이 법원은.*?본다',
                replacement="",
                priority=93,
                description="법리 해석 내용 제거"
            ),
            
            # 절차적 설명 제거 (noise_removal)
            DSLRule(
                rule_id="procedural_info_removal",
                rule_type="noise_removal",
                pattern=r'변론 종결|심리 종결|증거 조사|판결 선고|변론.*?진행|심리.*?완료',
                replacement="",
                priority=95,
                description="절차적 설명 제거"
            ),
            DSLRule(
                rule_id="court_process_removal", 
                rule_type="noise_removal",
                pattern=r'【원심판결】.*?선고|상고를 기각한다.*?부담으로 한다|【변론종결】.*?【청구취지】',
                replacement="",
                priority=92,
                description="법원 절차 설명 제거"
            ),
            DSLRule(
                rule_id="case_parties_removal",
                rule_type="noise_removal", 
                pattern=r'【원고, 상고인】.*?【피고, 피상고인】|【원심판결】.*?선고|【원 고】 【피 고】.*',
                replacement="",
                priority=87,
                description="당사자 표시 정보 제거"
            ),
            
            # 중복 표시 정보 제거 (redundancy_removal)
            DSLRule(
                rule_id="case_metadata_removal",
                rule_type="redundancy_removal",
                pattern=r'재판경과.*?\d{4}\.\d{2}\.\d{2}\.|참조판례 \d+ 건|인용판례 \d+ 건',
                replacement="",
                priority=89,
                description="재판 경과 및 참조 정보 제거"
            ),
            DSLRule(
                rule_id="court_info_removal",
                rule_type="redundancy_removal",
                pattern=r'제1심.*?제2심.*?선고|법원 유형:.*?사건 유형:|【연관판결】.*?2심',
                replacement="",
                priority=85,
                description="법원 정보 중복 제거"
            ),
            
            # 구조적 노이즈 제거
            DSLRule(
                rule_id="structural_noise_removal",
                rule_type="noise_removal",
                pattern=r'【판례내용】|【청구취지】|【판시사항】|\[\d+\]|페이지 [0-9]+|-----',
                replacement="",
                priority=84,
                description="구조적 노이즈 제거"
            ),
            DSLRule(
                rule_id="case_number_removal",
                rule_type="noise_removal", 
                pattern=r'판례 [0-9]+',
                replacement="",
                priority=77,
                description="판례 번호 제거"
            ),
            
            # 참조 URL 및 안내 문구 제거 (새로 추가)
            DSLRule(
                rule_id="reference_url_removal",
                rule_type="noise_removal",
                pattern=r'본 판례는 법제처에서 제공하는 자료로, 웹 페이지에서 직접 확인하시는 것이 좋습니다\. 참조 URL: http://www\.law.*',
                replacement="",
                priority=95,
                description="참조 URL 및 안내 문구 제거"
            ),
            
            # 기타 노이즈 제거
            DSLRule(
                rule_id="misc_noise_removal",
                rule_type="noise_removal",
                pattern=r'변론 전체의 취지|인정근거 다툼 없는 사실|페이지 번호|구분선|법원명.*?반복|사건번호.*?반복',
                replacement="",
                priority=80,
                description="기타 노이즈 제거"
            )
        ]
        
        for rule in default_rules:
            self.rules[rule.rule_id] = rule
    
    def _load_individual_rules_from_mongodb(self) -> int:
        """개별 규칙 컬렉션에서 규칙들을 로드 (동기식)"""
        try:
            # 동기식 pymongo 클라이언트 사용
            import pymongo
            import os
            
            mongodb_url = os.getenv('MONGODB_URL')
            if not mongodb_url:
                print(f"🔧 DEBUG: MONGODB_URL 환경변수가 없음, 개별 규칙 로드 건너뜀")
                return 0
            
            print(f"🔧 DEBUG: 개별 규칙 로드를 위한 동기식 MongoDB 클라이언트 연결...")
            
            # 동기식 클라이언트로 직접 연결
            client = pymongo.MongoClient(mongodb_url)
            db = client[os.getenv('MONGODB_DB', 'legal_db')]
            collection = db['dsl_rules_individual']
            
            # 모든 개별 규칙 로드
            documents = list(collection.find({}))
            
            print(f"🔧 DEBUG: 개별 규칙 문서 {len(documents)}개 발견")
            
            count = 0
            for doc in documents:
                try:
                    # _id를 rule_id로 변환
                    if '_id' in doc:
                        doc['rule_id'] = doc['_id']
                        del doc['_id']
                    
                    rule = DSLRule.from_dict(doc)
                    self.rules[rule.rule_id] = rule
                    count += 1
                    print(f"🔧 DEBUG: 개별 규칙 로드 성공 - {rule.rule_id}")
                except Exception as e:
                    print(f"🔧 WARNING: 개별 규칙 로드 실패 - {doc.get('rule_id', 'unknown')}: {e}")
                    continue
            
            # 연결 종료
            client.close()
            
            return count
            
        except Exception as e:
            print(f"🔧 ERROR: 개별 규칙 로드 오류: {e}")
            logger.error(f"개별 규칙 로드 실패: {e}")
            return 0
    
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
            print(f"🔧 DEBUG: MongoDB 저장 시작 - 컬렉션: {self.collection_name}")
            
            from app.core.database import db_manager
            
            collection = db_manager.get_collection(self.collection_name)
            print(f"🔧 DEBUG: 컬렉션 객체: {collection}")
            
            if collection is None:
                print(f"🔧 ERROR: 컬렉션을 가져올 수 없음: {self.collection_name}")
                return False
            
            if data is None:
                data = {
                    'version': self.version,
                    'updated_at': datetime.now().isoformat(),
                    'rules': [rule.to_dict() for rule in self.rules.values()]
                }
            
            print(f"🔧 DEBUG: 저장할 데이터 준비 완료 - 버전: {data['version']}, 규칙 수: {len(data['rules'])}")
            
            # 비동기 저장
            import asyncio
            
            async def save_async():
                try:
                    print(f"🔧 DEBUG: 비동기 저장 시작...")
                    
                    # 기존 규칙 삭제 후 새로 저장 (upsert)
                    delete_result = await collection.delete_many({})
                    print(f"🔧 DEBUG: 기존 규칙 삭제 완료 - 삭제된 문서 수: {delete_result.deleted_count}")
                    
                    result = await collection.insert_one(data)
                    print(f"🔧 DEBUG: 새 규칙 삽입 완료 - ID: {result.inserted_id}")
                    
                    return result.inserted_id is not None
                except Exception as e:
                    print(f"🔧 ERROR: 비동기 저장 중 오류: {e}")
                    return False
            
            # 동기 함수에서 비동기 호출
            try:
                print(f"🔧 DEBUG: 이벤트 루프 가져오기 시도...")
                loop = asyncio.get_event_loop()
                print(f"🔧 DEBUG: 기존 이벤트 루프 사용")
            except RuntimeError:
                print(f"🔧 DEBUG: 새 이벤트 루프 생성")
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            print(f"🔧 DEBUG: 비동기 함수 실행 시작...")
            success = loop.run_until_complete(save_async())
            print(f"🔧 DEBUG: 비동기 함수 실행 완료 - 결과: {success}")
            
            return success
            
        except Exception as e:
            print(f"🔧 ERROR: MongoDB 저장 최종 오류: {e}")
            logger.error(f"MongoDB에 규칙 저장 실패: {e}")
            return False
    
    def _save_single_rule_to_mongodb(self, rule: DSLRule) -> bool:
        """개별 규칙을 MongoDB에 저장 (동기식 클라이언트 사용)"""
        try:
            print(f"🔧 DEBUG: 개별 규칙 MongoDB 저장 시작 - ID: {rule.rule_id}")
            
            # 동기식 pymongo 클라이언트 사용
            import pymongo
            import os
            
            mongodb_url = os.getenv('MONGODB_URL')
            if not mongodb_url:
                print(f"🔧 ERROR: MONGODB_URL 환경변수가 없음")
                return False
            
            print(f"🔧 DEBUG: 동기식 MongoDB 클라이언트 연결 시도...")
            
            # 동기식 클라이언트로 직접 연결
            client = pymongo.MongoClient(mongodb_url)
            db = client[os.getenv('MONGODB_DB', 'legal_db')]
            collection = db['dsl_rules_individual']
            
            print(f"🔧 DEBUG: 동기식 컬렉션 연결 성공")
            
            # 규칙 데이터 준비
            rule_data = rule.to_dict()
            rule_data['_id'] = rule.rule_id  # rule_id를 MongoDB _id로 사용
            
            print(f"🔧 DEBUG: 개별 규칙 데이터 준비 완료 - ID: {rule.rule_id}")
            
            # 동기식 upsert 수행
            result = collection.replace_one(
                {"_id": rule.rule_id}, 
                rule_data, 
                upsert=True
            )
            
            print(f"🔧 DEBUG: 개별 규칙 저장 완료 - Matched: {result.matched_count}, Modified: {result.modified_count}, Upserted: {result.upserted_id}")
            
            # 연결 종료
            client.close()
            
            success = result.matched_count > 0 or result.upserted_id is not None
            print(f"🔧 DEBUG: 개별 규칙 저장 결과: {success}")
            
            return success
            
        except Exception as e:
            print(f"🔧 ERROR: 개별 규칙 저장 오류: {e}")
            logger.error(f"개별 규칙 MongoDB 저장 실패: {e}")
            return False
    
    def _reload_all_rules(self):
        """모든 규칙을 다시 로드 (기본 + 개별 규칙)"""
        try:
            print(f"🔧 DEBUG: 전체 규칙 다시 로드 시작...")
            
            # 현재 규칙 백업 (실패시 복구용)
            backup_rules = self.rules.copy()
            
            # 기본 규칙 다시 로드
            if self._load_from_mongodb():
                print(f"🔧 DEBUG: 기본 규칙 다시 로드 완료: {len(self.rules)}개")
            else:
                print(f"🔧 DEBUG: 기본 규칙 없음, 기본 규칙 생성")
                self._create_default_rules()
            
            # 개별 규칙 다시 로드
            individual_count = self._load_individual_rules_from_mongodb()
            print(f"🔧 DEBUG: 개별 규칙 다시 로드 완료: {individual_count}개")
            
            print(f"🔧 DEBUG: 전체 규칙 다시 로드 완료 - 총 {len(self.rules)}개 규칙")
            
        except Exception as e:
            print(f"🔧 ERROR: 규칙 다시 로드 실패: {e}")
            # 실패시 백업 복구
            self.rules = backup_rules
            logger.error(f"규칙 다시 로드 실패, 백업 복구: {e}")
    
    def _find_duplicate_rule(self, new_rule: DSLRule) -> Optional[DSLRule]:
        """중복 규칙 찾기 (동일한 패턴과 타입)"""
        for existing_rule in self.rules.values():
            if (existing_rule.rule_type == new_rule.rule_type and 
                existing_rule.pattern == new_rule.pattern):
                return existing_rule
        return None
    
    def add_rule(self, rule: DSLRule) -> bool:
        """규칙 추가 - 개별 규칙만 MongoDB에 추가/업데이트"""
        try:
            print(f"🔧 DEBUG: DSL 규칙 추가 시도 - ID: {rule.rule_id}")
            print(f"🔧 DEBUG: 규칙 패턴: {rule.pattern}")
            print(f"🔧 DEBUG: 규칙 타입: {rule.rule_type}")
            
            # 중복 규칙 확인
            existing_rule = self._find_duplicate_rule(rule)
            if existing_rule:
                print(f"🔧 WARNING: 중복 규칙 발견 - 기존: {existing_rule.rule_id}, 패턴: {existing_rule.pattern}")
                print(f"🔧 DEBUG: 중복 규칙이므로 추가하지 않음")
                return True  # 중복이지만 성공으로 처리 (이미 해당 규칙이 존재하므로)
            
            # 메모리에 규칙 추가
            self.rules[rule.rule_id] = rule
            print(f"🔧 DEBUG: 메모리에 규칙 추가 완료, 총 {len(self.rules)}개 규칙")
            
            # 개별 규칙만 MongoDB에 저장
            save_result = self._save_single_rule_to_mongodb(rule)
            print(f"🔧 DEBUG: MongoDB 개별 규칙 저장 결과: {save_result}")
            print(f"🔧 DEBUG: save_result 타입: {type(save_result)}, 값: {save_result}")
            
            if save_result is True:
                print(f"🔧 DEBUG: 저장 성공 확인됨, 자동 리로드 시작...")
                logger.info(f"규칙 추가: {rule.rule_id}")
                
                # 중요: 새 규칙 추가 후 전체 규칙을 다시 로드하여 메모리 동기화
                print(f"🔧 DEBUG: 새 규칙 추가 완료, 전체 규칙 다시 로드 중...")
                old_count = len(self.rules)
                print(f"🔧 DEBUG: 리로드 전 규칙 수: {old_count}")
                
                try:
                    self._reload_all_rules()
                    new_count = len(self.rules)
                    print(f"🔧 DEBUG: 규칙 다시 로드 완료 - {old_count}개 → {new_count}개")
                except Exception as reload_error:
                    print(f"🔧 ERROR: 규칙 리로드 실패: {reload_error}")
                
                return True
            else:
                print(f"🔧 ERROR: MongoDB 저장 실패 (save_result={save_result}), 메모리에서 규칙 제거")
                if rule.rule_id in self.rules:
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

