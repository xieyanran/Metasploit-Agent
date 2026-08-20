"""Semantic memory 依赖的数据库连接配置

memory/types/semantic.py 通过 get_database_config() 获取 Qdrant/Neo4j 连接参数，
两者字段与 memory/storage/qdrant_store.py::QdrantConnectionManager.get_instance()、
memory/storage/neo4j_store.py::Neo4jGraphStore.__init__() 的入参一一对应。
默认值指向本地 docker-compose.memory.yml 起的容器，无需任何 .env 配置即可跑通。
"""

import os
from typing import Optional
from pydantic import BaseModel


class DatabaseConfig(BaseModel):
    """从环境变量读取 Qdrant/Neo4j 连接参数"""

    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: Optional[str] = None
    qdrant_collection: str = "pentest_agent_semantic_memory"
    qdrant_distance: str = "cosine"
    qdrant_timeout: int = 30

    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_username: str = "neo4j"
    neo4j_password: str = "hello-agents-password"
    neo4j_database: str = "neo4j"

    @classmethod
    def from_env(cls) -> "DatabaseConfig":
        return cls(
            qdrant_url=os.getenv("QDRANT_URL", "http://localhost:6333"),
            qdrant_api_key=os.getenv("QDRANT_API_KEY") or None,
            qdrant_collection=os.getenv("QDRANT_COLLECTION", "pentest_agent_semantic_memory"),
            qdrant_distance=os.getenv("QDRANT_DISTANCE", "cosine"),
            qdrant_timeout=int(os.getenv("QDRANT_TIMEOUT", "30")),
            neo4j_uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
            neo4j_username=os.getenv("NEO4J_USERNAME", "neo4j"),
            neo4j_password=os.getenv("NEO4J_PASSWORD", "hello-agents-password"),
            neo4j_database=os.getenv("NEO4J_DATABASE", "neo4j"),
        )

    def get_qdrant_config(self) -> dict:
        """QdrantConnectionManager.get_instance(**config) 的入参"""
        return {
            "url": self.qdrant_url,
            "api_key": self.qdrant_api_key,
            "collection_name": self.qdrant_collection,
            "distance": self.qdrant_distance,
            "timeout": self.qdrant_timeout,
        }

    def get_neo4j_config(self) -> dict:
        """Neo4jGraphStore(**config) 的入参"""
        return {
            "uri": self.neo4j_uri,
            "username": self.neo4j_username,
            "password": self.neo4j_password,
            "database": self.neo4j_database,
        }


_config: Optional[DatabaseConfig] = None


def get_database_config() -> DatabaseConfig:
    """获取全局共享的数据库配置实例（懒加载单例）"""
    global _config
    if _config is None:
        _config = DatabaseConfig.from_env()
    return _config
