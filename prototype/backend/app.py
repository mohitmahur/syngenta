"""
FastAPI Application
====================
REST API serving the full AI-Powered Agricultural Marketing prototype.
Exposes endpoints for segmentation, content generation, receptivity
prediction, and analytics — all powered by REAL data.
"""

import os
import sys
from datetime import date
from typing import Optional

from pydantic import BaseModel
from typing import Optional
from datetime import datetime
import json

from fastapi import FastAPI, Query, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

# Ensure the prototype root is on the path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.data_loader import get_data_store
from backend.segmentation import SegmentationEngine
from backend.content_engine import ContentEngine
from backend.receptivity_model import ReceptivityModel
from backend.analytics import AnalyticsEngine

# ──────────────────────────────────────────────────────
# App init
# ──────────────────────────────────────────────────────
app = FastAPI(
    title="KrishiConnect AI — Agricultural Marketing Engine",
    description="AI-powered micro-targeted agricultural marketing at scale",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# ──────────────────────────────────────────────────────
# Lazy-initialized engines
# ──────────────────────────────────────────────────────
_segmentation = None
_content = None
_receptivity = None
_analytics = None


from pydantic import BaseModel
from typing import List

# In-memory queue for demo purposes
flagged_campaigns_queue = []


class ReviewDecision(BaseModel):
    campaign_id: str
    decision: str  # "approve" or "reject"
    notes: str = ""


@app.post("/api/campaign/queue")
async def queue_flagged_campaign(campaign_data: dict):
    """Internal endpoint: Content engine pushes guardrail-failed content here."""
    import uuid

    campaign_data["campaign_id"] = str(uuid.uuid4())
    campaign_data["status"] = "pending_review"
    flagged_campaigns_queue.append(campaign_data)
    return {"status": "queued", "campaign_id": campaign_data["campaign_id"]}


@app.get("/api/admin/review-queue")
async def get_review_queue():
    """Frontend endpoint: Fetch campaigns requiring human review."""
    return [c for c in flagged_campaigns_queue if c["status"] == "pending_review"]


@app.post("/api/admin/review-queue/resolve")
async def resolve_campaign(decision: ReviewDecision):
    """Frontend endpoint: Admin approves or rejects flagged content."""
    for campaign in flagged_campaigns_queue:
        if campaign["campaign_id"] == decision.campaign_id:
            campaign["status"] = decision.decision
            campaign["admin_notes"] = decision.notes
            return {"status": "success", "message": f"Campaign {decision.decision}d"}
    raise HTTPException(status_code=404, detail="Campaign not found in queue")


def get_segmentation():
    global _segmentation
    if _segmentation is None:
        _segmentation = SegmentationEngine()
    return _segmentation


def get_content():
    global _content
    if _content is None:
        _content = ContentEngine()
    return _content


def get_receptivity():
    global _receptivity
    if _receptivity is None:
        _receptivity = ReceptivityModel()
    return _receptivity


def get_analytics():
    global _analytics
    if _analytics is None:
        _analytics = AnalyticsEngine()
    return _analytics


# ──────────────────────────────────────────────────────
# Frontend route
# ──────────────────────────────────────────────────────
@app.get("/")
async def serve_frontend():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))


# ──────────────────────────────────────────────────────
# API: Data Overview
# ──────────────────────────────────────────────────────
@app.get("/api/data/overview")
async def data_overview():
    """Get an overview of all loaded datasets."""
    store = get_data_store()
    return {
        "growers": len(store.growers),
        "retailers": len(store.retailers),
        "reps": len(store.reps_territory),
        "pos_transactions": len(store.retailer_pos),
        "inventory_records": len(store.retailer_inventory),
        "visit_logs": len(store.retailer_visits),
        "whatsapp_messages": len(store.whatsapp_log),
        "digital_funnel_weeks": len(store.digital_funnel),
        "states": sorted(store.growers["state"].unique().tolist()),
        "crops": sorted(store.growers["crop"].unique().tolist()),
        "languages": sorted(store.growers["language"].unique().tolist()),
        "products": sorted(store.retailer_pos["sku_name"].unique().tolist()),
    }


# ──────────────────────────────────────────────────────
# API: Segmentation
# ──────────────────────────────────────────────────────
@app.get("/api/segments/summary")
async def segment_summary():
    """Get high-level segmentation summary."""
    engine = get_segmentation()
    # Use a Rabi season date for meaningful stage computation
    ref = date(2026, 2, 1)
    return engine.get_segment_summary(ref)


@app.get("/api/segments/list")
async def segment_list(
    crop: Optional[str] = None,
    state: Optional[str] = None,
    limit: int = Query(default=50, le=500),
):
    """List micro-segments with optional filtering."""
    engine = get_segmentation()
    ref = date(2026, 2, 1)
    segments = engine.build_segments(ref)

    if crop:
        segments = [s for s in segments if s["crop"] == crop]
    if state:
        segments = [s for s in segments if s["state"] == state]

    # Sort by grower count descending
    segments.sort(key=lambda s: s["grower_count"], reverse=True)

    # Remove grower_ids from list response (too large)
    for s in segments[:limit]:
        s["grower_ids"] = s["grower_ids"][:5]  # Keep just first 5 as sample

    return {"total": len(segments), "segments": segments[:limit]}


