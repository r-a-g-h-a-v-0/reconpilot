import os
from unittest.mock import patch, MagicMock
from backend.ai_provider import get_ai_provider, MockAIProvider, GeminiAIProvider, SafeFailureProvider

def test_mock_provider_default():
    # If AI_PROVIDER is not set, it should default to mock
    if "AI_PROVIDER" in os.environ:
        del os.environ["AI_PROVIDER"]
    provider = get_ai_provider()
    assert isinstance(provider, MockAIProvider)

def test_gemini_not_activated_when_mock_selected():
    os.environ["AI_PROVIDER"] = "mock"
    os.environ["GEMINI_API_KEY"] = "fake-key"
    provider = get_ai_provider()
    assert isinstance(provider, MockAIProvider)
    # Even with a valid key, if mock is selected, mock is used.

def test_gemini_requires_api_key():
    os.environ["AI_PROVIDER"] = "gemini"
    if "GEMINI_API_KEY" in os.environ:
        del os.environ["GEMINI_API_KEY"]
    provider = get_ai_provider()
    assert isinstance(provider, SafeFailureProvider)
    assert "missing or invalid" in provider.error_message

@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_gemini_provider_instantiates(mock_model, mock_configure):
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "fake-key"
    provider = get_ai_provider()
    assert isinstance(provider, GeminiAIProvider)
    mock_configure.assert_called_with(api_key="fake-key")

@patch("google.generativeai.configure")
@patch("google.generativeai.GenerativeModel")
def test_gemini_malformed_response_fails_safely(mock_model, mock_configure):
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "fake-key"
    provider = get_ai_provider()
    
    # Mock model generate_content to return malformed JSON
    mock_response = MagicMock()
    mock_response.text = "NOT JSON"
    provider.model.generate_content.return_value = mock_response
    
    rec = provider.analyze({"candidates": []})
    assert rec.recommendation == "needs_review"
    assert rec.confidence == 0.0
    assert "invalid response" in rec.reason

def test_mock_provider_generates_schema():
    provider = MockAIProvider()
    case_info = {
        "candidates": [{"invoice_id": "INV-123", "score": 75.0}]
    }
    rec = provider.analyze(case_info)
    assert rec.recommendation == "recommend_match"
    assert rec.suggested_invoice_id == "INV-123"

