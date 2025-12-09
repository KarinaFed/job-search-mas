# Job Search Multi-Agent System (MAS)

Intelligent multi-agent system that automates and optimizes job search processes. Acting as a personal career consultant, the system assists users from initial resume analysis to strategic job applications and performance tracking.

## Project Overview

This system implements a multi-agent architecture with 3 specialized agents:

1. **Profile & Strategy Analyst** - Analyzes resumes and creates personalized job search strategies
2. **Market Intelligence Agent** - Researches job market and identifies opportunities, ranks vacancies by relevance
3. **Content Personalization Agent** - Generates tailored application materials (cover letters, adapted resumes)

## Architecture

### System Components

- **Agents**: 3 specialized LLM-based agents with distinct roles
- **Tools**: Resume parser, Job search API (HH.ru), Content generator, Tool router
- **Memory**:
  - **Short-term**: Redis for session context
  - **Shared**: Redis workspace for agent collaboration
  - **Long-term**: PostgreSQL + pgvector for embeddings and structured data
- **Orchestrator**: Coordinates agent workflows and communication
- **Backend**: FastAPI with Swagger UI

### User Journey

1. **Assessment** -> Profile analysis and strategy creation
2. **Job Matching** -> Market research and relevance ranking
3. **Resume/Cover Letter** -> Content personalization

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Python 3.10+ (for local development)
- Access to LiteLLM server (configured in `.env`)

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd Project
```

2. Create `.env` file:
```bash
# Option 1: Use the helper script
python create_env.py

# Option 2: Copy manually
Copy-Item env.example .env
```

3. Update `.env` with your configuration:
```env
LITELLM_BASE_URL=http://a6k2.dgx:34000/v1
LITELLM_API_KEY=your_api_key
MODEL_NAME=qwen3-32b
```

4. Start services with Docker Compose:
```bash
docker-compose up -d
```

5. Access the API:
- API: http://localhost:8000
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start PostgreSQL and Redis (or use Docker):
```bash
docker-compose up -d postgres redis
```

3. Initialize database:
```bash
python -c "from models.database import init_db; init_db()"
```

4. Run the API:
```bash
uvicorn api.main:app --reload
```

## API Endpoints

### Task Execution

**POST** `/api/tasks`
- Execute tasks through the multi-agent system
- Task types: `analyze_profile`, `find_jobs`, `create_application`, `full_journey`

Example:
```json
{
  "user_id": "user_123",
  "task_type": "analyze_profile",
  "input_data": {
    "resume_text": "Experienced software engineer..."
  }
}
```

### Session Management

- **GET** `/api/sessions/{session_id}` - Get session context and workspace
- **DELETE** `/api/sessions/{session_id}` - Clear session data

### User Data

- **GET** `/api/users/{user_id}/applications` - Get user's applications

## Tools and Technologies Used

### Core Technologies

- **Python 3.11+**: Main programming language
- **FastAPI**: Modern, fast web framework for building APIs
- **LangChain**: Framework for building LLM-powered applications
- **LiteLLM**: Unified interface for multiple LLM providers
- **PostgreSQL + pgvector**: Relational database with vector extension for embeddings
- **Redis**: In-memory data store for session management and shared workspace
- **Docker & Docker Compose**: Containerization and orchestration

### LLM Integration

- **Model**: Qwen3-32b (via LiteLLM)
- **Embeddings**: text-embedding-ada-002 for vector search
- **LangChain Integration**: ChatOpenAI, ChatPromptTemplate for agent interactions

### External APIs

- **HH.ru API**: Job search and vacancy data (OAuth2 authentication)
- **Telegram Bot API**: User interface for resume submission and results

### Libraries and Frameworks

- **Pydantic**: Data validation and settings management
- **SQLAlchemy**: ORM for database operations
- **httpx**: Async HTTP client for API calls
- **PyPDF2 / pdfplumber**: PDF parsing for resume extraction
- **BeautifulSoup4**: HTML parsing for job descriptions
- **python-telegram-bot**: Telegram bot framework

### Development Tools

- **pytest**: Testing framework
- **loguru**: Advanced logging
- **uvicorn**: ASGI server for FastAPI

## Configuration

### Environment Variables

- `LITELLM_BASE_URL` - LiteLLM server URL
- `LITELLM_API_KEY` - LiteLLM API key
- `MODEL_NAME` - LLM model name (default: qwen3-32b)
- `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`
- `HH_CLIENT_ID` - HH.ru OAuth2 Client ID (required for HH.ru API access)
- `HH_CLIENT_SECRET` - HH.ru OAuth2 Client Secret (required for HH.ru API access)
- See `env.example` for configuration example

## Safety Features

- **Input Validation**: Schema validation and prompt injection detection
- **Output Sanitization**: Removal of sensitive information
- **Error Handling**: Graceful error management with fallback strategies
- **Guardrails**: Pattern-based injection detection

## Testing

```bash
# Run tests
pytest

# Test API endpoint
curl -X POST "http://localhost:8000/api/tasks" \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "test_user",
    "task_type": "analyze_profile",
    "input_data": {
      "resume_text": "Software engineer with 5 years experience..."
    }
  }'
```

## Agent Communication Flow

The system uses a multi-layered communication architecture:

### Communication Mechanisms

1. **Orchestrator-Based Coordination**
   - The `Orchestrator` manages the execution flow and delegates tasks to agents
   - Sequential execution: each agent receives context from previous agents
   - Task routing: orchestrator determines which agent handles each task type

2. **Shared Memory (Redis Workspace)**
   - **Session Context**: Stores temporary data for the current session (profile, strategy, job matches)
   - **Workspace**: Shared blackboard where agents publish their outputs
   - **TTL-based expiration**: Session data automatically expires after a set time

3. **Message Passing**
   - Agents communicate through structured context dictionaries
   - Context propagation: each agent reads from and writes to shared context
   - Agent trace: system tracks which agents participated in each task

### Communication Flow Example (Full Journey)

```
1. User submits resume -> API -> Orchestrator
2. Orchestrator creates session_id and initializes Redis context
3. Strategy Agent:
   - Reads: resume_text from task
   - Processes: Parses resume, generates strategy
   - Writes: profile, strategy -> Redis session context
   - Publishes: output -> Redis workspace
4. Market Intelligence Agent:
   - Reads: profile, strategy from Redis context
   - Processes: Searches jobs, ranks by relevance
   - Writes: job_matches -> Redis session context
   - Publishes: ranked jobs -> Redis workspace
5. Personalization Agent (for top 3 jobs):
   - Reads: profile, job_matches from Redis context
   - Processes: Generates cover letters and adapted resumes
   - Writes: applications -> PostgreSQL (long-term storage)
   - Publishes: generated content -> Redis workspace
6. Results returned to user via API/Telegram
```

### Data Persistence

- **Short-term (Redis)**: Session context, workspace data (TTL-based)
- **Long-term (PostgreSQL)**: User profiles, job postings, applications, strategies
- **Vector Memory (pgvector)**: Semantic embeddings for job matching