# ──────────────────────────────────────────────────────
# API: Grower Context
# ──────────────────────────────────────────────────────
@app.get("/api/grower/{grower_id}")
async def grower_context(grower_id: str):
    """Get full context profile for a grower."""
    engine = get_segmentation()
    ref = date(2026, 2, 1)
    ctx = engine.get_grower_context(grower_id, ref)
    if "error" in ctx:
        raise HTTPException(status_code=404, detail=ctx["error"])
    return ctx


@app.get("/api/grower/{grower_id}/receptivity")
async def grower_receptivity(grower_id: str):
    """Predict engagement receptivity for a grower."""
    engine = get_segmentation()
    model = get_receptivity()
    ref = date(2026, 2, 1)
    ctx = engine.get_grower_context(grower_id, ref)
    if "error" in ctx:
        raise HTTPException(status_code=404, detail=ctx["error"])
    prediction = model.predict(ctx)
    return {"grower_id": grower_id, **prediction}


# ──────────────────────────────────────────────────────
# API: Content Generation
# ──────────────────────────────────────────────────────
@app.get("/api/generate/{grower_id}")
async def generate_content(
    grower_id: str,
    format: str = Query(default="auto", pattern="^(auto|whatsapp|sms|voice_script)$"),
):
    """Generate personalized marketing content and delivery plan for a grower."""
    seg = get_segmentation()
    content_engine = get_content()
    receptivity_model = get_receptivity()
    ref = date(2026, 2, 1)

    ctx = seg.get_grower_context(grower_id, ref)
    if "error" in ctx:
        raise HTTPException(status_code=404, detail=ctx["error"])

    # 1. Fetch dynamic weather triggers
    from backend.weather_triggers import WeatherTriggerEngine

    weather_engine = WeatherTriggerEngine()
    triggers = weather_engine.evaluate_triggers(
        crop=ctx.get("crop", ""),
        stage=ctx.get("current_stage", ""),
        district=ctx.get("district", ""),
        ref_date=ref,
    )

    # 2. Predict receptivity
    receptivity = receptivity_model.predict(ctx)

    # 3. Generate content with visual/video and guardrails
    content_result = content_engine.generate(ctx, format, weather_triggers=triggers)

    # 4. Build orchestrator delivery plan
    from backend.orchestrator import CampaignOrchestrator

    orch = CampaignOrchestrator()
    plan = orch.build_delivery_plan(ctx, receptivity)

    # Combine response
    result = {
        "grower_id": grower_id,
        "language": content_result["language"],
        "channel": plan["primary_channel"],
        "product_recommended": content_result["product_recommended"],
        "generation_method": content_result["generation_method"],
        "weather_triggers": content_result.get("weather_triggers", []),
        "receptivity": receptivity,
        "delivery_plan": plan,
        "content": content_result.get("content", {}),
        "guardrail_check": content_result.get("guardrail_check", {}),
    }
    return result


# ──────────────────────────────────────────────────────
# API: Analytics
# ──────────────────────────────────────────────────────
@app.get("/api/analytics/whatsapp")
async def analytics_whatsapp():
    """WhatsApp campaign funnel metrics."""
    return get_analytics().get_whatsapp_funnel_metrics()


@app.get("/api/analytics/digital-funnel")
async def analytics_digital_funnel():
    """Digital campaign funnel metrics."""
    return get_analytics().get_digital_funnel_metrics()


@app.get("/api/analytics/conversion")
async def analytics_conversion():
    """Campaign-to-action conversion attribution."""
    return get_analytics().get_conversion_attribution()


@app.get("/api/analytics/pos-trends")
async def analytics_pos_trends(
    sku: Optional[str] = None,
    state: Optional[str] = None,
):
    """POS sales trends."""
    return get_analytics().get_pos_trends(sku, state)


@app.get("/api/analytics/inventory")
async def analytics_inventory():
    """Inventory health metrics."""
    return get_analytics().get_inventory_health()


@app.get("/api/analytics/field-activity")
async def analytics_field_activity():
    """Field rep activity summary."""
    return get_analytics().get_field_activity_summary()


# ──────────────────────────────────────────────────────
# API: Receptivity Model Info
# ──────────────────────────────────────────────────────
@app.get("/api/model/info")
async def model_info():
    """Get receptivity model training metrics."""
    model = get_receptivity()
    if not model.is_trained:
        model.train()
    return model.training_metrics

# ── 1. Define the Schema ──
class RLHFFeedback(BaseModel):
    grower_id: str
    campaign_id: str
    status: str  # "thumbs_up" or "thumbs_down"
    failure_reason: Optional[str] = None  # e.g., "Hallucinated Yield", "Tone Mismatch", "Safety Violation"
    comments: Optional[str] = ""
    payload_snapshot: dict  # The actual generated text that is being reviewed

# ── 2. Create the Endpoint ──
@app.post("/api/rlhf/feedback")
async def log_rlhf_feedback(feedback: RLHFFeedback):
    """
    Logs human-in-the-loop feedback for continuous LLM prompt tuning.
    Saves feedback directly to a local JSON Lines file.
    """
    log_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "grower_id": feedback.grower_id,
        "campaign_id": feedback.campaign_id,
        "status": feedback.status,
        "failure_reason": feedback.failure_reason,
        "comments": feedback.comments,
        "content_snapshot": feedback.payload_snapshot
    }
    
    # Save to a local JSONL file for the hackathon demo
    log_file = "rlhf_feedback_logs.jsonl"
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
        print(f"[RLHF] Logged feedback for campaign {feedback.campaign_id}: {feedback.status}")
        return {"status": "success", "message": "Feedback logged successfully."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


# ──────────────────────────────────────────────────────
# Run
# ──────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
