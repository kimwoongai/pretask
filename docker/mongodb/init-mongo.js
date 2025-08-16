// MongoDB 초기화 스크립트
db = db.getSiblingDB('document_processor');

// 사용자 생성
db.createUser({
    user: 'app_user',
    pwd: 'app_password',
    roles: [
        {
            role: 'readWrite',
            db: 'document_processor'
        }
    ]
});

// 컬렉션 생성 및 인덱스 설정
db.createCollection('document_cases');
db.createCollection('processing_results');
db.createCollection('rules_versions');
db.createCollection('batch_jobs');
db.createCollection('safety_gates');

// 인덱스 생성
db.document_cases.createIndex({ "case_id": 1 }, { unique: true });
db.document_cases.createIndex({ "court_type": 1, "case_type": 1, "year": 1 });
db.document_cases.createIndex({ "status": 1 });

db.processing_results.createIndex({ "case_id": 1, "rules_version": 1 });
db.processing_results.createIndex({ "created_at": -1 });

db.rules_versions.createIndex({ "version": 1 }, { unique: true });
db.rules_versions.createIndex({ "created_at": -1 });

db.batch_jobs.createIndex({ "job_id": 1 }, { unique: true });
db.batch_jobs.createIndex({ "status": 1 });

// 샘플 데이터 삽입 (개발용)
db.document_cases.insertMany([
    {
        case_id: "case_001",
        court_type: "지방법원",
        case_type: "민사",
        year: 2023,
        format_type: "pdf",
        original_content: "법원 판결문 샘플 내용입니다. 페이지 1\n\n본 사건은...\n\n---구분선---\n\n결론적으로...",
        status: "pending",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        case_id: "case_002", 
        court_type: "고등법원",
        case_type: "형사",
        year: 2023,
        format_type: "hwp",
        original_content: "형사 판결문 샘플입니다. 페이지 2\n\n피고인은...\n\n========\n\n판결 주문...",
        status: "pending",
        created_at: new Date(),
        updated_at: new Date()
    },
    {
        case_id: "case_003",
        court_type: "행정법원", 
        case_type: "행정",
        year: 2024,
        format_type: "doc",
        original_content: "행정 소송 판결문입니다. 페이지 3\n\n원고의 주장...\n\n-----------\n\n법원의 판단...",
        status: "pending",
        created_at: new Date(),
        updated_at: new Date()
    }
]);

print('MongoDB 초기화 완료');
print('- 사용자 app_user 생성');
print('- 컬렉션 및 인덱스 생성');
print('- 샘플 데이터 3건 삽입');
