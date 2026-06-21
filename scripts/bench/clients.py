import os
import json
import numpy as np

class BaseBenchClient:
    @property
    def name(self):
        return "Base"
        
    def ingest_batch(self, ids: list[str], texts: list[str], embeddings: np.ndarray):
        """Ingest a batch of documents"""
        raise NotImplementedError

    def query(self, embedding: np.ndarray, top_k: int = 10) -> list[str]:
        """Query and return top K document IDs"""
        raise NotImplementedError

class EngramBenchClient(BaseBenchClient):
    @property
    def name(self):
        return "Engram"
        
    def __init__(self, miner_url="http://127.0.0.1:8091"):
        # Import dynamically so we don't crash if SDK isn't installed
        import sys
        sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))
        from engram.sdk import EngramClient
        self.client = EngramClient(miner_url=miner_url)
        
    def ingest_batch(self, ids: list[str], texts: list[str], embeddings: np.ndarray):
        for doc_id, text, emb in zip(ids, texts, embeddings):
            self.client.ingest_embedding(emb.tolist(), metadata={"doc_id": doc_id})
            
    def query(self, embedding: np.ndarray, top_k: int = 10) -> list[str]:
        res = self.client.query_by_vector(embedding.tolist(), top_k=top_k)
        return [r["metadata"].get("doc_id", "") for r in res]

class PineconeBenchClient(BaseBenchClient):
    @property
    def name(self):
        return "Pinecone"
        
    def __init__(self, api_key: str, environment: str, index_name: str):
        from pinecone import Pinecone
        self.pc = Pinecone(api_key=api_key)
        self.index = self.pc.Index(index_name)
        
    def ingest_batch(self, ids: list[str], texts: list[str], embeddings: np.ndarray):
        vectors = []
        for doc_id, text, emb in zip(ids, texts, embeddings):
            vectors.append({"id": doc_id, "values": emb.tolist(), "metadata": {"text": text}})
        self.index.upsert(vectors=vectors)
        
    def query(self, embedding: np.ndarray, top_k: int = 10) -> list[str]:
        res = self.index.query(vector=embedding.tolist(), top_k=top_k)
        return [match["id"] for match in res["matches"]]

class WeaviateBenchClient(BaseBenchClient):
    @property
    def name(self):
        return "Weaviate"
        
    def __init__(self, url: str):
        import weaviate
        self.client = weaviate.Client(url)
        self.class_name = "Document"
        # Setup schema if missing
        try:
            self.client.schema.create_class({
                "class": self.class_name,
                "vectorizer": "none",
            })
        except Exception:
            pass # already exists

    def ingest_batch(self, ids: list[str], texts: list[str], embeddings: np.ndarray):
        with self.client.batch as batch:
            batch.batch_size = 100
            for doc_id, text, emb in zip(ids, texts, embeddings):
                batch.add_data_object(
                    data_object={"doc_id": doc_id, "text": text},
                    class_name=self.class_name,
                    vector=emb.tolist()
                )

    def query(self, embedding: np.ndarray, top_k: int = 10) -> list[str]:
        res = (
            self.client.query
            .get(self.class_name, ["doc_id"])
            .with_near_vector({"vector": embedding.tolist()})
            .with_limit(top_k)
            .do()
        )
        docs = res["data"]["Get"][self.class_name]
        return [doc["doc_id"] for doc in docs]

class PgVectorBenchClient(BaseBenchClient):
    @property
    def name(self):
        return "pgvector"
        
    def __init__(self, connection_string: str, dim: int = 384):
        import psycopg2
        from pgvector.psycopg2 import register_vector
        self.conn = psycopg2.connect(connection_string)
        register_vector(self.conn)
        with self.conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute(f"CREATE TABLE IF NOT EXISTS docs (id text PRIMARY KEY, text text, embedding vector({dim}))")
        self.conn.commit()

    def ingest_batch(self, ids: list[str], texts: list[str], embeddings: np.ndarray):
        with self.conn.cursor() as cur:
            for doc_id, text, emb in zip(ids, texts, embeddings):
                cur.execute(
                    "INSERT INTO docs (id, text, embedding) VALUES (%s, %s, %s) ON CONFLICT (id) DO NOTHING",
                    (doc_id, text, emb.tolist())
                )
        self.conn.commit()

    def query(self, embedding: np.ndarray, top_k: int = 10) -> list[str]:
        with self.conn.cursor() as cur:
            cur.execute(
                "SELECT id FROM docs ORDER BY embedding <-> %s LIMIT %s",
                (embedding.tolist(), top_k)
            )
            return [row[0] for row in cur.fetchall()]
