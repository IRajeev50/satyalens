from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from ..models import Monitor
from .retrieval import FactCheckRetriever

async def run_monitor(db: Session, monitor: Monitor, key: str | None) -> dict:
    result=await FactCheckRetriever(key).search(monitor.query,monitor.language)
    monitor.last_checked_at=datetime.now(timezone.utc); monitor.last_result_count=len(result.items); db.commit()
    return {"monitor_id":monitor.id,"result_count":len(result.items),"items":result.items,"warning":result.warning,"checked_at":monitor.last_checked_at.isoformat()}
