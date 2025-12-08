"""Profile & Strategy Analyst Agent."""
from typing import Dict, Any
from langchain.prompts import ChatPromptTemplate
from agents.base_agent import BaseAgent
from tools.resume_parser import ResumeParser
from models.schemas import Strategy, Profile
from loguru import logger


class StrategyAgent(BaseAgent):
    """Analyzes resumes and creates personalized job search strategies."""
    
    def __init__(self):
        """Initialize strategy agent."""
        super().__init__(
            name="strategy_agent",
            role="Profile & Strategy Analyst"
        )
        self.resume_parser = ResumeParser()
    
    async def process(self, task: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process strategy analysis task with ReAct reasoning loop."""
        try:
            session_id = task.get("session_id")
            user_id = task.get("user_id")
            resume_text = task.get("resume_text") or context.get("resume_text", "")
            resume_pdf = task.get("resume_pdf") or context.get("resume_pdf")
            
            if not resume_text and not resume_pdf:
                return {
                    "success": False,
                    "error": "Resume text or PDF is required"
                }
            
            logger.info(f"{self.name} processing strategy analysis for user {user_id}")
            
            # ReAct Reasoning Loop
            max_iterations = 3
            iteration = 0
            parsed_data = None
            resume_text_extracted = resume_text
            
            while iteration < max_iterations:
                iteration += 1
                logger.debug(f"{self.name} ReAct iteration {iteration}")
                
                # THINK: Reason about what needs to be done
                if iteration == 1:
                    reasoning = "I need to parse the resume first to extract structured information"
                    logger.debug(f"{self.name} [THINK] {reasoning}")
                
                # ACT: Execute action (parse resume)
                if iteration == 1:
                    logger.debug(f"{self.name} [ACT] Parsing resume...")
                    if resume_pdf:
                        parse_result = await self.resume_parser.execute(resume_pdf=resume_pdf)
                    else:
                        parse_result = await self.resume_parser.execute(resume_text=resume_text)
                    
                    if not parse_result.get("success"):
                        return parse_result
                    
                    parsed_data = parse_result["data"]
                    if not resume_text and parsed_data.get("resume_text"):
                        resume_text_extracted = parsed_data["resume_text"]
                    
                    logger.debug(f"{self.name} [OBSERVE] Resume parsed successfully. Skills: {len(parsed_data.get('skills', []))}, Seniority: {parsed_data.get('seniority')}")
                
                # THINK: Reason about strategy generation
                if iteration == 2:
                    reasoning = f"Now I need to analyze the parsed data and generate a personalized strategy. Profile has {len(parsed_data.get('skills', []))} skills, seniority: {parsed_data.get('seniority', 'unknown')}"
                    logger.debug(f"{self.name} [THINK] {reasoning}")
                
                # ACT: Generate strategy
                if iteration == 2:
                    logger.debug(f"{self.name} [ACT] Generating strategy using LLM...")
                    strategy = await self._generate_strategy(
                        resume_text=resume_text_extracted,
                        parsed_data=parsed_data,
                        user_id=user_id
                    )
                    
                    # OBSERVE: Check if strategy is complete
                    if strategy.get("target_positions") and strategy.get("objectives"):
                        logger.debug(f"{self.name} [OBSERVE] Strategy generated successfully with {len(strategy.get('target_positions', []))} target positions")
                        break  # Success, exit loop
                    else:
                        logger.warning(f"{self.name} [OBSERVE] Strategy incomplete, retrying...")
                
                # If we reach iteration 3, we should refine or use fallback
                if iteration == 3:
                    logger.warning(f"{self.name} [THINK] Max iterations reached, using generated strategy or fallback")
                    if 'strategy' not in locals():
                        strategy = await self._generate_strategy(
                            resume_text=resume_text_extracted,
                            parsed_data=parsed_data,
                            user_id=user_id
                        )
                    break
            
            # Final result
            result = {
                "success": True,
                "profile": {
                    "user_id": user_id,
                    "resume_text": resume_text_extracted,
                    **parsed_data
                },
                "strategy": strategy,
                "react_iterations": iteration
            }
            
            # Save to PostgreSQL
            try:
                from models.database import SessionLocal, ProfileDB, StrategyDB
                db = SessionLocal()
                try:
                    # Save or update profile
                    profile_db = db.query(ProfileDB).filter(ProfileDB.user_id == user_id).first()
                    if profile_db:
                        # Update existing profile
                        profile_db.resume_text = resume_text_extracted
                        profile_db.skills = parsed_data.get("skills", [])
                        profile_db.seniority = parsed_data.get("seniority", "middle")
                        profile_db.mobility = parsed_data.get("mobility", "none")
                        profile_db.location = parsed_data.get("location")
                        profile_db.salary_expectations = parsed_data.get("salary_expectations")
                        profile_db.career_objectives = parsed_data.get("career_objectives")
                        profile_db.preferred_industries = parsed_data.get("preferred_industries", [])
                    else:
                        # Create new profile
                        profile_db = ProfileDB(
                            user_id=user_id,
                            name=parsed_data.get("name") or None,
                            email=parsed_data.get("email") or None,
                            resume_text=resume_text_extracted,
                            skills=parsed_data.get("skills", []),
                            seniority=parsed_data.get("seniority", "middle"),
                            mobility=parsed_data.get("mobility", "none"),
                            location=parsed_data.get("location"),
                            salary_expectations=parsed_data.get("salary_expectations"),
                            career_objectives=parsed_data.get("career_objectives"),
                            preferred_industries=parsed_data.get("preferred_industries", [])
                        )
                        db.add(profile_db)
                    
                    # Save or update strategy
                    strategy_id = strategy.get("strategy_id", f"strategy_{user_id}")
                    strategy_db = db.query(StrategyDB).filter(StrategyDB.strategy_id == strategy_id).first()
                    if strategy_db:
                        # Update existing strategy
                        strategy_db.objectives = strategy.get("objectives", [])
                        strategy_db.target_positions = strategy.get("target_positions", [])
                        strategy_db.target_companies = strategy.get("target_companies", [])
                        strategy_db.priority_skills = strategy.get("priority_skills", [])
                        strategy_db.timeline = str(strategy.get("timeline", "")) if isinstance(strategy.get("timeline"), dict) else strategy.get("timeline", "")
                    else:
                        # Create new strategy
                        timeline_str = str(strategy.get("timeline", "")) if isinstance(strategy.get("timeline"), dict) else strategy.get("timeline", "")
                        strategy_db = StrategyDB(
                            strategy_id=strategy_id,
                            user_id=user_id,
                            objectives=strategy.get("objectives", []),
                            target_positions=strategy.get("target_positions", []),
                            target_companies=strategy.get("target_companies", []),
                            priority_skills=strategy.get("priority_skills", []),
                            timeline=timeline_str
                        )
                        db.add(strategy_db)
                    
                    db.commit()
                    logger.info(f"{self.name} saved profile and strategy to PostgreSQL for user {user_id}")
                except Exception as db_error:
                    db.rollback()
                    logger.warning(f"{self.name} failed to save to PostgreSQL: {db_error}")
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"{self.name} PostgreSQL save error: {e}")
            
            self.update_context(session_id, {
                "profile": result["profile"],
                "strategy": strategy
            })
            
            self.publish_output(session_id, result)
            
            logger.info(f"{self.name} completed strategy analysis after {iteration} ReAct iterations")
            return result
            
        except Exception as e:
            logger.error(f"{self.name} error: {e}")
            return {"success": False, "error": str(e)}
    
    async def _generate_strategy(self, resume_text: str, parsed_data: Dict, user_id: str) -> Dict[str, Any]:
        """Generate job search strategy."""
        from langchain.prompts import ChatPromptTemplate
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are an expert career consultant. Based on the candidate's 
            resume and profile, create a personalized job search strategy. 
            Return a JSON object with:
            - objectives: list of career objectives
            - target_positions: list of target job titles
            - target_companies: list of target company types/names (can be empty)
            - priority_skills: list of skills to develop or highlight
            - timeline: suggested timeline for job search
            
            Return ONLY valid JSON."""),
            ("human", """Create a job search strategy for this candidate:

Resume: {resume_text}
Skills: {skills}
Seniority: {seniority}
Location: {location}
Career Objectives: {objectives}
Preferred Industries: {industries}

Generate the strategy:""")
        ])
        
        try:
            chain = prompt | self.llm
            response = chain.invoke({
                "resume_text": resume_text[:1000],
                "skills": ", ".join([s.get("name", "") for s in parsed_data.get("skills", [])]),
                "seniority": parsed_data.get("seniority", "middle"),
                "location": parsed_data.get("location", "Not specified"),
                "objectives": parsed_data.get("career_objectives", "Career growth"),
                "industries": ", ".join(parsed_data.get("preferred_industries", []))
            })
            
            import json
            content = response.content.strip()
            
            # Extract JSON
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            if content.startswith("{"):
                strategy_data = json.loads(content)
            else:
                start = content.find("{")
                end = content.rfind("}") + 1
                strategy_data = json.loads(content[start:end])
            
            strategy_data["strategy_id"] = f"strategy_{user_id}"
            strategy_data["user_id"] = user_id
            
            return strategy_data
            
        except Exception as e:
            logger.error(f"Error generating strategy: {e}")
            return {
                "strategy_id": f"strategy_{user_id}",
                "user_id": user_id,
                "objectives": ["Find suitable position"],
                "target_positions": ["Software Developer"],
                "target_companies": [],
                "priority_skills": [],
                "timeline": "3-6 months"
            }

