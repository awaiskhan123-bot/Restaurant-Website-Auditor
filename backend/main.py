from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, HttpUrl
import datetime

from scanner import scan_website
from facts import extract_facts
from ai_auditor import analyze_website
from report import save_audit_report


app = FastAPI(
    title="AI Food Website Intelligence Auditor",
    description=(
        "Real-time AI-powered intelligence extraction "
        "system for Food & Beverage websites"
    ),
    version="3.0.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AuditRequest(BaseModel):
    url: HttpUrl


@app.get("/")
def root():
    return {
        "message": "AI Food Website Intelligence Auditor API",
        "version": "3.0.0",
        "mode": "real-time",
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok", "timestamp": datetime.datetime.now().isoformat()}


@app.post("/audit")
def audit_website(request: AuditRequest):

    url = str(request.url)
    audit_start = datetime.datetime.now()

    # ---------------------------------------------------------
    # 1. SCAN WEBSITE
    # ---------------------------------------------------------

    scan_result = scan_website(url)

    if "error" in scan_result and not scan_result.get("scan_successful"):
        raise HTTPException(
            status_code=400,
            detail=scan_result["error"],
        )

    # ---------------------------------------------------------
    # 2. EXTRACT FACTS
    # ---------------------------------------------------------

    facts = extract_facts(scan_result)

    if not facts.get("scan_successful"):
        raise HTTPException(
            status_code=400,
            detail=facts.get("error", "Website scan failed."),
        )

    # ---------------------------------------------------------
    # 3. AI ANALYSIS
    # ---------------------------------------------------------

    try:
        audit = analyze_website(facts)

        ai_analysis = {
            "score": audit.score,
            "summary": getattr(audit, "summary", ""),
            "problems": audit.problems,
            "missing_features": audit.missing_features,
            "recommendations": audit.recommendations,
            "priority": audit.priority,
            "strengths": getattr(audit, "strengths", []) or [],
            "ai_status": "AI analysis completed",
        }

    except Exception as exc:

        print("AI analysis failed:", exc)

        # Automatic fallback
        ai_analysis = {
            "score": 0,
            "summary": "AI analysis was unavailable. Showing extracted data only.",
            "problems": [],
            "missing_features": [],
            "recommendations": [],
            "priority": "Unknown",
            "strengths": [],
            "ai_status": "Automatic analysis used (AI unavailable)",
        }

    # ---------------------------------------------------------
    # 4. SAVE REPORT
    # ---------------------------------------------------------

    try:
        report_file = save_audit_report(facts, ai_analysis)
    except Exception:
        report_file = None

    # ---------------------------------------------------------
    # 5. RETURN RESULT
    # ---------------------------------------------------------

    audit_end = datetime.datetime.now()
    scan_duration_ms = round(
        (audit_end - audit_start).total_seconds() * 1000
    )

    return {
        "success": True,
        "website": url,
        "audit_timestamp": audit_end.isoformat(),
        "scan_duration_ms": scan_duration_ms,
        "automatic_facts": facts,
        "ai_analysis": ai_analysis,
        "report_file": report_file,
    }