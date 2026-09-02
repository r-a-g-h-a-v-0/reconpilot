import os
import json
from typing import List, Optional
from pydantic import BaseModel, Field

class AIRecommendation(BaseModel):
    recommendation: str  # "recommend_match", "needs_review", or "reject"
    confidence: float
    reason: str
    suggested_invoice_id: Optional[str] = None
    evidence_used: List[str] = Field(default_factory=list)

class AIProvider:
    def analyze(self, case_info: dict) -> AIRecommendation:
        raise NotImplementedError

class MockAIProvider(AIProvider):
    def analyze(self, case_info: dict) -> AIRecommendation:
        # A simple deterministic mock.
        # It never uses hidden ground truth.
        candidates = case_info.get("candidates", [])
        if candidates and candidates[0].get("score", 0) >= 60.0:
            return AIRecommendation(
                recommendation="recommend_match",
                confidence=0.8,
                reason="Mock AI suggests match based on highest scored candidate.",
                suggested_invoice_id=candidates[0].get("invoice_id"),
                evidence_used=["candidate_score"]
            )
        return AIRecommendation(
            recommendation="needs_review",
            confidence=0.5,
            reason="Mock AI cannot confidently match.",
            suggested_invoice_id=None,
            evidence_used=[]
        )

class SafeFailureProvider(AIProvider):
    def __init__(self, error_message: str):
        self.error_message = error_message
        
    def analyze(self, case_info: dict) -> AIRecommendation:
        return AIRecommendation(
            recommendation="needs_review",
            confidence=0.0,
            reason=f"AI assistance failed: {self.error_message}",
            suggested_invoice_id=None,
            evidence_used=[]
        )

class GeminiAIProvider(AIProvider):
    def __init__(self, api_key: str):
        from google import genai
        self.client = genai.Client(api_key=api_key)

    def analyze(self, case_info: dict) -> AIRecommendation:
        try:
            prompt = f"""
            You are an expert AI accountant assisting with a reconciliation case.
            The deterministic engine has flagged this case for human review due to ambiguity.
            Analyze the bank transaction and candidates below, and return a JSON object matching this schema:
            {{
                "recommendation": str, // must be one of: "recommend_match", "needs_review", "reject"
                "confidence": float,
                "reason": str,
                "suggested_invoice_id": str | null,
                "evidence_used": [str]
            }}
            
            Case Info:
            {json.dumps(case_info, indent=2)}
            """
            from google import genai
            response = self.client.models.generate_content(
                model='gemini-3.8-flash',
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json",
                ),
            )
            data = json.loads(response.text)
            
            return AIRecommendation(
                recommendation=str(data.get("recommendation", "needs_review")),
                confidence=float(data.get("confidence", 0.0)),
                reason=str(data.get("reason", "No reason provided")),
                suggested_invoice_id=data.get("suggested_invoice_id"),
                evidence_used=data.get("evidence_used", [])
            )
        except Exception as e:
            # Safe failure
            return AIRecommendation(
                recommendation="needs_review",
                confidence=0.0,
                reason=f"Gemini API error or invalid response: {str(e)}",
                suggested_invoice_id=None,
                evidence_used=[]
            )

def get_ai_provider() -> AIProvider:
    provider_name = os.environ.get("AI_PROVIDER", "mock").lower()
    if provider_name == "gemini":
        api_key = os.environ.get("GEMINI_API_KEY")
        if not api_key:
            return SafeFailureProvider("GEMINI_API_KEY is missing or invalid.")
        return GeminiAIProvider(api_key)
    return MockAIProvider()
