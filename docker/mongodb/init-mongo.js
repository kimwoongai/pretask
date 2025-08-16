// MongoDB 초기화 스크립트
db = db.getSiblingDB('legal_db');

// 사용자 생성
db.createUser({
    user: 'app_user',
    pwd: 'app_password',
    roles: [
        {
            role: 'readWrite',
            db: 'legal_db'
        }
    ]
});

// 컬렉션 생성 및 인덱스 설정
db.createCollection('cases');  // 케이스 데이터 (원본 + 전처리)
db.createCollection('processed_precedents');  // 전처리된 데이터
db.createCollection('processing_results');  // 처리 결과 및 메트릭
db.createCollection('rules_versions');  // 규칙 버전
db.createCollection('batch_jobs');  // 배치 작업
db.createCollection('safety_gates');

// 인덱스 생성
// cases (케이스 데이터)
db.cases.createIndex({ "precedent_id": 1 }, { unique: true });
db.cases.createIndex({ "court_type": 1, "decision_date": 1 });
db.cases.createIndex({ "extraction_date": -1 });
db.cases.createIndex({ "processed_content": 1 });  // 전처리된 케이스 조회용

// processed_precedents (전처리된 데이터)
db.processed_precedents.createIndex({ "original_id": 1, "rules_version": 1 });
db.processed_precedents.createIndex({ "precedent_id": 1 });
db.processed_precedents.createIndex({ "rules_version": 1, "status": 1 });
db.processed_precedents.createIndex({ "created_at": -1 });

// processing_results (처리 결과)
db.processing_results.createIndex({ "original_id": 1, "rules_version": 1 });
db.processing_results.createIndex({ "created_at": -1 });

db.rules_versions.createIndex({ "version": 1 }, { unique: true });
db.rules_versions.createIndex({ "created_at": -1 });

db.batch_jobs.createIndex({ "job_id": 1 }, { unique: true });
db.batch_jobs.createIndex({ "status": 1 });

// 샘플 데이터 삽입 (개발용)
db.cases.insertMany([
    {
        precedent_id: "sample_001",
        case_name: "민사소송 샘플 케이스",
        case_number: "2023-민-001",
        court_name: "서울중앙지방법원",
        court_type: "지방법원",
        decision_date: "2023-12-15",
        referenced_laws: "민법 제1조",
        content: "법원 판결문 샘플 내용입니다. 페이지 1\n\n본 사건은...\n\n---구분선---\n\n결론적으로...",
        content_length: 200,
        doc_type: "main",
        extraction_date: "2024-01-01",
        source_type: "court",
        source_url: "https://example.com/sample_001"
    },
    {
        precedent_id: "sample_002",
        case_name: "형사재판 샘플 케이스",
        case_number: "2023-형-002", 
        court_name: "서울고등법원",
        court_type: "고등법원",
        decision_date: "2023-11-20",
        referenced_laws: "형법 제1조",
        content: "형사 판결문 샘플입니다. 페이지 2\n\n피고인은...\n\n========\n\n판결 주문...",
        content_length: 180,
        doc_type: "main",
        extraction_date: "2024-01-01",
        source_type: "court",
        source_url: "https://example.com/sample_002"
    },
    {
        precedent_id: "sample_003",
        case_name: "행정소송 샘플 케이스",
        case_number: "2024-행-003",
        court_name: "서울행정법원",
        court_type: "행정법원",
        decision_date: "2024-01-10",
        referenced_laws: "행정소송법 제1조",
        content: "행정 소송 판결문입니다. 페이지 3\n\n원고의 주장...\n\n-----------\n\n법원의 판단...",
        content_length: 220,
        doc_type: "main",
        extraction_date: "2024-01-15",
        source_type: "court",
        source_url: "https://example.com/sample_003"
    }
]);

print('MongoDB 초기화 완료');
print('- 사용자 app_user 생성');
print('- 컬렉션 및 인덱스 생성');
print('- 샘플 데이터 3건 삽입');
