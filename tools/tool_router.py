"""Tool router for dynamic tool selection."""
from typing import Dict, Any, List, Optional
from langchain_openai import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from config import settings
from tools.base_tool import BaseTool
from tools.resume_parser import ResumeParser
from tools.job_search_api import JobSearchAPI
from tools.content_generator import ContentGenerator
from loguru import logger


class ToolRouter:
    """Router for dynamic tool selection based on context."""
    
    def __init__(self):
        """Initialize tool router."""
        self.llm = ChatOpenAI(
            model=settings.model_name,
            temperature=0.3,
            openai_api_key=settings.litellm_api_key,
            openai_api_base=settings.litellm_base_url
        )
        
        # Register available tools
        self.tools: Dict[str, BaseTool] = {
            "resume_parser": ResumeParser(),
            "job_search_api": JobSearchAPI(),
            "content_generator": ContentGenerator()
        }
    
    def get_available_tools(self) -> List[Dict[str, Any]]:
        """Get list of available tools with schemas."""
        return [tool.get_schema() for tool in self.tools.values()]
    
    async def select_tool(self, task_description: str, context: Dict[str, Any]) -> Optional[str]:
        """Select appropriate tool based on task description and context."""
        tools_list = "\n".join([
            f"- {name}: {tool.description}"
            for name, tool in self.tools.items()
        ])
        
        prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a tool selection assistant. Based on the task description 
            and context, select the most appropriate tool from the available tools.
            Return ONLY the tool name, nothing else."""),
            ("human", """Task: {task_description}
            
Context: {context}

Available tools:
{tools_list}

Select the tool name:""")
        ])
        
        try:
            chain = prompt | self.llm
            response = chain.invoke({
                "task_description": task_description,
                "context": str(context),
                "tools_list": tools_list
            })
            
            tool_name = response.content.strip().lower()
            
            # Validate tool name
            if tool_name in self.tools:
                logger.info(f"Selected tool: {tool_name}")
                return tool_name
            else:
                logger.warning(f"Invalid tool selected: {tool_name}, using default")
                return "resume_parser"  # Default fallback
                
        except Exception as e:
            logger.error(f"Error selecting tool: {e}")
            return "resume_parser"  # Default fallback
    
    async def execute_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Execute a tool by name."""
        if tool_name not in self.tools:
            return {"success": False, "error": f"Tool {tool_name} not found"}
        
        tool = self.tools[tool_name]
        try:
            result = await tool.execute(**kwargs)
            return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"success": False, "error": str(e)}
    
    def get_tool(self, tool_name: str) -> Optional[BaseTool]:
        """Get tool instance by name."""
        return self.tools.get(tool_name)

