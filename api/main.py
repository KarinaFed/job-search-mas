"""FastAPI main application."""
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from typing import Union
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional
import uuid

from config import settings
from agents.orchestrator import Orchestrator
from models.schemas import TaskRequest, TaskResponse
from models.database import init_db, get_db
from api.guardrails import validate_input, sanitize_output
from tools.resume_parser import ResumeParser
from loguru import logger

# Initialize orchestrator
orchestrator = Orchestrator()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting Job Search MAS API")
    try:
        init_db()
        logger.info("Database initialized")
    except Exception as e:
        logger.warning(f"Database initialization warning: {e}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Job Search MAS API")


app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Job Search Multi-Agent System API",
        "version": settings.api_version,
        "status": "running"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "job-search-mas"}


@app.post("/api/tasks", response_model=TaskResponse)
async def create_task(task_request: TaskRequest):
    """Create and execute a task."""
    try:
        # Input validation and sanitization
        validation_result = validate_input(task_request.dict())
        if not validation_result["valid"]:
            raise HTTPException(
                status_code=400,
                detail=f"Input validation failed: {validation_result['error']}"
            )
        
        # Generate session ID if not provided
        if not task_request.session_id:
            task_request.session_id = str(uuid.uuid4())
        
        # Execute task through orchestrator
        task_dict = {
            "task_type": task_request.task_type,
            "user_id": task_request.user_id,
            "session_id": task_request.session_id,
            "input_data": task_request.input_data
        }
        
        result = await orchestrator.execute_task(task_dict)
        
        # Sanitize output
        sanitized_result = sanitize_output(result)
        
        # Handle both "result" and "results" keys for compatibility
        result_data = sanitized_result.get("result") or sanitized_result.get("results")
        
        return TaskResponse(
            task_id=result.get("task_id", str(uuid.uuid4())),
            session_id=result.get("session_id", task_request.session_id),
            status=result.get("status", "failed"),
            result=result_data,
            error=sanitized_result.get("error"),
            agent_trace=result.get("agent_trace", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session context and workspace."""
    from memory.redis_memory import redis_memory
    
    context = redis_memory.get_session_context(session_id)
    workspace = redis_memory.get_workspace(session_id)
    
    return {
        "session_id": session_id,
        "context": context,
        "workspace": workspace
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """Clear session data."""
    from memory.redis_memory import redis_memory
    
    redis_memory.clear_session(session_id)
    return {"message": f"Session {session_id} cleared"}


@app.get("/api/users/{user_id}/applications")
async def get_user_applications(user_id: str, db=Depends(get_db)):
    """Get all applications for a user."""
    from models.database import ApplicationDB
    
    applications = db.query(ApplicationDB).filter(
        ApplicationDB.user_id == user_id
    ).order_by(ApplicationDB.created_at.desc()).all()
    
    return {
        "user_id": user_id,
        "applications": [
            {
                "application_id": app.application_id,
                "job_id": app.job_id,
                "status": app.status,
                "created_at": str(app.created_at),
                "updated_at": str(app.updated_at)
            }
            for app in applications
        ],
        "count": len(applications)
    }


@app.get("/api/users/{user_id}/metrics")
async def get_user_metrics(user_id: str, db=Depends(get_db)):
    """Get KPI metrics for a user."""
    from agents.analytics_agent import AnalyticsAgent
    
    analytics_agent = AnalyticsAgent(db)
    metrics = await analytics_agent._calculate_kpis(user_id)
    
    return metrics.dict()


@app.post("/api/resume/upload")
async def upload_resume(
    file: UploadFile = File(...),
    user_id: Optional[str] = Form(None)
):
    """Upload and parse PDF resume.
    
    If user_id is not provided, a new one will be automatically generated.
    Use the same user_id for subsequent requests to maintain your profile and history.
    """
    try:
        # Generate user_id if not provided
        if not user_id:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            logger.info(f"Generated new user_id: {user_id}")
        
        # Validate file type
        if not file.filename.endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are supported"
            )
        
        # Read file content
        pdf_bytes = await file.read()
        
        if len(pdf_bytes) == 0:
            raise HTTPException(
                status_code=400,
                detail="Empty file"
            )
        
        # Parse resume
        resume_parser = ResumeParser()
        result = await resume_parser.execute(resume_pdf=pdf_bytes)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse resume: {result.get('error', 'Unknown error')}"
            )
        
        parsed_data = result.get("data", {})
        
        return {
            "success": True,
            "message": "Resume parsed successfully",
            "data": parsed_data,
            "filename": file.filename,
            "user_id": user_id,
            "note": "Save this user_id to access your profile and history later"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resume/parse")
async def parse_resume_text(
    resume_text: str = Form(...),
    user_id: Optional[str] = Form(None)
):
    """Parse resume from text.
    
    If user_id is not provided, a new one will be automatically generated.
    Use the same user_id for subsequent requests to maintain your profile and history.
    """
    try:
        # Generate user_id if not provided
        if not user_id:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            logger.info(f"Generated new user_id: {user_id}")
        
        if not resume_text or len(resume_text.strip()) < 10:
            raise HTTPException(
                status_code=400,
                detail="Resume text is too short"
            )
        
        # Parse resume
        resume_parser = ResumeParser()
        result = await resume_parser.execute(resume_text=resume_text)
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse resume: {result.get('error', 'Unknown error')}"
            )
        
        parsed_data = result.get("data", {})
        
        return {
            "success": True,
            "message": "Resume parsed successfully",
            "data": parsed_data,
            "user_id": user_id,
            "note": "Save this user_id to access your profile and history later"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/resume/full-journey", response_model=TaskResponse)
async def upload_resume_and_full_journey(
    file: UploadFile = File(None),
    resume_text: str = Form(None),
    user_id: str = Form(None)
):
    """Upload resume (PDF or text) and automatically run full_journey.
    
    You can either:
    - Upload a PDF file (file parameter)
    - Or provide resume text (resume_text parameter)
    
    The system will automatically:
    1. Parse the resume
    2. Analyze profile and create strategy
    3. Find top relevant jobs
    4. Generate cover letters and adapted resumes for top-3 jobs (in Russian)
    
    If user_id is not provided, a new one will be automatically generated.
    """
    import base64
    
    try:
        # Generate user_id if not provided
        if not user_id:
            user_id = f"user_{uuid.uuid4().hex[:12]}"
            logger.info(f"Generated new user_id: {user_id}")
        
        # Handle None values (FastAPI sends None for optional params)
        if file is None or (hasattr(file, 'filename') and file.filename is None):
            file = None
        if resume_text is None or (isinstance(resume_text, str) and resume_text.strip() == ""):
            resume_text = None
            
        # Handle None values for optional parameters
        # FastAPI may send empty UploadFile object when file not provided
        has_file = file and hasattr(file, 'filename') and file.filename
        has_text = resume_text and len(str(resume_text).strip()) > 0
        
        # Validate that at least one input is provided
        if not has_file and not has_text:
            raise HTTPException(
                status_code=400,
                detail="Either file (PDF) or resume_text must be provided"
            )
        
        # Prepare input_data based on input type
        input_data = {}
        if has_file:
            # Validate file type
            if not file.filename.endswith('.pdf'):
                raise HTTPException(
                    status_code=400,
                    detail="Only PDF files are supported"
                )
            
            # Read PDF bytes
            pdf_bytes = await file.read()
            
            if len(pdf_bytes) == 0:
                raise HTTPException(
                    status_code=400,
                    detail="Empty file"
                )
            
            # Convert to base64 for JSON transmission
            input_data["resume_pdf"] = base64.b64encode(pdf_bytes).decode('utf-8')
            input_data["filename"] = file.filename
        elif has_text:
            # Use text input
            resume_text = str(resume_text).strip()
            if len(resume_text) < 10:
                raise HTTPException(
                    status_code=400,
                    detail="Resume text is too short"
                )
            input_data["resume_text"] = resume_text
        
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Execute full_journey task
        task_dict = {
            "task_type": "full_journey",
            "user_id": user_id,
            "session_id": session_id,
            "input_data": input_data
        }
        
        result = await orchestrator.execute_task(task_dict)
        
        # Sanitize output
        sanitized_result = sanitize_output(result)
        result_data = sanitized_result.get("result") or sanitized_result.get("results")
        
        return TaskResponse(
            task_id=result.get("task_id", str(uuid.uuid4())),
            session_id=session_id,
            status=result.get("status", "failed"),
            result=result_data,
            error=sanitized_result.get("error"),
            agent_trace=result.get("agent_trace", [])
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in full journey from resume: {e}")
        raise HTTPException(status_code=500, detail=str(e))




if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

