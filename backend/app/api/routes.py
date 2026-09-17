from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from ..database import get_db
from ..models import Artifact, Assessment, CaseStatus, Claim, IntakeMessage, MediaSignal, Monitor, ReviewEvent, VerificationCase
from ..schemas.verify import ReviewRequest, VerifyRequest, VerifyResponse
from ..schemas.monitor import MonitorCreate
from ..services.pipeline import verify, verify_normalized
from ..services.url_fetch import UnsafeURL
from ..services.ocr import extract_screenshot
from ..services.forensics import inspect_image
from ..services.whatsapp import parse_text_messages, signature_valid
from ..services.monitoring import run_monitor
import hmac
from ..config import settings
import hashlib

router = APIRouter()
def serialize(case, warnings=None):
    return {"case_id": case.id, "status": case.status.value, "input_type": case.input_type, "source_url": case.source_url, "language": case.language,
      "claims": [{"id": c.id, "text": c.text, "source_span": [c.source_start,c.source_end], "claim_type": c.claim_type, "gate_status": c.gate_status, "components": c.components or {}, "evidence": [{"id":e.id,"source_title":e.source_title,"source_url":e.source_url,"publisher":e.publisher,"quote":e.quote,"relation":e.relation,"rating":e.rating,"retrieved_at":e.retrieved_at.isoformat()} for e in c.evidence_items]} for c in case.claims],
      "assessment": {"verdict":case.assessment.verdict,"confidence":case.assessment.confidence,"rationale":case.assessment.rationale,"reasoning_path":case.assessment.reasoning_path,"rubric_version":case.assessment.rubric_version,"evidence_ids":case.assessment.evidence_ids}, "warnings": warnings or [], "security_flags": case.security_flags or []}

@router.post("/verify", response_model=VerifyResponse)
async def verify_route(payload: VerifyRequest, db: Session = Depends(get_db)):
    try: case, warnings = await verify(db, payload.text, str(payload.url) if payload.url else None)
    except (UnsafeURL, ValueError) as exc: raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        if payload.url: raise HTTPException(502, "Article could not be fetched safely") from exc
        raise
    return serialize(case, warnings)

@router.get("/cases/{case_id}", response_model=VerifyResponse)
def get_case(case_id: str, db: Session = Depends(get_db)):
    stmt = select(VerificationCase).where(VerificationCase.id==case_id).options(selectinload(VerificationCase.claims).selectinload(Claim.evidence_items), selectinload(VerificationCase.assessment))
    case = db.scalar(stmt)
    if not case: raise HTTPException(404, "Case not found")
    return serialize(case)

@router.post("/cases/{case_id}/review")
def review(case_id: str, payload: ReviewRequest, db: Session = Depends(get_db)):
    case = db.get(VerificationCase, case_id)
    if not case: raise HTTPException(404, "Case not found")
    if payload.verdict: case.assessment.verdict = payload.verdict
    case.status = CaseStatus.pending_review if payload.decision == "needs_more_evidence" else CaseStatus.reviewed
    db.add(ReviewEvent(case=case, actor=payload.actor, decision=payload.decision, reason=payload.reason)); db.commit()
    return {"case_id": case.id, "status": case.status.value, "verdict": case.assessment.verdict}


@router.post("/verify/screenshot", response_model=VerifyResponse)
async def verify_screenshot(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, "Screenshot exceeds upload limit")
    try: result = extract_screenshot(data, file.content_type or "")
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc: raise HTTPException(503, str(exc)) from exc
    case,warnings = await verify_normalized(db,result.text,file.filename or "screenshot", "screenshot")
    db.add(Artifact(case=case,kind="screenshot",filename=file.filename or "screenshot",mime_type=file.content_type or "application/octet-stream",sha256=hashlib.sha256(data).hexdigest(),byte_size=len(data),metadata_json={"width":result.width,"height":result.height,"ocr_engine":result.engine},extracted_text=result.text,extraction_confidence=result.confidence))
    for signal in inspect_image(data): db.add(MediaSignal(case=case, **signal.__dict__))
    db.commit()
    warnings.insert(0, f"OCR confidence: {result.confidence}. A reviewer should correct extraction errors before relying on the assessment.")
    return serialize(case,warnings)


