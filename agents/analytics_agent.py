"""Application & Analytics Tracker Agent."""
from typing import Dict, Any, List
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from agents.base_agent import BaseAgent
from models.database import ApplicationDB, ProfileDB, JobPostingDB
from models.schemas import KPIMetrics, ApplicationStatus
from loguru import logger


class AnalyticsAgent(BaseAgent):
    """Monitors application status and performance."""
    
    def __init__(self, db: Session):
        """Initialize analytics agent."""
        super().__init__(
            name="analytics_agent",
            role="Application & Analytics Tracker"
        )
        self.db = db
    
    async def process(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process analytics task."""
        try:
            session_id = task.get("session_id")
            user_id = task.get("user_id")
            task_type = task.get("task_type", "get_metrics")
            
            logger.info(f"{self.name} processing {task_type} for user {user_id}")
            
            if task_type == "get_metrics":
                metrics = await self._calculate_kpis(user_id)
                result = {"success": True, "metrics": metrics.dict()}
            elif task_type == "update_status":
                application_id = task.get("application_id")
                new_status = task.get("status")
                result = await self._update_application_status(application_id, new_status)
            elif task_type == "get_applications":
                result = await self._get_user_applications(user_id)
            else:
                result = {"success": False, "error": f"Unknown task type: {task_type}"}
            
            self.publish_output(session_id, result)
            return result
            
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _calculate_kpis(self, user_id: str) -> KPIMetrics:
        """Calculate KPI metrics for user."""
        # Get applications from last 30 days
        period_end = datetime.now()
        period_start = period_end - timedelta(days=30)
        
        applications = self.db.query(ApplicationDB).filter(
            ApplicationDB.user_id == user_id,
            ApplicationDB.created_at >= period_start
        ).all()
        
        total_applications = len(applications)
        applications_viewed = sum(1 for app in applications if app.status in ["viewed", "interview", "accepted"])
        interviews_scheduled = sum(1 for app in applications if app.status in ["interview", "accepted"])
        offers_received = sum(1 for app in applications if app.status == "accepted")
        
        # Calculate rates
        ctr = (applications_viewed / total_applications * 100) if total_applications > 0 else 0.0
        interview_rate = (interviews_scheduled / total_applications * 100) if total_applications > 0 else 0.0
        offer_rate = (offers_received / total_applications * 100) if total_applications > 0 else 0.0
        
        # Calculate average relevance (if available)
        avg_relevance = 0.0
        if applications:
            jobs = [app.job for app in applications if app.job and app.job.relevance_score]
            if jobs:
                avg_relevance = sum(job.relevance_score for job in jobs) / len(jobs)
        
        return KPIMetrics(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            total_applications=total_applications,
            applications_viewed=applications_viewed,
            interviews_scheduled=interviews_scheduled,
            offers_received=offers_received,
            average_relevance_score=avg_relevance,
            click_through_rate=ctr,
            interview_rate=interview_rate,
            offer_rate=offer_rate
        )
    
    async def _update_application_status(self, application_id: str, new_status: str) -> Dict[str, Any]:
        """Update application status."""
        application = self.db.query(ApplicationDB).filter(
            ApplicationDB.application_id == application_id
        ).first()
        
        if not application:
            return {"success": False, "error": "Application not found"}
        
        # Validate status
        valid_statuses = [s.value for s in ApplicationStatus]
        if new_status not in valid_statuses:
            return {"success": False, "error": f"Invalid status: {new_status}"}
        
        application.status = new_status
        application.updated_at = datetime.now()
        
        # Update timestamps based on status
        if new_status == "viewed" and not application.viewed_at:
            application.viewed_at = datetime.now()
        elif new_status == "interview" and not application.interview_at:
            application.interview_at = datetime.now()
        
        self.db.commit()
        
        logger.info(f"Updated application {application_id} to status {new_status}")
        return {"success": True, "application_id": application_id, "status": new_status}
    
    async def _get_user_applications(self, user_id: str) -> Dict[str, Any]:
        """Get all applications for user."""
        applications = self.db.query(ApplicationDB).filter(
            ApplicationDB.user_id == user_id
        ).order_by(ApplicationDB.created_at.desc()).all()
        
        apps_data = []
        for app in applications:
            apps_data.append({
                "application_id": app.application_id,
                "job_id": app.job_id,
                "status": app.status,
                "created_at": str(app.created_at),
                "updated_at": str(app.updated_at),
                "viewed_at": str(app.viewed_at) if app.viewed_at else None,
                "interview_at": str(app.interview_at) if app.interview_at else None
            })
        
        return {"success": True, "applications": apps_data, "count": len(apps_data)}

