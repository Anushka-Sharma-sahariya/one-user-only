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
    solution: str
    change: str
    metrics: str
    outOfScope: str


class DimensionScores(BaseModel):
    problem_clarity: float
    persona_precision: float
    solution_discipline: float
    metric_integrity: float
    scope_awareness: float
    ambition_level: float


class CompressResponse(BaseModel):
    status: str
    maturity_level: Optional[str] = None
    overall_score: Optional[float] = None
    dimension_scores: Optional[DimensionScores] = None
    diagnosis: Optional[List[str]] = None
    discipline_gaps: Optional[List[str]] = None
    prd: Optional[str] = None
    word_count: Optional[int] = None
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
        if not all([request.problem, request.coreUser, request.solution, request.change, request.metrics, request.outOfScope]):
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
            system_message="You are an opinionated product thinking examiner evaluating early PMs. This is NOT a PRD generator. This is a product maturity assessment engine. Evaluate product thinking across: Problem clarity, Persona precision, Solution discipline, Metric integrity, Scope awareness, Ambition level. CONSTRAINTS: Exactly ONE core user. Max THREE measurable metrics. All metrics MUST include numeric baselines AND numeric targets. PRD max 300 words. No vague modifiers ('slightly,' 'intuitive,' 'improve,' 'optimize,' 'seamless,' 'engagement' without definition). SCORING: Default 5-7 for average. Above 8 RARE (highly specific persona, measurable friction, clear causality, baselines+targets, constrained scope, meaningful impact not 3-5%). Below 5 for vague/multiple personas/disconnected solution/vanity metrics/safe ambition. MATURITY LEVELS: Level 1-Idea Thinker (goals not problems), Level 2-Feature Thinker (weak causality), Level 3-Metric-Aware PM (has numbers, weak ambition), Level 4-Outcome-Oriented PM (clear causality, measurable impact), Level 5-Strategic Operator (strong causal chain, bold ambition, tight persona). TONE: Calm, direct. Say 'This is vague' not 'Consider clarifying.' Say 'You are hedging' not 'This could be stronger.' Say 'This metric is safe' not 'You might want to increase.' Say 'This solution overreaches' not 'Consider narrowing scope.' Say 'Define this or remove it.' No emojis. No praise inflation. No motivational language. Enforce discipline, not encouragement. PRD REWRITE: Do NOT invent new strategy. Only clarify and tighten what user proposed. Keep under 300 words. Maintain headings: Problem, Core User, Solution, Expected Change, Success Metrics, Out of Scope. End with 'This is your disciplined version.' Return structured JSON only."
        ).with_model("anthropic", "claude-sonnet-4-5-20250929")
        
        # Create prompt
        prompt = f"""Evaluate this product thinking submission:

Problem: {request.problem}
Core User: {request.coreUser}
Solution: {request.solution}
Expected Change: {request.change}
Success Metrics: {request.metrics}
Out of Scope: {request.outOfScope}

EVALUATION RULES:
First, check structural constraints:
- Exactly ONE core user (reject if multiple)
- Maximum THREE metrics (reject if more)
- All metrics MUST have numeric baselines AND numeric targets (reject if missing)
- No vague modifiers without measurable outcomes

If any structural rule is violated, return:
{{
  "status": "rejected",
  "rejection_reason": "clear, direct explanation"
}}

If accepted, evaluate across 6 dimensions (scale 0-10):
1. Problem clarity: Is the problem measurable? Does it show friction and causality?
2. Persona precision: Is the user highly specific? Or generic?
3. Solution discipline: Does solution directly address problem without overreach?
4. Metric integrity: Baselines + targets present? Meaningful impact (not 3-5%)?
5. Scope awareness: Is scope explicitly constrained? Trade-offs clear?
6. Ambition level: Bold but realistic? Or safe and timid?

SCORING GUIDELINES:
- Default overall score: 5-7 for average submissions
- Above 8: RARE, requires exceptional discipline across all dimensions
- Below 5: Vague problem, multiple personas, disconnected solution, vanity metrics, safe ambition

ASSIGN MATURITY LEVEL:
- Level 1 – Idea Thinker: Describes goals, not problems. Vague users. No real metrics.
- Level 2 – Feature Thinker: Defines a feature but weak causal reasoning and safe metrics.
- Level 3 – Metric-Aware PM: Has numbers but weak ambition or fuzzy persona.
- Level 4 – Outcome-Oriented PM: Clear causality, measurable impact, disciplined scope.
- Level 5 – Strategic Operator: Strong causal chain, bold but realistic ambition, tight persona, clear trade-offs.

Return JSON in this exact format:
{{
  "status": "accepted",
  "maturity_level": "Level 1 | Level 2 | Level 3 | Level 4 | Level 5",
  "overall_score": number (1-10),
  "dimension_scores": {{
    "problem_clarity": number,
    "persona_precision": number,
    "solution_discipline": number,
    "metric_integrity": number,
    "scope_awareness": number,
    "ambition_level": number
  }},
  "diagnosis": [
    "short, sharp statement about strengths",
    "short, sharp statement about weaknesses"
  ],
  "discipline_gaps": [
    "specific weakness 1",
    "specific weakness 2 (if any)"
  ],
  "prd": "Rewritten disciplined PRD under 300 words. Use headings: Problem, Core User, Solution, Expected Change, Success Metrics, Out of Scope. End with: This is your disciplined version.",
  "word_count": number
}}

TONE: Calm, direct. No consultant phrasing. No emojis. No praise inflation. No motivational language."""
        
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
                    rejection_reason=result.get('rejection_reason', 'Submission does not meet structural requirements')
                )
            
            return CompressResponse(
                status='accepted',
                maturity_level=result.get('maturity_level', ''),
                overall_score=result.get('overall_score', 0),
                dimension_scores=DimensionScores(**result.get('dimension_scores', {})),
                diagnosis=result.get('diagnosis', []),
                discipline_gaps=result.get('discipline_gaps', []),
                prd=result.get('prd', ''),
                word_count=result.get('word_count', 0)
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