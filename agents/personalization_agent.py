"""Content Personalization Agent."""
from typing import Dict, Any
from agents.base_agent import BaseAgent
from tools.content_generator import ContentGenerator
from models.schemas import Application
from loguru import logger


class PersonalizationAgent(BaseAgent):
    """Generates tailored application materials."""
    
    def __init__(self):
        """Initialize personalization agent."""
        super().__init__(
            name="personalization_agent",
            role="Content Personalization Agent"
        )
        self.content_generator = ContentGenerator()
    
    async def process(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process content personalization task."""
        try:
            session_id = task.get("session_id")
            job_id = task.get("job_id")
            user_id = task.get("user_id")
            
            profile = context.get("profile", {})
            job_matches = context.get("job_matches", [])
            
            # Find the specific job
            job = None
            for match in job_matches:
                job_data = match.get("job") if isinstance(match, dict) else match
                if (job_data.get("job_id") if isinstance(job_data, dict) else job_data.job_id) == job_id:
                    job = job_data
                    break
            
            if not job:
                return {"success": False, "error": f"Job {job_id} not found in matches"}
            
            logger.info(f"{self.name} generating content for job {job_id}")
            
            # Prepare profile and job data
            profile_data = {
                "skills_str": self._format_skills(profile.get("skills", [])),
                "seniority": profile.get("seniority", "middle"),
                "career_objectives": profile.get("career_objectives", ""),
                "resume_text": profile.get("resume_text", "")
            }
            
            job_data = job if isinstance(job, dict) else job.dict()
            
            # Generate cover letter
            cover_letter_result = await self.content_generator.execute(
                content_type="cover_letter",
                profile=profile_data,
                job=job_data
            )
            
            # Generate adapted resume
            adapted_resume_result = await self.content_generator.execute(
                content_type="adapted_resume",
                profile=profile_data,
                job=job_data
            )
            
            # Create application
            application = {
                "application_id": f"app_{user_id}_{job_id}",
                "user_id": user_id,
                "job_id": job_id,
                "status": "draft",
                "cover_letter": cover_letter_result.get("content") if cover_letter_result.get("success") else None,
                "adapted_resume": adapted_resume_result.get("content") if adapted_resume_result.get("success") else None
            }
            
            result = {
                "success": True,
                "application": application,
                "cover_letter_generated": cover_letter_result.get("success", False),
                "resume_adapted": adapted_resume_result.get("success", False)
            }
            
            # Save application to PostgreSQL
            try:
                from models.database import SessionLocal, ApplicationDB
                db = SessionLocal()
                try:
                    # Check if application already exists
                    application_db = db.query(ApplicationDB).filter(
                        ApplicationDB.application_id == application["application_id"]
                    ).first()
                    
                    if application_db:
                        # Update existing application
                        application_db.status = application["status"]
                        application_db.cover_letter = application["cover_letter"]
                        application_db.adapted_resume = application["adapted_resume"]
                    else:
                        # Create new application
                        application_db = ApplicationDB(
                            application_id=application["application_id"],
                            user_id=user_id,
                            job_id=job_id,
                            status=application["status"],
                            cover_letter=application["cover_letter"],
                            adapted_resume=application["adapted_resume"]
                        )
                        db.add(application_db)
                    
                    db.commit()
                    logger.info(f"{self.name} saved application {application['application_id']} to PostgreSQL")
                except Exception as db_error:
                    db.rollback()
                    logger.warning(f"{self.name} failed to save application to PostgreSQL: {db_error}")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"{self.name} PostgreSQL save error: {e}")
            
            self.update_context(session_id, {
                "application": application
            })
            
            self.publish_output(session_id, result)
            
            logger.info(f"{self.name} completed content generation")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return {"success": False, "error": str(e)}
    
    def _format_skills(self, skills: list) -> str:
        """Format skills list to string."""
        if not skills:
            return ""
        
        skill_strs = []
        for skill in skills:
            if isinstance(skill, dict):
                name = skill.get("name", "")
                level = skill.get("level", "")
                if level:
                    skill_strs.append(f"{name} ({level})")
                else:
                    skill_strs.append(name)
            else:
                skill_strs.append(str(skill))
        
        return ", ".join(skill_strs)

