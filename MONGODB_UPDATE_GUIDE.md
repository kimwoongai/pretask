# MongoDB Atlas 규칙 업데이트 가이드

## 📋 업데이트 순서

### 1. 기본 규칙 업데이트 (dsl_rules 컬렉션)

**컬렉션**: `dsl_rules`  
**문서 ID**: `68a58cea3c9a110dddf6c28f`

1. MongoDB Atlas에 로그인
2. `legal_db` 데이터베이스 선택
3. `dsl_rules` 컬렉션 선택
4. 문서 ID `68a58cea3c9a110dddf6c28f` 찾기
5. **전체 문서를 `mongodb_rules_data.json` 내용으로 교체**

### 2. 추가 개별 규칙 삽입 (dsl_rules_individual 컬렉션)

**컬렉션**: `dsl_rules_individual`

`mongodb_additional_rules.json` 파일의 각 규칙을 개별 문서로 삽입:

1. `dsl_rules_individual` 컬렉션 선택
2. "Insert Document" 클릭
3. 각 규칙을 하나씩 삽입:

```json
{
  "_id": "ai_noise_removal_684eb04e7bceb320096d8c7c_34",
  "rule_id": "ai_noise_removal_684eb04e7bceb320096d8c7c_34",
  "rule_type": "noise_removal",
  "pattern": "본 판례는 법제처에서 제공하는 자료로, 웹 페이지에서 직접 확인하시는 것이 좋습니다\\. 참조 URL: http://www\\.law.*",
  "replacement": "",
  "priority": 98,
  "enabled": true,
  "description": "AI 제안: 참조 URL 및 안내 문구 제거",
  "performance_score": 0.95,
  "created_at": "2025-01-20T10:00:00.000000",
  "updated_at": "2025-01-20T10:00:00.000000",
  "usage_count": 0,
  "success_rate": 0
}
```

### 3. 위험한 규칙 제거

다음 규칙들이 있다면 **삭제**하거나 **enabled: false**로 설정:

- `ai_fact_retention_*` (모든 fact_retention 규칙)
- `consolidated_*` (모든 통합 규칙)
- 패턴이 `"당사자 정보, 사건 발생 경위..."` 같은 긴 치환 텍스트를 포함하는 규칙

### 4. 확인 방법

업데이트 후 서비스를 재시작하고 다음으로 확인:

1. 단건 처리 실행
2. `applied_rules` 배열이 비어있지 않은지 확인
3. `processed_content`가 원본과 다르게 정제되었는지 확인
4. 토큰 수가 비정상적으로 증가하지 않았는지 확인

## 🎯 예상 결과

**업데이트 전:**
- `applied_rules: []` (빈 배열)
- 원본과 처리 결과 동일

**업데이트 후:**
- `applied_rules: ["ui_elements_removal", "legal_judgment_removal", ...]` (규칙 적용됨)
- UI 요소, 법적 판단, 절차적 설명 등이 제거된 깔끔한 결과

## ⚠️ 주의사항

1. **백업**: 기존 데이터 백업 후 진행
2. **테스트**: 업데이트 후 반드시 단건 처리로 테스트
3. **모니터링**: 처리 결과가 비정상적이면 즉시 롤백
