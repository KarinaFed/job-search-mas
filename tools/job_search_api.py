"""Job search API tool for HH.ru."""
import httpx
from typing import List, Dict, Any, Optional
from models.schemas import JobPosting, SeniorityLevel
from config import settings
from tools.base_tool import BaseTool
from loguru import logger
from datetime import datetime, timedelta


class JobSearchAPI(BaseTool):
    """Tool for searching jobs via HH.ru API."""
    
    # Common city name mappings (fallback cache for popular cities only)
    # Most cities will be resolved via HH.ru API dynamically
    CITY_TO_AREA_CODE = {
        "москва": "1",
        "санкт-петербург": "2",
        "спб": "2",
        "питер": "2",
    }
    
    def __init__(self):
        """Initialize job search API."""
        super().__init__(
            name="job_search_api",
            description="Search for job postings on HH.ru and other job boards"
        )
        self.hh_api_url = settings.hh_api_url
        self.hh_client_id = settings.hh_client_id
        self.hh_client_secret = settings.hh_client_secret
        self.hh_api_key = settings.hh_api_key
        self.client = httpx.AsyncClient(timeout=30.0)
        self._access_token: Optional[str] = None
        self._token_expires_at: Optional[datetime] = None
    
    async def _get_access_token(self) -> Optional[str]:
        """Get OAuth2 access token using Client Credentials flow."""
        # Check if we have a valid cached token
        if self._access_token and self._token_expires_at:
            if datetime.now() < self._token_expires_at:
                return self._access_token
        
        # If we have direct API key, use it
        if self.hh_api_key:
            return self.hh_api_key
        
        # Get new token via OAuth2
        if not self.hh_client_id or not self.hh_client_secret:
            logger.warning("HH.ru OAuth2 credentials not configured")
            return None
        
        try:
            token_url = f"{self.hh_api_url}/oauth/token"
            data = {
                "grant_type": "client_credentials",
                "client_id": self.hh_client_id,
                "client_secret": self.hh_client_secret
            }
            
            response = await self.client.post(token_url, data=data)
            
            if response.status_code == 200:
                token_data = response.json()
                self._access_token = token_data.get("access_token")
                expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
                self._token_expires_at = datetime.now().replace(microsecond=0) + \
                    timedelta(seconds=expires_in - 60)  # Refresh 1 min before expiry
                logger.info("Successfully obtained HH.ru access token")
                return self._access_token
            else:
                logger.warning(f"Failed to get access token: {response.status_code} - {response.text}. Continuing without token (public API).")
                return None
        except Exception as e:
            logger.warning(f"Error getting access token: {e}. Continuing without token (public API).")
            return None
    
    async def _normalize_area(self, area: str) -> Optional[str]:
        """Convert city name to HH.ru area code using API lookup."""
        if not area:
            return None
        
        # If already a number, return as is
        if area.isdigit():
            return area
        
        # Normalize area name
        area_lower = area.lower().strip()
        # Remove common prefixes like "г. ", "город "
        area_lower = area_lower.replace("г. ", "").replace("город ", "").strip()
        
        # Check cached mapping first
        if area_lower in self.CITY_TO_AREA_CODE:
            return self.CITY_TO_AREA_CODE[area_lower]
        
        # Try to find area code via HH.ru API
        try:
            response = await self.client.get(
                f"{self.hh_api_url}/areas",
                headers={"User-Agent": "JobSearchMAS/1.0"},
                timeout=5.0
            )
            
            if response.status_code == 200:
                areas = response.json()
                area_code = self._find_area_code(areas, area_lower)
                if area_code:
                    logger.info(f"Mapped city '{area}' to HH.ru area code {area_code}")
                    return area_code
        except Exception as e:
            logger.debug(f"Could not fetch areas from HH.ru API: {e}. Using fallback.")
        
        # Fallback: try partial match in cached mappings
        for city, code in self.CITY_TO_AREA_CODE.items():
            if city in area_lower or area_lower in city:
                logger.info(f"Mapped city '{area}' to HH.ru area code {code} (fallback)")
                return code
        
        logger.info(f"Could not map city '{area}' to HH.ru area code. Searching without area filter.")
        return None
    
    def _find_area_code(self, areas: list, city_name: str) -> Optional[str]:
        """Recursively search for area code by city name in HH.ru areas tree."""
        for area in areas:
            area_name = area.get("name", "").lower()
            
            # Exact match
            if area_name == city_name:
                return str(area.get("id"))
            
            # Partial match
            if city_name in area_name or area_name in city_name:
                return str(area.get("id"))
            
            # Check child areas recursively
            if area.get("areas"):
                result = self._find_area_code(area["areas"], city_name)
                if result:
                    return result
        
        return None
    
    async def execute(self, 
                     query: str,
                     area: Optional[str] = None,
                     salary: Optional[int] = None,
                     experience: Optional[str] = None,
                     per_page: int = 20) -> Dict[str, Any]:
        """Search jobs on HH.ru."""
        try:
            # Get access token (optional - HH.ru public API works without it)
            token = await self._get_access_token()
            
            params = {"text": query, "per_page": per_page, "page": 0}
            
            # Normalize area to HH.ru area code
            if area:
                area_code = await self._normalize_area(area)
                if area_code:
                    params["area"] = area_code
                # If normalization failed, don't add area parameter
            
            if salary:
                params["salary"] = salary
            if experience:
                params["experience"] = experience
            
            headers = {"User-Agent": "JobSearchMAS/1.0"}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            
            response = await self.client.get(
                f"{self.hh_api_url}/vacancies",
                params=params,
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                jobs = []
                
                for item in data.get("items", [])[:per_page]:
                    vacancy_id = item.get("id")
                    if vacancy_id:
                        full_vacancy = await self._get_vacancy_details(vacancy_id, token)
                        if full_vacancy:
                            jobs.append(full_vacancy)
                
                logger.info(f"Found {len(jobs)} jobs on HH.ru")
                return {"success": True, "jobs": jobs, "count": len(jobs)}
            else:
                error_text = response.text
                logger.warning(f"HH.ru API returned status {response.status_code}: {error_text}")
                
                # If error is about area, try without area filter
                if response.status_code == 400 and "area" in error_text.lower():
                    logger.info("Retrying search without area filter...")
                    params.pop("area", None)
                    response = await self.client.get(
                        f"{self.hh_api_url}/vacancies",
                        params=params,
                        headers=headers
                    )
                    if response.status_code == 200:
                        data = response.json()
                        jobs = []
                        for item in data.get("items", [])[:per_page]:
                            vacancy_id = item.get("id")
                            if vacancy_id:
                                full_vacancy = await self._get_vacancy_details(vacancy_id, token)
                                if full_vacancy:
                                    jobs.append(full_vacancy)
                        logger.info(f"Found {len(jobs)} jobs on HH.ru (without area filter)")
                        return {"success": True, "jobs": jobs, "count": len(jobs)}
                
                return {"success": False, "jobs": self._get_mock_jobs(query), "count": len(self._get_mock_jobs(query))}
                
        except Exception as e:
            logger.error(f"Error searching HH.ru: {e}")
            return {"success": False, "jobs": self._get_mock_jobs(query), "count": len(self._get_mock_jobs(query))}
    
    async def _get_vacancy_details(self, vacancy_id: str, token: Optional[str] = None) -> Optional[JobPosting]:
        """Get detailed vacancy information."""
        try:
            headers = {"User-Agent": "JobSearchMAS/1.0"}
            
            if token:
                headers["Authorization"] = f"Bearer {token}"
            elif self.hh_api_key:
                headers["Authorization"] = f"Bearer {self.hh_api_key}"
            
            response = await self.client.get(
                f"{self.hh_api_url}/vacancies/{vacancy_id}",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                
                salary_min = None
                salary_max = None
                if data.get("salary"):
                    salary_min = data["salary"].get("from")
                    salary_max = data["salary"].get("to")
                
                skills_required = []
                if data.get("key_skills"):
                    skills_required = [skill.get("name", "") for skill in data["key_skills"]]
                
                seniority = None
                exp_req = data.get("experience", {}).get("id", "")
                if exp_req == "noExperience":
                    seniority = SeniorityLevel.JUNIOR
                elif exp_req == "between1And3":
                    seniority = SeniorityLevel.MIDDLE
                elif exp_req == "between3And6":
                    seniority = SeniorityLevel.SENIOR
                elif exp_req == "moreThan6":
                    seniority = SeniorityLevel.LEAD
                
                # Extract requirements from description or snippet
                description = data.get("description", "") or data.get("snippet", {}).get("requirement", "")
                requirements = [description[:500]] if description else []
                
                # Parse posted date
                posted_at = None
                if data.get("published_at"):
                    try:
                        posted_at = datetime.fromisoformat(data.get("published_at").replace("Z", "+00:00"))
                    except:
                        pass
                
                return JobPosting(
                    job_id=str(vacancy_id),
                    title=data.get("name", ""),
                    company=data.get("employer", {}).get("name", ""),
                    description=description[:2000] if description else "",
                    requirements=requirements,
                    skills_required=skills_required,
                    location=data.get("area", {}).get("name", ""),
                    salary_min=salary_min,
                    salary_max=salary_max,
                    seniority_level=seniority,
                    url=data.get("alternate_url", ""),
                    source="hh.ru",
                    posted_at=posted_at
                )
            return None
        except Exception as e:
            logger.error(f"Error getting vacancy details: {e}")
            return None
    
    def _get_mock_jobs(self, query: str) -> List[JobPosting]:
        """Return mock jobs for development/testing."""
        return [
            JobPosting(
                job_id="mock_1",
                title=f"Python Developer - {query}",
                company="Tech Corp",
                description="We are looking for an experienced Python developer with Django experience.",
                requirements=["3+ years Python", "Django experience", "PostgreSQL"],
                skills_required=["Python", "Django", "PostgreSQL", "REST API"],
                location="Moscow",
                salary_min=150000,
                salary_max=250000,
                seniority_level=SeniorityLevel.MIDDLE,
                url="https://hh.ru/vacancy/mock_1",
                source="hh.ru"
            ),
            JobPosting(
                job_id="mock_2",
                title=f"Senior {query} Engineer",
                company="StartupXYZ",
                description="Join our team as a senior engineer with leadership experience.",
                requirements=["5+ years experience", "Team leadership"],
                skills_required=["Python", "AWS", "Docker", "Kubernetes"],
                location="Saint Petersburg",
                salary_min=300000,
                salary_max=400000,
                seniority_level=SeniorityLevel.SENIOR,
                url="https://hh.ru/vacancy/mock_2",
                source="hh.ru"
            )
        ]
    
    def _get_parameters(self) -> Dict[str, Any]:
        """Get tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Job search query"},
                "area": {"type": "string", "description": "Area code (e.g., 1 for Moscow)"},
                "salary": {"type": "integer", "description": "Minimum salary"},
                "experience": {"type": "string", "description": "Experience level"},
                "per_page": {"type": "integer", "description": "Number of results", "default": 20}
            },
            "required": ["query"]
        }
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
