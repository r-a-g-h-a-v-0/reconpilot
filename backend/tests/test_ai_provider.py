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

@patch("google.genai.Client")
def test_gemini_provider_instantiates(mock_client):
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "fake-key"
    provider = get_ai_provider()
    assert isinstance(provider, GeminiAIProvider)
    mock_client.assert_called_with(api_key="fake-key")

@patch("google.genai.Client")
def test_gemini_malformed_response_fails_safely(mock_client_class):
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "fake-key"

    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    provider = get_ai_provider()

    mock_response = MagicMock()
    mock_response.text = "NOT JSON"
    mock_client.models.generate_content.return_value = mock_response

    rec = provider.analyze({"candidates": []})
    assert rec.recommendation == "needs_review"
    assert rec.confidence == 0.0
    assert "invalid response" in rec.reason

@patch("google.genai.Client")
def test_gemini_valid_structured_response_parsed(mock_client_class):
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "fake-key"

    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    provider = get_ai_provider()

    mock_response = MagicMock()
    mock_response.text = '{"recommendation": "recommend_match", "confidence": 0.85, "reason": "Looks good", "suggested_invoice_id": "INV-123", "evidence_used": ["date"]}'
    mock_client.models.generate_content.return_value = mock_response

    rec = provider.analyze({"candidates": []})
    assert rec.recommendation == "recommend_match"
    assert rec.confidence == 0.85
    assert rec.suggested_invoice_id == "INV-123"

@patch("google.genai.Client")
def test_gemini_invalid_recommendation_value(mock_client_class):
    os.environ["AI_PROVIDER"] = "gemini"
    os.environ["GEMINI_API_KEY"] = "fake-key"

    mock_client = MagicMock()
    mock_client_class.return_value = mock_client
    provider = get_ai_provider()

    mock_response = MagicMock()
    mock_response.text = '{"recommendation": "do_it", "confidence": "high", "reason": "why not"}'
    mock_client.models.generate_content.return_value = mock_response

    rec = provider.analyze({"candidates": []})
    assert rec.recommendation == "needs_review"
    assert rec.confidence == 0.0
    assert "error or invalid response" in rec.reason

def test_mock_provider_generates_schema():
    provider = MockAIProvider()
    case_info = {
        "candidates": [{"invoice_id": "INV-123", "score": 75.0}]
    }
    rec = provider.analyze(case_info)
    assert rec.recommendation == "recommend_match"
    assert rec.suggested_invoice_id == "INV-123"

