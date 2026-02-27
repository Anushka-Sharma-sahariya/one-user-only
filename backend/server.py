from fastapi import FastAPI, APIRouter, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
import uuid
from datetime import datetime, timezone
from emergentintegrations.llm.chat import LlmChat, UserMessage
import json
import re


ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")


# Define Models
class StatusCheck(BaseModel):
    model_config = ConfigDict(extra="ignore")  # Ignore MongoDB's _id field
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    client_name: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class StatusCheckCreate(BaseModel):
    client_name: str


# PRD Models
class CompressRequest(BaseModel):
    problem: str
    coreUser: str
    change: str
    metrics: str
    outOfScope: str


class ClarityScore(BaseModel):
    overall: float
    persona_specificity: float
    metric_strength: float
    problem_sharpness: float
    bloat_penalty: float


class CompressResponse(BaseModel):
    status: str
    prd: Optional[str] = None
    word_count: Optional[int] = None
    clarity_score: Optional[ClarityScore] = None
    bloat_words_detected: Optional[List[str]] = None
    callouts: Optional[List[str]] = None
    rejection_reason: Optional[str] = None


# Add your routes to the router instead of directly to app
@api_router.get("/")
async def root():
    return {"message": "Hello World"}

@api_router.post("/status", response_model=StatusCheck)
async def create_status_check(input: StatusCheckCreate):
    status_dict = input.model_dump()
    status_obj = StatusCheck(**status_dict)
    
    # Convert to dict and serialize datetime to ISO string for MongoDB
    doc = status_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    
    _ = await db.status_checks.insert_one(doc)
    return status_obj

@api_router.get("/status", response_model=List[StatusCheck])
async def get_status_checks():
    # Exclude MongoDB's _id field from the query results
    status_checks = await db.status_checks.find({}, {"_id": 0}).to_list(1000)
    
    # Convert ISO string timestamps back to datetime objects
    for check in status_checks:
        if isinstance(check['timestamp'], str):
            check['timestamp'] = datetime.fromisoformat(check['timestamp'])
    
    return status_checks


@api_router.post("/compress", response_model=CompressResponse)
async def compress_prd(request: CompressRequest):
    """Compress PRD using Claude API"""
    try:
        # Server-side validation
        if not all([request.problem, request.coreUser, request.change, request.metrics, request.outOfScope]):
            raise HTTPException(status_code=400, detail="All fields are required")
        
        # Check for multiple users in Core User field
        if ',' in request.coreUser or ' and ' in request.coreUser.lower() or '/' in request.coreUser:
            raise HTTPException(status_code=400, detail="Pick one user. Not a committee.")
        
        # Check if metrics contain numbers
        if not re.search(r'\d', request.metrics):
            raise HTTPException(status_code=400, detail="Metrics need numbers.")
        
        # Initialize Claude chat
        api_key = os.environ.get('EMERGENT_LLM_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="API key not configured")
        
        chat = LlmChat(
            api_key=api_key,
            session_id=str(uuid.uuid4()),
            system_message="You are an opinionated product coach helping early PMs write disciplined PRDs. Enforce max 300 words. Only one core user. Maximum 3 measurable metrics with numbers. Remove vague language and buzzwords. Strike through buzzwords using markdown (~~word~~). Return structured JSON only."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Create prompt
        prompt = f"""Write a PRD using the following inputs:

Problem: {request.problem}
Core User: {request.coreUser}
Expected Change: {request.change}
Success Metrics: {request.metrics}
Out of Scope: {request.outOfScope}

Return JSON in this exact format:
{{
  "status": "accepted" or "rejected",
  "prd": "the compressed PRD with sections: Problem, Core User, Solution, Success Metrics, Out of Scope",
  "word_count": number,
  "clarity_score": {{
    "overall": number between 0-10,
    "persona_specificity": number between 0-10,
    "metric_strength": number between 0-10,
    "problem_sharpness": number between 0-10,
    "bloat_penalty": number between 0-10
  }},
  "bloat_words_detected": ["list", "of", "buzzwords"],
  "callouts": ["list of suggestions or critiques"],
  "rejection_reason": "only if status is rejected"
}}

If the input is too vague, unfocused, or impossible to compress into a disciplined PRD, set status to "rejected" and explain why."""
        
        user_message = UserMessage(text=prompt)
        response = await chat.send_message(user_message)
        
        # Parse JSON response
        try:
            # Extract JSON from response (handle potential markdown code blocks)
            response_text = response.strip()
            if response_text.startswith('```'):
                # Remove markdown code block formatting
                lines = response_text.split('\n')
                response_text = '\n'.join(lines[1:-1]) if len(lines) > 2 else response_text
            
            result = json.loads(response_text)
            
            # Create response object
            if result.get('status') == 'rejected':
                return CompressResponse(
                    status='rejected',
                    rejection_reason=result.get('rejection_reason', 'PRD could not be compressed')
                )
            
            return CompressResponse(
                status='accepted',
                prd=result.get('prd', ''),
                word_count=result.get('word_count', 0),
                clarity_score=ClarityScore(**result.get('clarity_score', {})),
                bloat_words_detected=result.get('bloat_words_detected', []),
                callouts=result.get('callouts', [])
            )
            
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse JSON response: {e}\nResponse: {response}")
            raise HTTPException(status_code=500, detail="Failed to parse AI response")
            
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error in compress_prd: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()