"""
규칙 DSL 엔진 및 자동 패치 시스템
"""
import re
import json
import hashlib
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RuleType(str, Enum):
    """규칙 유형"""
    PAGE_NUMBER_REMOVAL = "page_number_removal"
    HEADER_FOOTER_REMOVAL = "header_footer_removal"
    SEPARATOR_REMOVAL = "separator_removal"
    WHITESPACE_NORMALIZATION = "whitespace_normalization"
    DUPLICATE_REMOVAL = "duplicate_removal"
    SECTION_SYNONYM = "section_synonym"
    REFERENCE_CLEANUP = "reference_cleanup"


@dataclass
class RuleDefinition:
    """규칙 정의"""
    rule_id: str
    rule_type: RuleType
    pattern: str
    replacement: str
    description: str
    priority: int = 0
    enabled: bool = True
    conditions: Optional[Dict[str, Any]] = None


class DSLEngine:
    """DSL 엔진"""
    
    def __init__(self):
        self.rules: List[RuleDefinition] = []
        self.whitelist_patterns = self._load_whitelist()
    
    def _load_whitelist(self) -> List[str]:
        """화이트리스트 패턴 로드"""
        return [
            r"페이지\s*\d+",  # 페이지번호
            r"^\s*[-=]+\s*$",  # 구분선
            r"^\s*\d+\s*$",  # 단독 숫자
            r"법원.*제.*호",  # 법원 제호
            r"\s{2,}",  # 연속 공백
            r"\n{2,}",  # 연속 줄바꿈
        ]
    
    def load_rules_from_dsl(self, dsl_content: str) -> None:
        """DSL 내용으로부터 규칙 로드"""
        try:
            rules_data = json.loads(dsl_content)
            self.rules = []
            
            for rule_data in rules_data.get("rules", []):
                rule = RuleDefinition(
                    rule_id=rule_data["rule_id"],
                    rule_type=RuleType(rule_data["rule_type"]),
                    pattern=rule_data["pattern"],
                    replacement=rule_data.get("replacement", ""),
                    description=rule_data["description"],
                    priority=rule_data.get("priority", 0),
                    enabled=rule_data.get("enabled", True),
                    conditions=rule_data.get("conditions")
                )
                self.rules.append(rule)
            
            # 우선순위별 정렬
            self.rules.sort(key=lambda x: x.priority, reverse=True)
            
        except Exception as e:
            logger.error(f"Failed to load DSL rules: {e}")
            raise
    
    def apply_rules(self, content: str, case_metadata: Optional[Dict[str, Any]] = None) -> Tuple[str, List[str]]:
        """규칙 적용"""
        processed_content = content
        applied_rules = []
        
        for rule in self.rules:
            if not rule.enabled:
                continue
            
            # 조건 검사
            if rule.conditions and case_metadata:
                if not self._check_conditions(rule.conditions, case_metadata):
                    continue
            
            try:
                # 패턴 적용
                if rule.rule_type == RuleType.PAGE_NUMBER_REMOVAL:
                    processed_content, changed = self._apply_page_number_removal(processed_content, rule)
                elif rule.rule_type == RuleType.HEADER_FOOTER_REMOVAL:
                    processed_content, changed = self._apply_header_footer_removal(processed_content, rule)
                elif rule.rule_type == RuleType.SEPARATOR_REMOVAL:
                    processed_content, changed = self._apply_separator_removal(processed_content, rule)
                elif rule.rule_type == RuleType.WHITESPACE_NORMALIZATION:
                    processed_content, changed = self._apply_whitespace_normalization(processed_content, rule)
                elif rule.rule_type == RuleType.DUPLICATE_REMOVAL:
                    processed_content, changed = self._apply_duplicate_removal(processed_content, rule)
                elif rule.rule_type == RuleType.SECTION_SYNONYM:
                    processed_content, changed = self._apply_section_synonym(processed_content, rule)
                elif rule.rule_type == RuleType.REFERENCE_CLEANUP:
                    processed_content, changed = self._apply_reference_cleanup(processed_content, rule)
                else:
                    # 기본 정규식 적용
                    new_content = re.sub(rule.pattern, rule.replacement, processed_content)
                    changed = new_content != processed_content
                    processed_content = new_content
                
                if changed:
                    applied_rules.append(rule.rule_id)
                    
            except Exception as e:
                logger.warning(f"Failed to apply rule {rule.rule_id}: {e}")
        
        return processed_content, applied_rules
    
    def _check_conditions(self, conditions: Dict[str, Any], metadata: Dict[str, Any]) -> bool:
        """조건 검사"""
        for key, expected_value in conditions.items():
            if key not in metadata:
                return False
            
            actual_value = metadata[key]
            
            if isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            elif isinstance(expected_value, dict):
                # 범위 조건 등
                if "min" in expected_value and actual_value < expected_value["min"]:
                    return False
                if "max" in expected_value and actual_value > expected_value["max"]:
                    return False
            else:
                if actual_value != expected_value:
                    return False
        
        return True
    
    def _apply_page_number_removal(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """페이지번호 제거"""
        original_content = content
        content = re.sub(rule.pattern, rule.replacement, content, flags=re.MULTILINE)
        return content, content != original_content
    
    def _apply_header_footer_removal(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """머리글/바닥글 제거"""
        lines = content.split('\n')
        filtered_lines = []
        
        for line in lines:
            if not re.match(rule.pattern, line.strip()):
                filtered_lines.append(line)
        
        new_content = '\n'.join(filtered_lines)
        return new_content, new_content != content
    
    def _apply_separator_removal(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """구분선 제거"""
        original_content = content
        content = re.sub(rule.pattern, rule.replacement, content, flags=re.MULTILINE)
        return content, content != original_content
    
    def _apply_whitespace_normalization(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """공백 정규화"""
        original_content = content
        # 연속 공백을 단일 공백으로
        content = re.sub(r'\s+', ' ', content)
        # 연속 줄바꿈을 최대 2개로
        content = re.sub(r'\n{3,}', '\n\n', content)
        return content, content != original_content
    
    def _apply_duplicate_removal(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """중복 제거"""
        lines = content.split('\n')
        seen = set()
        filtered_lines = []
        
        for line in lines:
            line_hash = hashlib.md5(line.strip().encode()).hexdigest()
            if line_hash not in seen:
                seen.add(line_hash)
                filtered_lines.append(line)
        
        new_content = '\n'.join(filtered_lines)
        return new_content, new_content != content
    
    def _apply_section_synonym(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """섹션 동의어 처리"""
        original_content = content
        content = re.sub(rule.pattern, rule.replacement, content)
        return content, content != original_content
    
    def _apply_reference_cleanup(self, content: str, rule: RuleDefinition) -> Tuple[str, bool]:
        """참조 정리"""
        original_content = content
        content = re.sub(rule.pattern, rule.replacement, content)
        return content, content != original_content
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """규칙 요약"""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": len([r for r in self.rules if r.enabled]),
            "rule_types": {
                rule_type.value: len([r for r in self.rules if r.rule_type == rule_type])
                for rule_type in RuleType
            }
        }


class AutoPatcher:
    """자동 패치 시스템"""
    
    def __init__(self, dsl_engine: DSLEngine):
        self.dsl_engine = dsl_engine
        self.patch_history: List[Dict[str, Any]] = []
        self.oscillation_tracker: Dict[str, List[datetime]] = {}
    
    async def analyze_failures(self, failure_patterns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """실패 패턴 분석 및 패치 제안"""
        patch_suggestions = []
        
        for pattern in failure_patterns:
            error_type = self._classify_error(pattern["_id"])
            
            if error_type:
                suggestion = await self._generate_patch_suggestion(error_type, pattern)
                if suggestion:
                    patch_suggestions.append(suggestion)
        
        return patch_suggestions
    
    def _classify_error(self, error_message: str) -> Optional[str]:
        """오류 분류"""
        error_patterns = {
            "page_number": [r"페이지\s*\d+", r"page\s*\d+"],
            "separator": [r"[-=]{3,}", r"구분선"],
            "header_footer": [r"법원", r"제.*호"],
            "whitespace": [r"\s{2,}", r"공백"],
            "reference": [r"참조", r"조문", r"항"],
        }
        
        for error_type, patterns in error_patterns.items():
            for pattern in patterns:
                if re.search(pattern, error_message, re.IGNORECASE):
                    return error_type
        
        return None
    
    async def _generate_patch_suggestion(self, error_type: str, pattern_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """패치 제안 생성"""
        error_count = pattern_data["count"]
        sample_cases = pattern_data["sample_cases"]
        
        # 최소 임계값 확인
        if error_count < 3:
            return None
        
        # 패치 생성
        patch_id = f"auto_patch_{error_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        if error_type == "page_number":
            return {
                "patch_id": patch_id,
                "rule_type": RuleType.PAGE_NUMBER_REMOVAL.value,
                "description": f"페이지번호 제거 규칙 개선 (실패 {error_count}건)",
                "pattern": r"(?:^|\n)\s*(?:페이지|page)\s*\d+\s*(?:\n|$)",
                "replacement": "\n",
                "confidence_score": min(0.9, error_count / 10),
                "applicable_cases": sample_cases[:5]
            }
        elif error_type == "separator":
            return {
                "patch_id": patch_id,
                "rule_type": RuleType.SEPARATOR_REMOVAL.value,
                "description": f"구분선 제거 규칙 개선 (실패 {error_count}건)",
                "pattern": r"(?:^|\n)\s*[-=]{3,}\s*(?:\n|$)",
                "replacement": "\n",
                "confidence_score": min(0.85, error_count / 15),
                "applicable_cases": sample_cases[:5]
            }
        elif error_type == "header_footer":
            return {
                "patch_id": patch_id,
                "rule_type": RuleType.HEADER_FOOTER_REMOVAL.value,
                "description": f"머리글/바닥글 제거 규칙 개선 (실패 {error_count}건)",
                "pattern": r"(?:^|\n)\s*(?:법원|제\s*\d+\s*호).*?(?:\n|$)",
                "replacement": "\n",
                "confidence_score": min(0.8, error_count / 20),
                "applicable_cases": sample_cases[:5]
            }
        
        return None
    
    def apply_patch(self, patch: Dict[str, Any], current_rules: str) -> str:
        """패치 적용"""
        try:
            rules_data = json.loads(current_rules)
            
            # 새 규칙 추가 또는 기존 규칙 수정
            new_rule = {
                "rule_id": patch["patch_id"],
                "rule_type": patch["rule_type"],
                "pattern": patch["pattern"],
                "replacement": patch.get("replacement", ""),
                "description": patch["description"],
                "priority": 100,  # 높은 우선순위
                "enabled": True,
                "auto_generated": True,
                "confidence_score": patch.get("confidence_score", 0.5)
            }
            
            rules_data["rules"].append(new_rule)
            
            # 패치 이력 저장
            self.patch_history.append({
                "patch_id": patch["patch_id"],
                "applied_at": datetime.now(),
                "patch_data": patch
            })
            
            return json.dumps(rules_data, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to apply patch {patch['patch_id']}: {e}")
            raise
    
    def check_oscillation(self, rule_area: str) -> bool:
        """오실레이션 검사"""
        now = datetime.now()
        
        if rule_area not in self.oscillation_tracker:
            self.oscillation_tracker[rule_area] = []
        
        # 최근 1시간 내 변경 횟수 확인
        recent_changes = [
            change_time for change_time in self.oscillation_tracker[rule_area]
            if (now - change_time).total_seconds() < 3600
        ]
        
        if len(recent_changes) >= 2:
            logger.warning(f"Oscillation detected in rule area: {rule_area}")
            return True
        
        self.oscillation_tracker[rule_area].append(now)
        return False
    
    def rollback_patch(self, patch_id: str, current_rules: str) -> str:
        """패치 롤백"""
        try:
            rules_data = json.loads(current_rules)
            
            # 해당 패치 규칙 제거
            rules_data["rules"] = [
                rule for rule in rules_data["rules"]
                if rule.get("rule_id") != patch_id
            ]
            
            return json.dumps(rules_data, indent=2, ensure_ascii=False)
            
        except Exception as e:
            logger.error(f"Failed to rollback patch {patch_id}: {e}")
            raise


class RulesVersionManager:
    """규칙 버전 관리자"""
    
    def __init__(self):
        self.current_version = "v1.0.0"
    
    def increment_version(self, version_type: str = "patch") -> str:
        """버전 증가"""
        try:
            # v1.2.3 형태에서 숫자 추출
            version_parts = self.current_version[1:].split('.')
            major, minor, patch = map(int, version_parts)
            
            if version_type == "major":
                major += 1
                minor = 0
                patch = 0
            elif version_type == "minor":
                minor += 1
                patch = 0
            else:  # patch
                patch += 1
            
            self.current_version = f"v{major}.{minor}.{patch}"
            return self.current_version
            
        except Exception as e:
            logger.error(f"Failed to increment version: {e}")
            return self.current_version
    
    def create_version_tag(self, rules_content: str, description: str) -> Dict[str, Any]:
        """버전 태그 생성"""
        return {
            "version": self.current_version,
            "description": description,
            "rules_content": rules_content,
            "created_at": datetime.now(),
            "checksum": hashlib.sha256(rules_content.encode()).hexdigest()
        }
