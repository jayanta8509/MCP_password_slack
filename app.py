from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
import time

from client import ask_question

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="slack forget passwords",
    description="passwords",
    version="1.0.0"
)

# CORS middleware for cross-origin requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class NexusFlowRequest(BaseModel):
    user_id: str
    query: str


@app.post("/chat/agent")
async def ask_question_endpoint(request: NexusFlowRequest):
    
    try:
        logger.info(f"Received query from user {request.user_id}: {request.query}")

        if not request.query or request.query.strip() == "":
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        if not request.user_id or request.user_id.strip() == "":
            raise HTTPException(status_code=400, detail="User ID cannot be empty")

        # Process the query with memory
        answer = await ask_question(question=request.query, user_id=request.user_id)

        logger.info(f"Successfully processed query for user {request.user_id}")
        return {
            "response": answer,
            "status_code": 200,
            "query": request.query,
            "user_id": request.user_id,
            "timestamp": time.time(),
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        logger.error(f"Error processing query: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing query: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )