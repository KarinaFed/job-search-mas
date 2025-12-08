"""Vector database for long-term memory using pgvector."""
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import List, Optional, Dict, Any
import json
import numpy as np
from openai import OpenAI
from config import settings
from models.database import ProfileDB, JobPostingDB
from loguru import logger


class VectorMemory:
    """Vector memory manager using pgvector for embeddings."""
    
    def __init__(self, db: Session):
        """Initialize vector memory."""
        self.db = db
        # Use LiteLLM-compatible OpenAI client
        self.openai_client = OpenAI(
            base_url=settings.litellm_base_url,
            api_key=settings.litellm_api_key
        )
        self.embedding_model = "text-embedding-ada-002"  # Use embedding model
        
        # Initialize pgvector extension
        try:
            self.db.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            self.db.commit()
            logger.info("pgvector extension initialized")
        except Exception as e:
            logger.warning(f"Could not initialize pgvector: {e}")
    
    def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text."""
        try:
            response = self.openai_client.embeddings.create(
                model=self.embedding_model,
                input=text
            )
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Error getting embedding: {e}")
            return []
    
    def store_job_embedding(self, job_id: str, job_text: str):
        """Store job posting embedding."""
        embedding = self.get_embedding(job_text)
        if embedding:
            job = self.db.query(JobPostingDB).filter(JobPostingDB.job_id == job_id).first()
            if job:
                job.embedding = json.dumps(embedding)
                self.db.commit()
                logger.info(f"Stored embedding for job {job_id}")
    
    def search_similar_jobs(self, query_text: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for similar jobs using vector similarity."""
        query_embedding = self.get_embedding(query_text)
        if not query_embedding:
            return []
        
        try:
            jobs = self.db.query(JobPostingDB).limit(limit * 2).all()
            results = []
            for job in jobs:
                if job.embedding:
                    stored_embedding = json.loads(job.embedding)
                    similarity = self._cosine_similarity(query_embedding, stored_embedding)
                    results.append({"job": job, "similarity": similarity})
            
            results.sort(key=lambda x: x["similarity"], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"Error in vector search: {e}")
            return []
    
    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        try:
            v1 = np.array(vec1)
            v2 = np.array(vec2)
            dot_product = np.dot(v1, v2)
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            return float(dot_product / (norm1 * norm2))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    def retrieve_user_history(self, user_id: str) -> List[Dict[str, Any]]:
        """Retrieve user's interaction history."""
        profile = self.db.query(ProfileDB).filter(ProfileDB.user_id == user_id).first()
        if profile:
            applications = profile.applications
            return [
                {
                    "type": "application",
                    "job_id": app.job_id,
                    "status": app.status,
                    "created_at": str(app.created_at)
                }
                for app in applications
            ]
        return []
