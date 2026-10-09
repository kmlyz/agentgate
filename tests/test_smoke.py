"""Smoke test to verify that the core dependencies can be imported successfully."""

def test_imports():
    import dotenv
    import google.adk
    import google.genai
    import pydantic
    assert google.adk is not None
    assert google.genai is not None
    assert pydantic is not None
    assert dotenv is not None
