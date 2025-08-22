#!/usr/bin/env python3
"""
기본 규칙을 AI 제안 규칙들로 업데이트하는 스크립트
"""

import os
import sys
from datetime import datetime

# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.dsl_rules import dsl_manager

def main():
    print("🔧 기본 규칙 업데이트 시작...")
    
    try:
        # 현재 규칙 상태 확인
        print(f"현재 규칙 수: {len(dsl_manager.rules)}")
        
        # 모든 규칙 삭제
        dsl_manager.rules.clear()
        print("기존 규칙 모두 삭제 완료")
        
        # 새로운 개선된 기본 규칙 생성
        dsl_manager._create_default_rules()
        print(f"새로운 기본 규칙 생성 완료: {len(dsl_manager.rules)}개")
        
        # 생성된 규칙 목록 출력
        print("\n생성된 규칙들:")
        for rule_id, rule in dsl_manager.rules.items():
            print(f"  - {rule_id}: {rule.description} (우선순위: {rule.priority})")
        
        # MongoDB에 저장
        save_success = dsl_manager.save_rules()
        
        if save_success:
            print("\n✅ MongoDB 저장 완료!")
            print(f"총 {len(dsl_manager.rules)}개 규칙이 업데이트되었습니다.")
        else:
            print("\n❌ MongoDB 저장 실패!")
            return False
            
        return True
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        return False

if __name__ == "__main__":
    success = main()
    if success:
        print("\n🎉 기본 규칙 업데이트 성공!")
    else:
        print("\n💥 기본 규칙 업데이트 실패!")
        sys.exit(1)
