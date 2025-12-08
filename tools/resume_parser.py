"""Resume parsing tool with PDF support."""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from config import settings
from tools.base_tool import BaseTool
from loguru import logger
import io
import PyPDF2
import pdfplumber


class ResumeParser(BaseTool):
    """Tool for parsing resumes and extracting structured information."""
    
    def __init__(self):
        """Initialize resume parser."""
        super().__init__(
            name="resume_parser",
            description="Parse resume text or PDF file and extract structured information including skills, seniority, location, and career objectives"
        )
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=0.3,
            openai_api_key=settings.litellm_api_key,
            openai_api_base=settings.litellm_base_url
        )
    
    def _extract_text_from_pdf(self, pdf_bytes: bytes) -> str:
        """Extract text from PDF file."""
        text_parts = []
        
        # Try pdfplumber first (better for complex layouts)
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
            if text_parts:
                logger.info("Extracted text using pdfplumber")
                return "\n".join(text_parts)
        except Exception as e:
            logger.warning(f"pdfplumber extraction failed: {e}, trying PyPDF2")
        
        # Fallback to PyPDF2
        try:
            pdf_file = io.BytesIO(pdf_bytes)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            for page in pdf_reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
            if text_parts:
                logger.info("Extracted text using PyPDF2")
                return "\n".join(text_parts)
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {e}")
            raise ValueError(f"Failed to extract text from PDF: {e}")
        
        raise ValueError("Could not extract text from PDF")
    
    async def execute(self, 
                     resume_text: Optional[str] = None,
                     resume_pdf: Optional[bytes] = None) -> Dict[str, Any]:
        """Parse resume text or PDF and extract structured information."""
        try:
            # Extract text from PDF if provided
            if resume_pdf:
                resume_text = self._extract_text_from_pdf(resume_pdf)
            elif not resume_text:
                raise ValueError("Either resume_text or resume_pdf must be provided")
            
            if not resume_text or len(resume_text.strip()) < 10:
                raise ValueError("Resume text is too short or empty")
            
            prompt = ChatPromptTemplate.from_messages([
                ("system", """You are an expert resume parser. Extract structured information from resumes.
                Return a JSON object with the following fields:
                - skills: list of objects with name, level (beginner/intermediate/advanced/expert), years_experience
                - seniority: one of "junior", "middle", "senior", "lead"
                - mobility: one of "none", "local", "regional", "national", "international"
                - location: city or region
                - salary_expectations: integer or null
                - career_objectives: string or null
                - preferred_industries: list of strings
                
                Return ONLY valid JSON, no additional text."""),
                ("human", "Parse this resume:\n\n{resume_text}")
            ])
            
            chain = prompt | self.llm
            response = chain.invoke({"resume_text": resume_text})
            
            import json
            content = response.content.strip()
            
            # Extract JSON from response
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            # Remove markdown code blocks if present
            if content.startswith("{"):
                parsed_data = json.loads(content)
            else:
                # Try to find JSON in the text
                start = content.find("{")
                end = content.rfind("}") + 1
                if start >= 0 and end > start:
                    parsed_data = json.loads(content[start:end])
                else:
                    raise ValueError("No JSON found in response")
            
            result = {
                "skills": parsed_data.get("skills", []),
                "seniority": parsed_data.get("seniority", "middle"),
                "mobility": parsed_data.get("mobility", "local"),
                "location": parsed_data.get("location"),
                "salary_expectations": parsed_data.get("salary_expectations"),
                "career_objectives": parsed_data.get("career_objectives"),
                "preferred_industries": parsed_data.get("preferred_industries", []),
                "resume_text": resume_text  # Include extracted text
            }
            
            logger.info("Successfully parsed resume")
            return {"success": True, "data": result}
            
        except Exception as e:
            logger.error(f"Error parsing resume: {e}")
            return {
                "success": False,
                "error": str(e),
                "data": {
                    "skills": [],
                    "seniority": "middle",
                    "mobility": "local",
                    "location": None,
                    "salary_expectations": None,
                    "career_objectives": None,
                    "preferred_industries": [],
                    "resume_text": resume_text if resume_text else ""
                }
            }
    
    def _get_parameters(self) -> Dict[str, Any]:
        """Get tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "resume_text": {
                    "type": "string",
                    "description": "The resume text to parse (optional if resume_pdf provided)"
                },
                "resume_pdf": {
                    "type": "string",
                    "format": "binary",
                    "description": "PDF file bytes (optional if resume_text provided)"
                }
            },
            "required": []
        }
