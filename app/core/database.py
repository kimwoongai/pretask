"""
데이터베이스 연결 및 관리
"""
import asyncio
from typing import Optional, Dict, List, Any
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase, AsyncIOMotorCollection
import redis.asyncio as redis
from app.core.config import settings
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    """데이터베이스 관리자"""
    
    def __init__(self):
        self.mongo_client: Optional[AsyncIOMotorClient] = None
        self.mongo_db: Optional[AsyncIOMotorDatabase] = None
        self.redis_client: Optional[redis.Redis] = None
    
    async def connect(self):
        """데이터베이스 연결"""
        try:
            # MongoDB 연결
            self.mongo_client = AsyncIOMotorClient(settings.mongodb_url)
            self.mongo_db = self.mongo_client[settings.mongodb_db]
            
            # Redis 연결
            self.redis_client = redis.from_url(settings.redis_url)
            
            # 연결 테스트
            await self.mongo_client.admin.command('ping')
            await self.redis_client.ping()
            
            logger.info("Database connections established successfully")
            
        except Exception as e:
            logger.error(f"Failed to connect to databases: {e}")
            raise
    
    async def disconnect(self):
        """데이터베이스 연결 해제"""
        if self.mongo_client:
            self.mongo_client.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Database connections closed")
    
    def get_collection(self, collection_name: str) -> AsyncIOMotorCollection:
        """MongoDB 컬렉션 반환"""
        if not self.mongo_db:
            raise RuntimeError("MongoDB not connected")
        return self.mongo_db[collection_name]
    
    async def get_redis(self) -> redis.Redis:
        """Redis 클라이언트 반환"""
        if not self.redis_client:
            raise RuntimeError("Redis not connected")
        return self.redis_client


class DocumentRepository:
    """문서 케이스 저장소"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection_name = "document_cases"
    
    async def save_case(self, case_data: Dict[str, Any]) -> str:
        """케이스 저장"""
        collection = self.db_manager.get_collection(self.collection_name)
        result = await collection.insert_one(case_data)
        return str(result.inserted_id)
    
    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """케이스 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        return await collection.find_one({"case_id": case_id})
    
    async def update_case(self, case_id: str, update_data: Dict[str, Any]) -> bool:
        """케이스 업데이트"""
        collection = self.db_manager.get_collection(self.collection_name)
        result = await collection.update_one(
            {"case_id": case_id},
            {"$set": update_data}
        )
        return result.modified_count > 0
    
    async def get_stratified_sample(self, criteria: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
        """층화 샘플링"""
        collection = self.db_manager.get_collection(self.collection_name)
        
        # 층화 기준에 따른 파이프라인 구성
        pipeline = []
        
        if criteria:
            pipeline.append({"$match": criteria})
        
        # 층화를 위한 그룹핑
        if "court_type" in criteria or "case_type" in criteria:
            pipeline.extend([
                {"$group": {
                    "_id": {
                        "court_type": "$court_type",
                        "case_type": "$case_type",
                        "year": "$year"
                    },
                    "docs": {"$push": "$$ROOT"}
                }},
                {"$project": {
                    "docs": {"$slice": ["$docs", limit // 10]}  # 각 그룹에서 일정 수만 선택
                }},
                {"$unwind": "$docs"},
                {"$replaceRoot": {"newRoot": "$docs"}},
                {"$limit": limit}
            ])
        else:
            pipeline.append({"$sample": {"size": limit}})
        
        cursor = collection.aggregate(pipeline)
        return await cursor.to_list(length=None)


class ProcessingResultRepository:
    """처리 결과 저장소"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection_name = "processing_results"
    
    async def save_result(self, result_data: Dict[str, Any]) -> str:
        """결과 저장"""
        collection = self.db_manager.get_collection(self.collection_name)
        result = await collection.insert_one(result_data)
        return str(result.inserted_id)
    
    async def get_results_by_version(self, rules_version: str) -> List[Dict[str, Any]]:
        """버전별 결과 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        cursor = collection.find({"rules_version": rules_version})
        return await cursor.to_list(length=None)
    
    async def get_failure_patterns(self, rules_version: str) -> List[Dict[str, Any]]:
        """실패 패턴 분석"""
        collection = self.db_manager.get_collection(self.collection_name)
        
        pipeline = [
            {"$match": {"rules_version": rules_version, "errors": {"$ne": []}}},
            {"$unwind": "$errors"},
            {"$group": {
                "_id": "$errors",
                "count": {"$sum": 1},
                "sample_cases": {"$addToSet": "$case_id"}
            }},
            {"$sort": {"count": -1}},
            {"$limit": 10}
        ]
        
        cursor = collection.aggregate(pipeline)
        return await cursor.to_list(length=None)


class RulesRepository:
    """규칙 저장소"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection_name = "rules_versions"
    
    async def save_version(self, version_data: Dict[str, Any]) -> str:
        """규칙 버전 저장"""
        collection = self.db_manager.get_collection(self.collection_name)
        result = await collection.insert_one(version_data)
        return str(result.inserted_id)
    
    async def get_latest_version(self) -> Optional[Dict[str, Any]]:
        """최신 버전 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        return await collection.find_one(sort=[("created_at", -1)])
    
    async def get_version(self, version: str) -> Optional[Dict[str, Any]]:
        """특정 버전 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        return await collection.find_one({"version": version})


class CacheManager:
    """캐시 관리자"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
    
    async def get_evaluation_cache(self, case_id: str, rules_version: str) -> Optional[Dict[str, Any]]:
        """평가 캐시 조회"""
        redis_client = await self.db_manager.get_redis()
        cache_key = f"eval:{case_id}:{rules_version}"
        
        cached_data = await redis_client.get(cache_key)
        if cached_data:
            import json
            return json.loads(cached_data)
        return None
    
    async def set_evaluation_cache(self, case_id: str, rules_version: str, result: Dict[str, Any], ttl: int = 3600):
        """평가 캐시 저장"""
        redis_client = await self.db_manager.get_redis()
        cache_key = f"eval:{case_id}:{rules_version}"
        
        import json
        await redis_client.setex(cache_key, ttl, json.dumps(result, default=str))
    
    async def invalidate_cache_pattern(self, pattern: str):
        """패턴 기반 캐시 무효화"""
        redis_client = await self.db_manager.get_redis()
        keys = await redis_client.keys(pattern)
        if keys:
            await redis_client.delete(*keys)


# 글로벌 인스턴스
db_manager = DatabaseManager()
document_repo = DocumentRepository(db_manager)
result_repo = ProcessingResultRepository(db_manager)
rules_repo = RulesRepository(db_manager)
cache_manager = CacheManager(db_manager)