@router.post("/inspect/image")
async def inspect_media_image(file: UploadFile = File(...), db: Session = Depends(get_db)):
    data=await file.read(settings.max_upload_mb*1024*1024+1)
    if len(data)>settings.max_upload_mb*1024*1024: raise HTTPException(413,"Image exceeds upload limit")
    if (file.content_type or "") not in {"image/png","image/jpeg","image/webp"}: raise HTTPException(400,"Only PNG, JPEG and WebP are accepted")
    case=VerificationCase(input_type="image",original_input=file.filename or "image",normalized_text="Media inspection only",status=CaseStatus.pending_review)
    db.add(case); db.flush()
    case.assessment=Assessment(verdict="unverifiable",confidence="Low",rationale="Media signals do not establish semantic truth. Verify any associated caption or claim separately.",reasoning_path=["Inspected local metadata and generated a perceptual hash.","Kept provenance/authenticity signals separate from claim assessment.","Queued for human review."],evidence_ids=[],rubric_version="1.0.0")
    db.add(Artifact(case=case,kind="image",filename=file.filename or "image",mime_type=file.content_type or "",sha256=hashlib.sha256(data).hexdigest(),byte_size=len(data),metadata_json={}))
    signals=inspect_image(data)
    for x in signals: db.add(MediaSignal(case=case,**x.__dict__))
    db.commit()
    return {"case_id":case.id,"status":case.status.value,"assessment":{"verdict":case.assessment.verdict,"confidence":case.assessment.confidence,"rationale":case.assessment.rationale},"signals":[x.__dict__ for x in signals],"warnings":["No automated signal is an authenticity verdict. Human review is required."]}


@router.get("/intake/whatsapp/webhook")
def whatsapp_verify(hub_mode: str | None = None, hub_verify_token: str | None = None, hub_challenge: str | None = None):
    if not settings.whatsapp_verify_token: raise HTTPException(503,"WhatsApp intake is not configured")
    if hub_mode=="subscribe" and hmac.compare_digest(hub_verify_token or "",settings.whatsapp_verify_token): return Response(hub_challenge or "",media_type="text/plain")
    raise HTTPException(403,"Webhook verification failed")

@router.post("/intake/whatsapp/webhook")
async def whatsapp_intake(request: Request, db: Session = Depends(get_db)):
    body=await request.body()
    if not signature_valid(body,request.headers.get("x-hub-signature-256"),settings.whatsapp_app_secret): raise HTTPException(401,"Invalid webhook signature")
    try: payload=__import__("json").loads(body)
    except ValueError as exc: raise HTTPException(400,"Invalid JSON") from exc
    accepted=[]
    for msg in parse_text_messages(payload):
        existing=db.scalar(select(IntakeMessage).where(IntakeMessage.provider_message_id==msg.message_id))
        if existing: continue
        case,warnings=await verify_normalized(db,msg.text,"WhatsApp text", "whatsapp")
        db.add(IntakeMessage(provider_message_id=msg.message_id,case=case,channel="whatsapp",sender_hash=hashlib.sha256(msg.sender.encode()).hexdigest(),message_type="text",status="case_created")); db.commit()
        accepted.append({"message_id":msg.message_id,"case_id":case.id})
    return {"accepted":accepted,"count":len(accepted),"outbound_status":"not_sent"}


@router.post("/monitors")
def create_monitor(payload: MonitorCreate, db: Session = Depends(get_db)):
    monitor=Monitor(query=payload.query,language=payload.language); db.add(monitor); db.commit(); db.refresh(monitor)
    return {"id":monitor.id,"query":monitor.query,"language":monitor.language,"status":monitor.status}

@router.get("/monitors")
def list_monitors(db: Session = Depends(get_db)):
    rows=db.scalars(select(Monitor).order_by(Monitor.created_at.desc())).all()
    return [{"id":x.id,"query":x.query,"language":x.language,"status":x.status,"last_checked_at":x.last_checked_at,"last_result_count":x.last_result_count} for x in rows]

@router.post("/monitors/{monitor_id}/run")
async def execute_monitor(monitor_id: str, db: Session = Depends(get_db)):
    monitor=db.get(Monitor,monitor_id)
    if not monitor: raise HTTPException(404,"Monitor not found")
    if monitor.status!="active": raise HTTPException(409,"Monitor is paused")
    return await run_monitor(db,monitor,settings.google_factcheck_api_key)

@router.post("/monitors/{monitor_id}/pause")
def pause_monitor(monitor_id: str, db: Session = Depends(get_db)):
    monitor=db.get(Monitor,monitor_id)
    if not monitor: raise HTTPException(404,"Monitor not found")
    monitor.status="paused"; db.commit(); return {"id":monitor.id,"status":monitor.status}
