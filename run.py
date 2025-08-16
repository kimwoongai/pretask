#!/usr/bin/env python3
"""
Document Processing Pipeline 실행 스크립트
"""
import uvicorn
import sys
import os

# 프로젝트 루트를 Python path에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    print("🚀 Document Processing Pipeline 시작")
    print("📊 웹 인터페이스: http://localhost:8000")
    print("📚 API 문서: http://localhost:8000/docs")
    print("🛑 종료: Ctrl+C")
    print("-" * 50)
    
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
