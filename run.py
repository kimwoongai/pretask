#!/usr/bin/env python3
"""
Document Processing Pipeline 실행 스크립트
"""
import uvicorn
import sys
import os
import asyncio

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_database_connection():
    """데이터베이스 연결 테스트"""
    print("=" * 60)
    print("🔍 DATABASE CONNECTION TEST")
    print("=" * 60)
    
    try:
        from app.core.config import settings
        from app.core.database import db_manager
        
        # 환경 변수 확인
        print(f"Environment: {settings.environment}")
        print(f"MongoDB URL set: {'Yes' if settings.mongodb_url else 'No'}")
        if settings.mongodb_url:
            print(f"MongoDB URL (first 30 chars): {settings.mongodb_url[:30]}...")
        else:
            print("⚠️  MONGODB_URL environment variable not set!")
        print(f"MongoDB DB: {settings.mongodb_db}")
        print(f"Redis URL set: {'Yes' if settings.redis_url else 'No'}")
        
        # 데이터베이스 연결 시도
        await db_manager.connect()
        
        # 연결 상태 확인
        if db_manager.mongo_client:
            print("✅ MongoDB connection successful!")
            
            # 컬렉션 확인
            collection = db_manager.get_collection("precedents_v2")
            if collection is not None:
                try:
                    count = await collection.count_documents({})
                    print(f"📊 precedents_v2 collection has {count} documents")
                except Exception as e:
                    print(f"❌ Error counting documents: {e}")
            else:
                print("❌ Failed to get precedents_v2 collection")
        else:
            print("❌ MongoDB connection failed - client is None")
            
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 60)

if __name__ == "__main__":
    print("🚀 Document Processing Pipeline 시작")
    print("📊 웹 인터페이스: http://localhost:8000")
    print("📚 API 문서: http://localhost:8000/docs")
    print("🛑 종료: Ctrl+C")
    print("-" * 50)
    
    # 데이터베이스 연결 테스트 (동기적으로 실행)
    try:
        asyncio.run(test_database_connection())
    except Exception as e:
        print(f"Failed to run database connection test: {e}")
    
    # 환경에 따라 다른 설정 사용
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    port = int(os.getenv("PORT", "8000"))
    
    if is_production:
        # 프로덕션 환경에서는 Gunicorn 사용 권장
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=False,
            log_level="info",
            workers=1
        )
    else:
        # 개발 환경
        uvicorn.run(
            "app.main:app",
            host="0.0.0.0",
            port=port,
            reload=True,
            log_level="info"
        )
