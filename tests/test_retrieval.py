import pytest
from backend.app.services.retrieval import FactCheckRetriever

@pytest.mark.asyncio
async def test_degrades_without_key():
    result=await FactCheckRetriever(None).search("claim")
    assert result.items==[] and "not configured" in result.warning
