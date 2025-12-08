"""Market Intelligence Agent."""
from typing import Dict, Any, List
from langchain.prompts import ChatPromptTemplate
from agents.base_agent import BaseAgent
from tools.job_search_api import JobSearchAPI
from tools.tool_router import ToolRouter
from models.schemas import JobPosting, JobMatch
from loguru import logger


class MarketIntelligenceAgent(BaseAgent):
    """Researches job market and identifies opportunities."""
    
    def __init__(self):
        """Initialize market intelligence agent."""
        super().__init__(
            name="market_intelligence_agent",
            role="Market Intelligence Agent"
        )
        self.job_search_api = JobSearchAPI()
        self.tool_router = ToolRouter()
    
    async def process(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process job search and ranking task."""
        try:
            session_id = task.get("session_id")
            profile = context.get("profile", {})
            strategy = context.get("strategy", {})
            
            logger.info(f"{self.name} processing job search")
            
            # Step 1: Determine search query from strategy
            search_query = self._build_search_query(profile, strategy)
            
            # Step 2: Search for jobs
            search_result = await self.job_search_api.execute(
                query=search_query,
                area=profile.get("location"),
                salary=profile.get("salary_expectations"),
                per_page=20
            )
            
            if not search_result.get("success"):
                return search_result
            
            jobs = search_result.get("jobs", [])
            logger.info(f"{self.name} received {len(jobs)} jobs from API")
            
            # Step 3: Rank jobs by relevance
            ranked_jobs = await self._rank_jobs(jobs, profile, strategy)
            logger.info(f"{self.name} ranked {len(ranked_jobs)} jobs after ranking")
            
            # Step 4: Store results
            # Convert JobMatch objects to dict format
            jobs_data = []
            for job_match in ranked_jobs[:20]:  # Return all 20 ranked jobs
                if isinstance(job_match, JobMatch):
                    jobs_data.append({
                        "job": job_match.job.dict() if isinstance(job_match.job, JobPosting) else job_match.job,
                        "relevance_score": job_match.relevance_score,
                        "match_reasons": job_match.match_reasons,
                        "gaps": job_match.gaps
                    })
                else:
                    jobs_data.append(job_match)
            
            result = {
                "success": True,
                "jobs": jobs_data,
                "total_found": len(jobs_data),  # Use actual number of returned jobs
                "search_query": search_query
            }
            logger.info(f"{self.name} returning {len(jobs_data)} jobs in result")
            
            # Save jobs to PostgreSQL
            try:
                from models.database import SessionLocal, JobPostingDB
                from memory.vector_memory import VectorMemory
                from datetime import datetime
                
                db = SessionLocal()
                try:
                    vector_memory = VectorMemory(db)
                    
                    for job_match in ranked_jobs[:20]:  # Save top 20 jobs
                        # Extract job data
                        if isinstance(job_match, dict):
                            job_dict = job_match.get("job", {})
                        else:
                            job_dict = job_match.job.dict() if hasattr(job_match.job, 'dict') else {}
                        
                        if not job_dict or not job_dict.get("job_id"):
                            continue
                        
                        job_id = job_dict.get("job_id")
                        relevance_score = job_match.relevance_score if hasattr(job_match, 'relevance_score') else job_match.get("relevance_score")
                        
                        # Save or update job posting
                        job_db = db.query(JobPostingDB).filter(JobPostingDB.job_id == job_id).first()
                        
                        # Parse posted_at if it's a string
                        posted_at = None
                        if job_dict.get("posted_at"):
                            if isinstance(job_dict["posted_at"], str):
                                try:
                                    posted_at = datetime.fromisoformat(job_dict["posted_at"].replace('Z', '+00:00'))
                                except:
                                    pass
                            else:
                                posted_at = job_dict["posted_at"]
                        
                        job_data = {
                            "job_id": job_id,
                            "title": job_dict.get("title", ""),
                            "company": job_dict.get("company", ""),
                            "description": job_dict.get("description", ""),
                            "requirements": job_dict.get("requirements", []),
                            "skills_required": job_dict.get("skills_required", []),
                            "location": job_dict.get("location"),
                            "salary_min": job_dict.get("salary_min"),
                            "salary_max": job_dict.get("salary_max"),
                            "seniority_level": job_dict.get("seniority_level"),
                            "url": job_dict.get("url"),
                            "source": job_dict.get("source", "hh.ru"),
                            "posted_at": posted_at,
                            "relevance_score": relevance_score
                        }
                        
                        if job_db:
                            # Update existing job
                            for key, value in job_data.items():
                                setattr(job_db, key, value)
                        else:
                            # Create new job
                            job_db = JobPostingDB(**job_data)
                            db.add(job_db)
                        
                        # Store embedding for vector search
                        job_text = f"{job_dict.get('title', '')} {job_dict.get('description', '')} {' '.join(job_dict.get('skills_required', []))}"
                        vector_memory.store_job_embedding(job_id, job_text[:5000])  # Limit text length
                    
                    db.commit()
                    logger.info(f"{self.name} saved {len(ranked_jobs[:20])} jobs to PostgreSQL")
                except Exception as db_error:
                    db.rollback()
                    logger.warning(f"{self.name} failed to save jobs to PostgreSQL: {db_error}")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"{self.name} PostgreSQL save error: {e}")
            
            self.update_context(session_id, {
                "job_matches": jobs_data
            })
            
            self.publish_output(session_id, result)
            
            logger.info(f"{self.name} found {len(ranked_jobs)} relevant jobs")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return {"success": False, "error": str(e)}
    
    def _build_search_query(self, profile: Dict, strategy: Dict) -> str:
        """Build search query from profile and strategy."""
        target_positions = strategy.get("target_positions", [])
        if target_positions:
            return target_positions[0]
        
        skills = profile.get("skills", [])
        if skills:
            skill_names = [s.get("name", "") if isinstance(s, dict) else s.name for s in skills[:3]]
            return " ".join(skill_names)
        
        return "разработчик"  # Default query
    
    async def _rank_jobs(self, jobs: List[JobPosting], profile: Dict, strategy: Dict) -> List[JobMatch]:
        """Rank jobs by relevance using LLM."""
        if not jobs:
            return []
        
        # Prepare job summaries for ranking
        job_summaries = []
        for job in jobs[:20]:  # Limit for LLM processing
            job_dict = job.dict() if isinstance(job, JobPosting) else job
            job_summaries.append({
                "job_id": job_dict.get("job_id"),
                "title": job_dict.get("title"),
                "company": job_dict.get("company"),
                "skills_required": job_dict.get("skills_required", []),
                "description": job_dict.get("description", "")[:200]
            })
        
        # Use LLM to rank jobs
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a job matching expert. Rank jobs by relevance to the candidate.
            Return a JSON array with job_id and relevance_score (0.0-1.0) for each job."""),
            ("human", """Rank these jobs for the candidate:

Candidate Skills: {candidate_skills}
Candidate Seniority: {seniority}
Target Positions: {target_positions}

Jobs:
{jobs}

Return JSON array with job_id and relevance_score:""")
        ])
        
        try:
            candidate_skills = [s.get("name", "") if isinstance(s, dict) else s.name for s in profile.get("skills", [])]
            
            chain = prompt | self.llm
            response = chain.invoke({
                "candidate_skills": ", ".join(candidate_skills),
                "seniority": profile.get("seniority", "middle"),
                "target_positions": ", ".join(strategy.get("target_positions", [])),
                "jobs": str(job_summaries)
            })
            
            import json
            content = response.content.strip()
            
            # Extract JSON array
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            if content.startswith("["):
                rankings = json.loads(content)
            else:
                start = content.find("[")
                end = content.rfind("]") + 1
                rankings = json.loads(content[start:end])
            
            # Create ranked job matches
            job_dict = {}
            for job in jobs:
                if isinstance(job, JobPosting):
                    job_dict[job.job_id] = job
                elif isinstance(job, dict):
                    job_dict[job.get("job_id")] = job
                else:
                    job_id = getattr(job, "job_id", None) or job.get("job_id") if hasattr(job, "get") else None
                    if job_id:
                        job_dict[job_id] = job
            
            ranked_matches = []
            ranked_job_ids = set()
            
            for ranking in rankings:
                job_id = ranking.get("job_id")
                score = ranking.get("relevance_score", 0.5)
                if job_id in job_dict:
                    job = job_dict[job_id]
                    # Convert to JobPosting if needed
                    if isinstance(job, JobPosting):
                        job_obj = job
                    elif isinstance(job, dict):
                        job_obj = JobPosting(**job)
                    else:
                        job_obj = job
                    
                    ranked_matches.append(JobMatch(
                        job=job_obj,
                        relevance_score=float(score),
                        match_reasons=ranking.get("match_reasons", []),
                        gaps=ranking.get("gaps", [])
                    ))
                    ranked_job_ids.add(job_id)
            
            # Add jobs that weren't ranked by LLM (fallback - ensure all jobs are included)
            for job_id, job in job_dict.items():
                if job_id not in ranked_job_ids:
                    if isinstance(job, JobPosting):
                        job_obj = job
                    elif isinstance(job, dict):
                        job_obj = JobPosting(**job)
                    else:
                        job_obj = job
                    
                    # Add with default relevance score (will be sorted after ranked ones)
                    ranked_matches.append(JobMatch(
                        job=job_obj,
                        relevance_score=0.5,  # Default score
                        match_reasons=[],
                        gaps=[]
                    ))
            
            # Sort by relevance score (descending)
            ranked_matches.sort(key=lambda x: x.relevance_score, reverse=True)
            logger.info(f"{self.name} created {len(ranked_matches)} ranked matches (LLM ranked {len(rankings)}, added {len(ranked_matches) - len(rankings)} with default score)")
            return ranked_matches
            
        except Exception as e:
            logger.error(f"Error ranking jobs: {e}")
            # Fallback: return jobs with default scores
            from models.schemas import JobPosting as JobPostingSchema
            return [
                JobMatch(
                    job=job if isinstance(job, JobPostingSchema) else (JobPostingSchema(**job) if isinstance(job, dict) else job),
                    relevance_score=0.5,
                    match_reasons=[],
                    gaps=[]
                )
                for job in jobs
            ]

