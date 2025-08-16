FROM mongo:7.0

# 환경 설정
ENV MONGO_INITDB_ROOT_USERNAME=admin
ENV MONGO_INITDB_ROOT_PASSWORD=password
ENV MONGO_INITDB_DATABASE=document_processor

# 초기화 스크립트 복사
COPY init-mongo.js /docker-entrypoint-initdb.d/

# 데이터 디렉토리 권한 설정
RUN chown -R mongodb:mongodb /data/db

EXPOSE 27017

CMD ["mongod"]
