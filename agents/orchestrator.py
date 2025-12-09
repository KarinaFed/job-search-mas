"""Orchestrator for coordinating agents."""
from typing import Dict, Any, List
from agents.strategy_agent import StrategyAgent
from agents.market_intelligence_agent import MarketIntelligenceAgent
from agents.personalization_agent import PersonalizationAgent
from memory.redis_memory import redis_memory
from loguru import logger
import uuid


class Orchestrator:
    """Orchestrates multi-agent system workflow."""
    
    def __init__(self):
        """Initialize orchestrator."""
        self.agents = {
            "strategy": StrategyAgent(),
            "market_intelligence": MarketIntelligenceAgent(),
            "personalization": PersonalizationAgent()
        }
        logger.info("Orchestrator initialized")
    
    async def execute_task(self, task_request: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task through the agent system."""
        task_type = task_request.get("task_type")
        session_id = task_request.get("session_id") or str(uuid.uuid4())
        user_id = task_request.get("user_id")
        
        logger.info(f"Orchestrator executing task: {task_type} for user {user_id}")
        
        # Initialize session context
        redis_memory.set_session_context(session_id, {
            "user_id": user_id,
            "task_type": task_type,
            "agent_trace": []
        })
        
        try:
            if task_type == "analyze_profile":
                return await self._analyze_profile(task_request, session_id)
            elif task_type == "find_jobs":
                return await self._find_jobs(task_request, session_id)
            elif task_type == "create_application":
                return await self._create_application(task_request, session_id)
            elif task_type == "full_journey":
                return await self._full_journey(task_request, session_id)
            else:
                return {
                    "success": False,
                    "error": f"Unknown task type: {task_type}",
                    "session_id": session_id
                }
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            return {
                "success": False,
                "error": str(e),
                "session_id": session_id
            }
    
    async def _analyze_profile(self, task_request: Dict, session_id: str) -> Dict[str, Any]:
        """Execute profile analysis workflow."""
        context = redis_memory.get_session_context(session_id)
        context["agent_trace"].append("strategy_agent")
        
        input_data = task_request.get("input_data", {})
        
        # Handle base64 encoded PDF
        resume_pdf = None
        if input_data.get("resume_pdf"):
            import base64
            try:
                # If it's base64 string, decode it
                if isinstance(input_data["resume_pdf"], str):
                    resume_pdf = base64.b64decode(input_data["resume_pdf"])
                else:
                    resume_pdf = input_data["resume_pdf"]
            except Exception as e:
                logger.warning(f"Error decoding base64 PDF: {e}")
                resume_pdf = input_data["resume_pdf"]
        
        task = {
            "session_id": session_id,
            "user_id": task_request.get("user_id"),
            "resume_text": input_data.get("resume_text", ""),
            "resume_pdf": resume_pdf  # Support PDF input (bytes or base64)
        }
        
        result = await self.agents["strategy"].process(task, context)
        redis_memory.update_session_context(session_id, context)
        
        return {
            "task_id": str(uuid.uuid4()),
            "session_id": session_id,
            "status": "completed" if result.get("success") else "failed",
            "result": result,
            "agent_trace": context["agent_trace"]
        }
    
    async def _find_jobs(self, task_request: Dict, session_id: str) -> Dict[str, Any]:
        """Execute job search workflow."""
        context = redis_memory.get_session_context(session_id)
        
        # Ensure profile exists
        if "profile" not in context:
            # First run strategy agent
            context["agent_trace"].append("strategy_agent")
            input_data = task_request.get("input_data", {})
            
            # Handle base64 encoded PDF
            resume_pdf = None
            if input_data.get("resume_pdf"):
                import base64
                try:
                    if isinstance(input_data["resume_pdf"], str):
                        resume_pdf = base64.b64decode(input_data["resume_pdf"])
                    else:
                        resume_pdf = input_data["resume_pdf"]
                except Exception as e:
                    logger.warning(f"Error decoding base64 PDF: {e}")
                    resume_pdf = input_data["resume_pdf"]
            
            strategy_task = {
                "session_id": session_id,
                "user_id": task_request.get("user_id"),
                "resume_text": input_data.get("resume_text", ""),
                "resume_pdf": resume_pdf  # Support PDF input (bytes or base64)
            }
            strategy_result = await self.agents["strategy"].process(strategy_task, context)
            if not strategy_result.get("success"):
                return {
                    "task_id": str(uuid.uuid4()),
                    "session_id": session_id,
                    "status": "failed",
                    "error": "Profile analysis failed",
                    "agent_trace": context["agent_trace"]
                }
            context = redis_memory.get_session_context(session_id)
        
        # Run market intelligence agent
        context["agent_trace"].append("market_intelligence_agent")
        market_task = {
            "session_id": session_id,
            "user_id": task_request.get("user_id")
        }
        
        result = await self.agents["market_intelligence"].process(market_task, context)
        redis_memory.update_session_context(session_id, context)
        
        return {
            "task_id": str(uuid.uuid4()),
            "session_id": session_id,
            "status": "completed" if result.get("success") else "failed",
            "result": result,
            "agent_trace": context["agent_trace"]
        }
    
    async def _create_application(self, task_request: Dict, session_id: str) -> Dict[str, Any]:
        """Execute application creation workflow."""
        context = redis_memory.get_session_context(session_id)
        
        # Ensure prerequisites exist
        if "job_matches" not in context:
            return {
                "task_id": str(uuid.uuid4()),
                "session_id": session_id,
                "status": "failed",
                "error": "Job matches not found. Run find_jobs first.",
                "agent_trace": context.get("agent_trace", [])
            }
        
        context["agent_trace"].append("personalization_agent")
        personalization_task = {
            "session_id": session_id,
            "user_id": task_request.get("user_id"),
            "job_id": task_request.get("input_data", {}).get("job_id")
        }
        
        result = await self.agents["personalization"].process(personalization_task, context)
        redis_memory.update_session_context(session_id, context)
        
        return {
            "task_id": str(uuid.uuid4()),
            "session_id": session_id,
            "status": "completed" if result.get("success") else "failed",
            "result": result,
            "agent_trace": context["agent_trace"]
        }
    
    async def _full_journey(self, task_request: Dict, session_id: str) -> Dict[str, Any]:
        """Execute full user journey: analyze → find jobs → create application."""
        results = {}
        
        # Step 1: Analyze profile
        analyze_result = await self._analyze_profile(task_request, session_id)
        results["profile_analysis"] = analyze_result
        if not analyze_result.get("status") == "completed":
            return analyze_result
        
        # Step 2: Find jobs
        find_jobs_result = await self._find_jobs(task_request, session_id)
        results["job_search"] = find_jobs_result
        if not find_jobs_result.get("status") == "completed":
            return find_jobs_result
        
        # Step 3: Create applications for top 3 jobs
        context = redis_memory.get_session_context(session_id)
        job_matches = context.get("job_matches", [])
        
        if job_matches:
            # Get top 3 jobs
            top_jobs = job_matches[:3]
            applications = []
            
            for job_match in top_jobs:
                # Handle both dict and JobMatch object formats
                if isinstance(job_match, dict):
                    job_id = job_match.get("job", {}).get("job_id")
                    job_data = job_match.get("job", {})
                else:
                    # JobMatch object
                    job_id = job_match.job.job_id if hasattr(job_match, 'job') else None
                    job_data = job_match.job.dict() if hasattr(job_match.job, 'dict') else {}
                
                if not job_id:
                    logger.warning(f"Could not extract job_id from job match")
                    continue
                
                app_task = task_request.copy()
                app_task["input_data"] = {"job_id": job_id}
                app_result = await self._create_application(app_task, session_id)
                
                if app_result.get("status") == "completed":
                    applications.append({
                        "job_id": job_id,
                        "job_title": job_data.get("title", ""),
                        "company": job_data.get("company", ""),
                        "application": app_result.get("result", {})
                    })
            
            results["applications"] = applications
            results["applications_count"] = len(applications)
        
        return {
            "task_id": str(uuid.uuid4()),
            "session_id": session_id,
            "status": "completed",
            "result": results,
            "agent_trace": context.get("agent_trace", [])
        }
