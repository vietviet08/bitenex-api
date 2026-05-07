# =============================================================================
# Semantic Smart Search - API Router
# =============================================================================

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List

# Placeholder for real DB session dependency
from app.shared.dto import BaseDTO

router = APIRouter(prefix="/search", tags=["Smart Search"])

class SmartSearchResult(BaseDTO):
    id: str
    name: str
    description: str
    match_score: float

@router.get("/semantic", response_model=List[SmartSearchResult])
async def search_semantic(
    q: str = Query(..., description="Natural language query, e.g. 'Món gì nóng dễ tiêu, vị gừng'"),
    limit: int = Query(10, ge=1, le=50)
):
    """
    Semantic Smart Search using Vector Database and OpenAI Embeddings.
    Instead of hard keywords, it understands context and culinary desires.
    """
    # TODO: Initialize OpenAI Client
    # client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    
    # TODO: Generate embedding for the user's query
    # response = await client.embeddings.create(input=q, model="text-embedding-3-small")
    # query_vector = response.data[0].embedding
    
    # TODO: Perform similarity search using pgvector in PostgreSQL
    # results = await db.execute(
    #     select(MenuItem, MenuItem.embedding.cosine_distance(query_vector).label('distance'))
    #     .order_by('distance')
    #     .limit(limit)
    # )
    
    # Mocked Response for structural setup
    return [
        SmartSearchResult(
            id="mock-item-1",
            name="Cháo Gà Gừng Hành",
            description="Cháo gà nóng hổi, nấu chậm với gừng và hành lá, rất dễ tiêu.",
            match_score=0.92
        ),
        SmartSearchResult(
            id="mock-item-2",
            name="Phở Gà Ta Nước Trong",
            description="Phở gà nước trong vắt, ấm bụng, ít béo.",
            match_score=0.85
        )
    ]
