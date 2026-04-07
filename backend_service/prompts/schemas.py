"""
HackT Sovereign Core - Prompt & Output Schemas (v2.0)
======================================================
Pydantic V2 models for validating prompt routing and LLM structured outputs.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional, Literal, Dict, Any
from enum import Enum

class ThreatLevel(str, Enum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class Vulnerability(BaseModel):
    model_config = ConfigDict(strict=True)
    type: str = Field(..., description="Vulnerability type (e.g., XSS, SQLi)")
    file: str = Field(..., description="File path where vulnerability was found")
    line: Optional[int] = Field(None, description="Line number (if known)")
    description: str = Field(..., description="Plain-language description")
    suggested_fix: str = Field(..., description="Brief mitigation step")

class CodeAnalysisOutput(BaseModel):
    """
    The exact JSON structure the LLM MUST return for code audits.
    🚨 UPGRADE: Includes original_code for React Diff Bridge
    """
    threat_level: ThreatLevel = Field(..., description="Overall threat severity")
    vulnerabilities: List[Vulnerability] = Field(..., description="List of found vulnerabilities")
    confidence: float = Field(..., description="Confidence score (0.0 to 1.0)")
    citations: List[str] = Field(default_factory=list, description="Source citations from Vault")
    
    # 🚨 DIFF BRIDGE FIELDS
    original_code: Optional[str] = Field(None, description="The original vulnerable code snippet")
    diff_start_line: Optional[int] = Field(None, description="Starting line number for diff display")
    
    @field_validator('confidence')
    @classmethod
    def check_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError('Confidence must be between 0.0 and 1.0')
        return v