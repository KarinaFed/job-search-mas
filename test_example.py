"""Example test script for the API."""
import requests
import json

API_URL = "http://localhost:8000"

def test_analyze_profile():
    """Test profile analysis."""
    payload = {
        "user_id": "test_user_1",
        "task_type": "analyze_profile",
        "input_data": {
            "resume_text": """
            John Doe
            Software Engineer
            
            Experience:
            - 5 years of Python development
            - Django, Flask, FastAPI
            - PostgreSQL, Redis
            - Docker, Kubernetes
            
            Skills: Python, Django, PostgreSQL, Docker
            Location: Moscow
            """
        }
    }
    
    response = requests.post(f"{API_URL}/api/tasks", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

def test_find_jobs():
    """Test job search."""
    payload = {
        "user_id": "test_user_1",
        "task_type": "find_jobs",
        "input_data": {}
    }
    
    response = requests.post(f"{API_URL}/api/tasks", json=payload)
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    return response.json()

if __name__ == "__main__":
    print("Testing Job Search MAS API")
    print("=" * 50)
    
    print("\n1. Testing profile analysis...")
    result1 = test_analyze_profile()
    session_id = result1.get("session_id")
    
    if session_id:
        print(f"\n2. Testing job search with session {session_id}...")
        test_find_jobs()

