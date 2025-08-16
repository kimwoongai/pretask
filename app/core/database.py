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
            # MongoDB 연결 (선택사항)
            try:
                logger.info(f"Attempting to connect to MongoDB with URL: {settings.mongodb_url[:20]}...")
                logger.info(f"Database name: {settings.mongodb_db}")
                
                self.mongo_client = AsyncIOMotorClient(
                    settings.mongodb_url, 
                    serverSelectionTimeoutMS=10000,  # 10초로 증가
                    connectTimeoutMS=10000,
                    socketTimeoutMS=10000
                )
                self.mongo_db = self.mongo_client[settings.mongodb_db]
                
                # 연결 테스트
                await self.mongo_client.admin.command('ping')
                logger.info("MongoDB connection established successfully")
                
                # precedents_v2 컬렉션 존재 확인
                collections = await self.mongo_db.list_collection_names()
                logger.info(f"Available collections: {collections}")
                
                if "precedents_v2" in collections:
                    count = await self.mongo_db.precedents_v2.count_documents({})
                    logger.info(f"precedents_v2 collection has {count} documents")
                else:
                    logger.warning("precedents_v2 collection not found!")
                    
            except Exception as e:
                logger.error(f"MongoDB connection failed: {e}")
                logger.error(f"MongoDB URL: {settings.mongodb_url}")
                self.mongo_client = None
                self.mongo_db = None
            
            # Redis 연결 (선택사항)
            try:
                self.redis_client = redis.from_url(settings.redis_url, socket_connect_timeout=5)
                await self.redis_client.ping()
                logger.info("Redis connection established successfully")
            except Exception as e:
                logger.warning(f"Redis connection failed, running without cache: {e}")
                self.redis_client = None
            
            logger.info("Database initialization completed")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # 데이터베이스 없이도 애플리케이션 실행 가능
            self.mongo_client = None
            self.mongo_db = None
            self.redis_client = None
    
    async def disconnect(self):
        """데이터베이스 연결 해제"""
        if self.mongo_client:
            self.mongo_client.close()
        
        if self.redis_client:
            await self.redis_client.close()
        
        logger.info("Database connections closed")
    
    def get_collection(self, collection_name: str) -> Optional[AsyncIOMotorCollection]:
        """MongoDB 컬렉션 반환"""
        if self.mongo_db is None:
            logger.warning("MongoDB not available, returning None")
            return None
        return self.mongo_db[collection_name]
    
    async def get_redis(self) -> Optional[redis.Redis]:
        """Redis 클라이언트 반환"""
        if not self.redis_client:
            logger.warning("Redis not available, returning None")
            return None
        return self.redis_client


class DocumentRepository:
    """원본 문서 저장소 (precedents_v2 - 읽기 전용)"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection_name = "precedents_v2"  # 원본 데이터는 읽기만
    
    async def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """원본 케이스 조회 (읽기 전용)"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            from bson import ObjectId
            # ObjectId로 조회 시도
            if ObjectId.is_valid(case_id):
                return await collection.find_one({"_id": ObjectId(case_id)})
            # precedent_id로 조회 시도
            return await collection.find_one({"precedent_id": case_id})
        return None
    
    async def get_cases_sample(self, limit: int = 100) -> List[Dict[str, Any]]:
        """케이스 샘플 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            cursor = collection.aggregate([{"$sample": {"size": limit}}])
            return await cursor.to_list(length=limit)
        return []
    
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


class ProcessedPrecedentRepository:
    """전처리된 판례 저장소"""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db_manager = db_manager
        self.collection_name = "processed_precedents"
    
    async def save_processed_case(self, processed_data: Dict[str, Any]) -> str:
        """전처리된 케이스 저장"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            result = await collection.insert_one(processed_data)
            return str(result.inserted_id)
        else:
            # 데모 모드: 더미 ID 반환
            return f"processed_{processed_data.get('original_id', 'unknown')}"
    
    async def get_processed_case(self, original_id: str, rules_version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """전처리된 케이스 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            query = {"original_id": original_id}
            if rules_version:
                query["rules_version"] = rules_version
            # 최신 버전 우선
            return await collection.find_one(query, sort=[("created_at", -1)])
        return None
    
    async def get_processed_cases(
        self, 
        limit: int = 50, 
        offset: int = 0, 
        rules_version: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """전처리된 케이스 목록 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            query = {}
            if rules_version:
                query["rules_version"] = rules_version
            if status:
                query["status"] = status
            
            cursor = collection.find(query).skip(offset).limit(limit).sort("created_at", -1)
            return await cursor.to_list(length=limit)
        return []
    
    async def update_processed_case(self, processed_id: str, update_data: Dict[str, Any]) -> bool:
        """전처리된 케이스 업데이트"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            from bson import ObjectId
            result = await collection.update_one(
                {"_id": ObjectId(processed_id)},
                {"$set": {**update_data, "updated_at": datetime.now()}}
            )
            return result.modified_count > 0
        return False
    
    async def get_processing_stats(self, rules_version: Optional[str] = None) -> Dict[str, Any]:
        """처리 통계 조회"""
        collection = self.db_manager.get_collection(self.collection_name)
        if collection:
            match_query = {}
            if rules_version:
                match_query["rules_version"] = rules_version
            
            pipeline = [
                {"$match": match_query},
                {"$group": {
                    "_id": "$status",
                    "count": {"$sum": 1},
                    "avg_quality_score": {"$avg": "$quality_score"},
                    "avg_token_reduction": {"$avg": "$token_reduction_percent"}
                }}
            ]
            
            cursor = collection.aggregate(pipeline)
            results = await cursor.to_list(length=None)
            
            stats = {"total": 0, "by_status": {}}
            for result in results:
                stats["by_status"][result["_id"]] = {
                    "count": result["count"],
                    "avg_quality_score": result.get("avg_quality_score", 0),
                    "avg_token_reduction": result.get("avg_token_reduction", 0)
                }
                stats["total"] += result["count"]
            
            return stats
        return {"total": 0, "by_status": {}}


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
