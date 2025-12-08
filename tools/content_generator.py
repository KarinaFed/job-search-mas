"""Content generation tool for cover letters and resume adaptation."""
from typing import Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from config import settings
from models.schemas import Profile, JobPosting
from tools.base_tool import BaseTool
from loguru import logger


class ContentGenerator(BaseTool):
    """Tool for generating personalized content."""
    
    def __init__(self):
        """Initialize content generator."""
        super().__init__(
            name="content_generator",
            description="Generate personalized cover letters and adapt resumes for specific job positions"
        )
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=0.7,
            openai_api_key=settings.litellm_api_key,
            openai_api_base=settings.litellm_base_url
        )
    
    async def execute(self, 
                     content_type: str,
                     profile: Dict[str, Any],
                     job: Dict[str, Any],
                     additional_context: Optional[str] = None) -> Dict[str, Any]:
        """Generate content (cover letter or adapted resume)."""
        if content_type == "cover_letter":
            return await self._generate_cover_letter(profile, job, additional_context)
        elif content_type == "adapted_resume":
            return await self._adapt_resume(profile, job)
        else:
            return {"success": False, "error": f"Unknown content type: {content_type}"}
    
    async def _generate_cover_letter(self, profile: Dict, job: Dict, context: Optional[str]) -> Dict[str, Any]:
        """Generate personalized cover letter in Russian."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Вы - эксперт по карьерному консультированию. Напишите убедительное, 
            персонализированное сопроводительное письмо (300-400 слов) на русском языке, которое 
            подчеркивает релевантный опыт и навыки кандидата для конкретной вакансии. 
            Письмо должно быть профессиональным, структурированным и убедительным.
            
            Важно: Все письмо должно быть написано на русском языке!"""),
            ("human", """Напишите сопроводительное письмо на русском языке:

Информация о кандидате:
Имя и контакты (из резюме): {candidate_info}
Навыки: {skills}
Уровень: {seniority}
Цели: {objectives}

Вакансия: {job_title} в {company}
Требования: {requirements}
Описание: {job_description}
Контекст: {additional_context}

ВАЖНО: 
- Используй реальное имя кандидата из резюме (НЕ плейсхолдеры типа [Ваше имя])
- Используй реальные контакты из резюме (телефон, email) вместо плейсхолдеров
- Письмо должно заканчиваться подписью с реальным именем и контактами

Напишите сопроводительное письмо на русском языке с реальными данными кандидата:""")
        ])
        
        try:
            # Extract candidate info from resume text
            resume_text = profile.get("resume_text", "")
            candidate_info = self._extract_candidate_info(resume_text)
            
            chain = prompt | self.llm
            response = chain.invoke({
                "candidate_info": candidate_info,
                "skills": profile.get("skills_str", ""),
                "seniority": profile.get("seniority", "middle"),
                "objectives": profile.get("career_objectives", "Career growth"),
                "job_title": job.get("title", ""),
                "company": job.get("company", ""),
                "requirements": ", ".join(job.get("requirements", []))[:500],
                "job_description": job.get("description", "")[:500],
                "additional_context": context or "None"
            })
            
            cover_letter = response.content.strip()
            logger.info("Generated cover letter")
            return {"success": True, "content": cover_letter, "type": "cover_letter"}
        except Exception as e:
            logger.error(f"Error generating cover letter: {e}")
            return {"success": False, "error": str(e)}
    
    async def _adapt_resume(self, profile: Dict, job: Dict) -> Dict[str, Any]:
        """Adapt resume to highlight relevant skills in Russian."""
        prompt = ChatPromptTemplate.from_messages([
            ("system", """Вы - эксперт по написанию резюме. Адаптируйте резюме кандидата 
            так, чтобы оно лучше соответствовало требованиям вакансии. Переупорядочьте разделы, 
            подчеркните релевантный опыт и скорректируйте формулировки в соответствии с 
            описанием вакансии.
            
            Важно: Все резюме должно быть написано на русском языке! Сохраните структуру и 
            форматирование оригинального резюме, но адаптируйте содержание под вакансию."""),
            ("human", """Адаптируйте это резюме для вакансии на русском языке:

Резюме: {original_resume}
Вакансия: {job_title} в {company}
Требования: {requirements}
Необходимые навыки: {skills_required}

Создайте адаптированное резюме на русском языке:""")
        ])
        
        try:
            chain = prompt | self.llm
            response = chain.invoke({
                "original_resume": profile.get("resume_text", "")[:2000],
                "job_title": job.get("title", ""),
                "company": job.get("company", ""),
                "requirements": ", ".join(job.get("requirements", [])),
                "skills_required": ", ".join(job.get("skills_required", []))
            })
            
            adapted_resume = response.content.strip()
            logger.info("Generated adapted resume")
            return {"success": True, "content": adapted_resume, "type": "adapted_resume"}
        except Exception as e:
            logger.error(f"Error adapting resume: {e}")
            return {"success": False, "error": str(e)}
    
    def _extract_candidate_info(self, resume_text: str) -> str:
        """Extract candidate name and contact info from resume text."""
        if not resume_text:
            return "Информация о кандидате не найдена"
        
        lines = resume_text.split('\n')
        info_parts = []
        
        # Try to extract name (usually in first few lines)
        for i, line in enumerate(lines[:10]):
            line = line.strip()
            # Look for name pattern (usually first line with name)
            if i == 0 and line and len(line) < 100:
                info_parts.append(f"Имя: {line}")
            # Look for phone
            if 'телефон' in line.lower() or 'phone' in line.lower() or '+' in line or any(c.isdigit() for c in line):
                if len(line) < 100:
                    info_parts.append(line)
            # Look for email
            if '@' in line and ('.com' in line or '.ru' in line or '.org' in line):
                info_parts.append(line)
            # Look for telegram
            if '@' in line and ('tg' in line.lower() or 'telegram' in line.lower()):
                info_parts.append(line)
        
        if not info_parts:
            # Fallback: extract first meaningful lines
            for line in lines[:5]:
                if line.strip() and len(line.strip()) < 100:
                    info_parts.append(line.strip())
                    if len(info_parts) >= 3:
                        break
        
        return "\n".join(info_parts[:5]) if info_parts else resume_text[:300]
    
    def _get_parameters(self) -> Dict[str, Any]:
        """Get tool parameters schema."""
        return {
            "type": "object",
            "properties": {
                "content_type": {
                    "type": "string",
                    "enum": ["cover_letter", "adapted_resume"],
                    "description": "Type of content to generate"
                },
                "profile": {"type": "object", "description": "Candidate profile"},
                "job": {"type": "object", "description": "Job posting"},
                "additional_context": {"type": "string", "description": "Additional context"}
            },
            "required": ["content_type", "profile", "job"]
        }
