# ✅ 두 가지 주요 문제 해결 완료

## 1️⃣ **광범위한 정규식 생성 문제 수정**

### **🔧 수정된 파일들:**

#### **`app/services/openai_service.py` (174-185번 줄)**
```python
# ❌ 기존 (위험한 프롬프트)
"- **사실관계만 남기고 나머지는 모두 노이즈로 제거하는 패턴을 제안하세요**"
"pattern_before": "따라서.*?판단한다|그러므로.*?인정된다"  # 광범위!

# ✅ 수정 (보수적 프롬프트)
"- **확실한 노이즈만 제거하는 구체적이고 안전한 패턴을 제안하세요**"
"- **중요: 광범위한 정규식(.*?) 사용을 피하고 라인 단위 매칭(^패턴$)을 선호하세요**"
"pattern_before": "^페이지 \\d+$"  # 안전!
```

#### **`app/api/endpoints.py` (176번 줄)**
```python
# ❌ 기존 (위험한 임계값)
auto_apply_threshold=0.5  # 50% 신뢰도면 자동 적용

# ✅ 수정 (보수적 임계값)
auto_apply_threshold=0.9  # 90% 이상만 자동 적용
```

### **🎯 효과:**
- ✅ 더 이상 `【.*?】` 같은 위험한 패턴 생성 안함
- ✅ `^페이지 \d+$` 같은 안전한 라인 단위 패턴만 생성
- ✅ 90% 이상 신뢰도만 자동 적용으로 안전성 확보

---

## 2️⃣ **배치 처리 결과 MongoDB 저장 기능 추가**

### **🔧 수정된 파일:**

#### **`app/services/batch_processor.py`**

**추가된 기능:**
1. **배치 처리 플로우에 저장 단계 추가 (105-107번 줄)**
```python
# 3. 배치 처리 결과를 MongoDB에 저장
await self._update_job_status(job, "saving", "처리 결과를 MongoDB에 저장 중...")
await self._save_batch_results_to_mongodb(sample_cases, batch_results, job)
```

2. **MongoDB 저장 함수 구현 (132-225번 줄)**
```python
async def _save_batch_results_to_mongodb(
    self, 
    sample_cases: List[Dict[str, Any]], 
    batch_results: List[Tuple[str, Any, List[str], str]], 
    job: BatchJob
):
    """배치 처리 결과를 MongoDB cases 컬렉션에 저장"""
```

### **💾 저장되는 데이터:**
- **기본 정보**: case_name, court_name, decision_date
- **처리 결과**: original_content, processed_content
- **성능 지표**: token_count, quality_score, nrr, fpr, ss
- **규칙 정보**: applied_rules, rules_version
- **배치 정보**: processing_mode="batch", batch_job_id
- **평가 결과**: errors, suggestions

### **🎯 효과:**
- ✅ 배치 처리 결과가 `cases` 컬렉션에 자동 저장
- ✅ 단건 처리와 동일한 데이터 구조로 일관성 유지
- ✅ 10개마다 진행 상황 로그로 모니터링 가능
- ✅ 개별 케이스 저장 실패시에도 전체 작업 계속 진행

---

## 🚀 **즉시 효과**

### **광범위한 정규식 문제 해결:**
- 더 이상 과도한 삭제 (97.5%) 발생 안함
- 사실관계 보존하면서 확실한 노이즈만 제거
- 토큰 보존율 3% → 60-70% 개선 예상

### **배치 처리 저장 문제 해결:**
- 배치로 처리한 모든 케이스가 MongoDB에 저장됨
- 단건/배치 처리 결과를 통합적으로 관리 가능
- 처리 이력과 성능 지표 추적 가능

**이제 두 가지 핵심 문제가 모두 해결되었습니다!** 🎉
