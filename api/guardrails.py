"""Guardrails and safety features."""
import re
from typing import Dict, Any, List
from loguru import logger


# Prompt injection patterns
INJECTION_PATTERNS = [
    r"ignore\s+(previous|all|above)",
    r"forget\s+(previous|all|above)",
    r"system\s*:",
    r"assistant\s*:",
    r"user\s*:",
    r"<\|.*?\|>",
    r"\[INST\]",
    r"\[/INST\]",
]


def validate_input(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and sanitize input data."""
    try:
        # Check for prompt injection
        text_fields = _extract_text_fields(data)
        for field, text in text_fields:
            if _detect_prompt_injection(text):
                logger.warning(f"Potential prompt injection detected in field: {field}")
                return {
                    "valid": False,
                    "error": f"Invalid input detected in field: {field}"
                }
        
        # Validate task type
        task_type = data.get("task_type")
        valid_task_types = [
            "analyze_profile",
            "find_jobs",
            "create_application",
            "full_journey"
        ]
        if task_type and task_type not in valid_task_types:
            return {
                "valid": False,
                "error": f"Invalid task_type: {task_type}"
            }
        
        # Validate required fields
        if not data.get("user_id"):
            return {
                "valid": False,
                "error": "user_id is required"
            }
        
        return {"valid": True}
        
    except Exception as e:
        logger.error(f"Input validation error: {e}")
        return {"valid": False, "error": str(e)}


def sanitize_output(data: Dict[str, Any]) -> Dict[str, Any]:
    """Sanitize output data."""
    try:
        # Remove sensitive information
        sanitized = data.copy()
        
        # Remove potential sensitive fields
        sensitive_keys = ["api_key", "password", "token", "secret"]
        for key in list(sanitized.keys()):
            if any(sk in key.lower() for sk in sensitive_keys):
                sanitized.pop(key)
        
        # Sanitize nested dictionaries
        if isinstance(sanitized.get("result"), dict):
            sanitized["result"] = _sanitize_dict(sanitized["result"])
        
        return sanitized
        
    except Exception as e:
        logger.error(f"Output sanitization error: {e}")
        return data


def _detect_prompt_injection(text: str) -> bool:
    """Detect potential prompt injection attacks."""
    if not isinstance(text, str):
        return False
    
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower, re.IGNORECASE):
            return True
    
    return False


def _extract_text_fields(data: Dict[str, Any], prefix: str = "") -> List[tuple]:
    """Extract all text fields from nested dictionary."""
    fields = []
    
    for key, value in data.items():
        field_name = f"{prefix}.{key}" if prefix else key
        
        if isinstance(value, str):
            fields.append((field_name, value))
        elif isinstance(value, dict):
            fields.extend(_extract_text_fields(value, field_name))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, str):
                    fields.append((f"{field_name}[{i}]", item))
                elif isinstance(item, dict):
                    fields.extend(_extract_text_fields(item, f"{field_name}[{i}]"))
    
    return fields


def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize dictionary."""
    sanitized = {}
    for key, value in data.items():
        if isinstance(value, dict):
            sanitized[key] = _sanitize_dict(value)
        elif isinstance(value, list):
            sanitized[key] = [
                _sanitize_dict(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            sanitized[key] = value
    return sanitized


def validate_schema(data: Dict[str, Any], schema: Dict[str, Any]) -> bool:
    """Validate data against schema (simplified)."""
    # This is a simplified schema validation
    # For production, use jsonschema library
    required_fields = schema.get("required", [])
    
    for field in required_fields:
        if field not in data:
            return False
    
    return True

