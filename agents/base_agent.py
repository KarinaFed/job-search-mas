"""Base agent class."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from config import settings
from memory.redis_memory import redis_memory
from loguru import logger


class BaseAgent(ABC):
    """Base class for all agents."""
    
    def __init__(self, name: str, role: str):
        """Initialize agent."""
        self.name = name
        self.role = role
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=settings.temperature,
            openai_api_key=settings.litellm_api_key,
            openai_api_base=settings.litellm_base_url
        )
        logger.info(f"Initialized agent: {self.name} ({self.role})")
    
    @abstractmethod
    async def process(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process a task and return result."""
        pass
    
    def get_context(self, session_id: str) -> Dict[str, Any]:
        """Get session context."""
        return redis_memory.get_session_context(session_id) or {}
    
    def update_context(self, session_id: str, updates: Dict[str, Any]):
        """Update session context."""
        redis_memory.update_session_context(session_id, updates)
    
    def publish_output(self, session_id: str, output: Dict[str, Any]):
        """Publish output to shared workspace."""
        redis_memory.append_agent_output(session_id, self.name, output)
        logger.debug(f"{self.name} published output to workspace")
    
    def get_workspace(self, session_id: str) -> Dict[str, Any]:
        """Get collaborative workspace."""
        return redis_memory.get_workspace(session_id)

