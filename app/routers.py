from typing import Any, Dict, List, Optional
from datetime import datetime

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from .db import get_session
from .models import (
    AnomalyRecord, CognitiveTick, CognitiveCluster, 
    ClusterMembership, WorkflowTrigger
)
from .anomaly_detector import anomaly_detector
from .cluster_engine import cluster_engine


router = APIRouter(prefix="/cognitive", tags=["cognitive"])


# Request/Response Models
class TickCreate(BaseModel):
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    kind: str
    payload: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    auto_analyze: bool = True


class TickResponse(BaseModel):
    id: str
    agent_id: Optional[str]
    user_id: Optional[str]
    kind: str
    payload: Optional[str]
    processed: bool = False

    class Config:
        from_attributes = True


class AnomalyCreate(BaseModel):
    agent_id: Optional[str] = None
    user_id: Optional[str] = None
    tick_id: Optional[str] = None
    severity: str
    score: Optional[float] = None
    description: str
    category: Optional[str] = None


class AnomalyResponse(BaseModel):
    id: str
    agent_id: Optional[str]
    user_id: Optional[str]
    severity: str
    score: Optional[float]
    description: str
    category: Optional[str]
    resolved: bool = False

    class Config:
        from_attributes = True


class ClusterResponse(BaseModel):
    id: str
    user_id: Optional[str]
    name: Optional[str]
    member_count: int
    category: Optional[str]

    class Config:
        from_attributes = True


class TriggerCreate(BaseModel):
    user_id: Optional[str] = None
    name: str
    condition_type: str  # anomaly, cluster, pattern
    condition_config: Dict[str, Any]
    workflow_id: Optional[str] = None
    action_config: Optional[Dict[str, Any]] = None


class TriggerResponse(BaseModel):
    id: str
    name: str
    condition_type: str
    enabled: bool
    trigger_count: int

    class Config:
        from_attributes = True


class InsightResponse(BaseModel):
    kind: str
    payload: str
    score: Optional[float] = None
    created_at: Optional[str] = None


# Tick Endpoints
@router.post("/ticks", response_model=TickResponse)
async def create_tick(
    payload: TickCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Ingest a cognitive tick and optionally analyze for anomalies."""
    user_id = request.headers.get("x-user-id") or payload.user_id

    tick = CognitiveTick(
        agent_id=payload.agent_id,
        user_id=user_id,
        kind=payload.kind,
        payload=payload.payload,
        extra_metadata=payload.metadata,
    )
    session.add(tick)
    await session.commit()
    await session.refresh(tick)

    # Auto-analyze if requested
    if payload.auto_analyze and payload.payload:
        # Check for pattern anomalies
        score, severity, description = anomaly_detector.detect_pattern_anomaly(
            payload.payload, []
        )
        
        if score > 0.3:  # Only record significant anomalies
            anomaly = AnomalyRecord(
                agent_id=payload.agent_id,
                user_id=user_id,
                tick_id=tick.id,
                severity=severity,
                score=score,
                description=description,
                category="pattern",
            )
            session.add(anomaly)
            
            # Check triggers
            await _check_triggers(session, user_id, "anomaly", {
                "severity": severity,
                "score": score,
                "tick_id": str(tick.id),
            })

        # Try to assign to cluster
        vector = cluster_engine.generate_feature_vector(payload.payload, payload.kind)
        
        # Get existing clusters
        stmt = select(CognitiveCluster)
        if user_id:
            stmt = stmt.where(CognitiveCluster.user_id == user_id)
        result = await session.execute(stmt)
        clusters = result.scalars().all()
        
        centroids = [(str(c.id), c.centroid) for c in clusters if c.centroid]
        
        cluster_match = cluster_engine.find_nearest_cluster(vector, centroids)
        if cluster_match:
            cluster_id, distance = cluster_match
            # Add to existing cluster
            membership = ClusterMembership(
                tick_id=tick.id,
                cluster_id=cluster_id,
                distance=distance,
            )
            session.add(membership)
            
            # Update cluster centroid
            for c in clusters:
                if str(c.id) == cluster_id:
                    c.centroid = cluster_engine.update_centroid(
                        c.centroid, vector, c.member_count
                    )
                    c.member_count += 1
                    break

        tick.processed = True
        await session.commit()

    return TickResponse(
        id=str(tick.id),
        agent_id=str(tick.agent_id) if tick.agent_id else None,
        user_id=str(tick.user_id) if tick.user_id else None,
        kind=tick.kind,
        payload=tick.payload,
        processed=tick.processed,
    )


@router.get("/ticks", response_model=List[TickResponse])
async def list_ticks(
    user_id: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List cognitive ticks with optional filtering."""
    stmt = select(CognitiveTick).order_by(CognitiveTick.created_at.desc())
    if user_id:
        stmt = stmt.where(CognitiveTick.user_id == user_id)
    if kind:
        stmt = stmt.where(CognitiveTick.kind == kind)
    
    result = await session.execute(stmt.limit(limit))
    ticks = result.scalars().all()
    
    return [
        TickResponse(
            id=str(t.id),
            agent_id=str(t.agent_id) if t.agent_id else None,
            user_id=str(t.user_id) if t.user_id else None,
            kind=t.kind,
            payload=t.payload,
            processed=t.processed,
        )
        for t in ticks
    ]


# Anomaly Endpoints
@router.post("/anomalies", response_model=AnomalyResponse)
async def create_anomaly(
    payload: AnomalyCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Record an anomaly."""
    user_id = request.headers.get("x-user-id") or payload.user_id

    anomaly = AnomalyRecord(
        agent_id=payload.agent_id,
        user_id=user_id,
        tick_id=payload.tick_id,
        severity=payload.severity,
        score=payload.score,
        description=payload.description,
        category=payload.category,
    )
    session.add(anomaly)
    await session.commit()
    await session.refresh(anomaly)

    return AnomalyResponse(
        id=str(anomaly.id),
        agent_id=str(anomaly.agent_id) if anomaly.agent_id else None,
        user_id=str(anomaly.user_id) if anomaly.user_id else None,
        severity=anomaly.severity,
        score=anomaly.score,
        description=anomaly.description,
        category=anomaly.category,
        resolved=anomaly.resolved,
    )


@router.get("/anomalies", response_model=List[AnomalyResponse])
async def list_anomalies(
    user_id: Optional[str] = None,
    severity: Optional[str] = None,
    resolved: Optional[bool] = None,
    limit: int = 50,
    session: AsyncSession = Depends(get_session),
):
    """List anomalies with optional filtering."""
    stmt = select(AnomalyRecord).order_by(AnomalyRecord.created_at.desc())
    if user_id:
        stmt = stmt.where(AnomalyRecord.user_id == user_id)
    if severity:
        stmt = stmt.where(AnomalyRecord.severity == severity)
    if resolved is not None:
        stmt = stmt.where(AnomalyRecord.resolved == resolved)

    result = await session.execute(stmt.limit(limit))
    anomalies = result.scalars().all()

    return [
        AnomalyResponse(
            id=str(a.id),
            agent_id=str(a.agent_id) if a.agent_id else None,
            user_id=str(a.user_id) if a.user_id else None,
            severity=a.severity,
            score=a.score,
            description=a.description,
            category=a.category,
            resolved=a.resolved,
        )
        for a in anomalies
    ]


@router.patch("/anomalies/{anomaly_id}/resolve")
async def resolve_anomaly(
    anomaly_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Mark an anomaly as resolved."""
    stmt = select(AnomalyRecord).where(AnomalyRecord.id == anomaly_id)
    result = await session.execute(stmt)
    anomaly = result.scalar_one_or_none()
    
    if not anomaly:
        return {"status": "not_found"}
    
    anomaly.resolved = True
    await session.commit()
    return {"status": "resolved", "id": anomaly_id}


# Cluster Endpoints
@router.get("/clusters", response_model=List[ClusterResponse])
async def list_clusters(
    user_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List cognitive clusters."""
    stmt = select(CognitiveCluster).order_by(CognitiveCluster.member_count.desc())
    if user_id:
        stmt = stmt.where(CognitiveCluster.user_id == user_id)

    result = await session.execute(stmt)
    clusters = result.scalars().all()

    return [
        ClusterResponse(
            id=str(c.id),
            user_id=str(c.user_id) if c.user_id else None,
            name=c.name,
            member_count=c.member_count,
            category=c.category,
        )
        for c in clusters
    ]


@router.post("/clusters")
async def create_cluster(
    name: str,
    category: Optional[str] = None,
    user_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """Create a new cluster."""
    cluster = CognitiveCluster(
        user_id=user_id,
        name=name,
        category=category,
        member_count=0,
    )
    session.add(cluster)
    await session.commit()
    await session.refresh(cluster)

    return {"id": str(cluster.id), "name": cluster.name}


# Trigger Endpoints
@router.post("/triggers", response_model=TriggerResponse)
async def create_trigger(
    payload: TriggerCreate,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Create a workflow trigger."""
    user_id = request.headers.get("x-user-id") or payload.user_id

    trigger = WorkflowTrigger(
        user_id=user_id,
        name=payload.name,
        condition_type=payload.condition_type,
        condition_config=payload.condition_config,
        workflow_id=payload.workflow_id,
        action_config=payload.action_config,
    )
    session.add(trigger)
    await session.commit()
    await session.refresh(trigger)

    return TriggerResponse(
        id=str(trigger.id),
        name=trigger.name,
        condition_type=trigger.condition_type,
        enabled=trigger.enabled,
        trigger_count=trigger.trigger_count,
    )


@router.get("/triggers", response_model=List[TriggerResponse])
async def list_triggers(
    user_id: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """List workflow triggers."""
    stmt = select(WorkflowTrigger)
    if user_id:
        stmt = stmt.where(WorkflowTrigger.user_id == user_id)

    result = await session.execute(stmt)
    triggers = result.scalars().all()

    return [
        TriggerResponse(
            id=str(t.id),
            name=t.name,
            condition_type=t.condition_type,
            enabled=t.enabled,
            trigger_count=t.trigger_count,
        )
        for t in triggers
    ]


# Insights Endpoint (for LLM context injection)
@router.get("/insights", response_model=List[InsightResponse])
async def get_insights(
    user_id: Optional[str] = None,
    limit: int = 5,
    session: AsyncSession = Depends(get_session),
):
    """Get recent cognitive insights for context injection."""
    insights = []

    # Get recent anomalies
    stmt = select(AnomalyRecord).where(AnomalyRecord.resolved == False)
    if user_id:
        stmt = stmt.where(AnomalyRecord.user_id == user_id)
    stmt = stmt.order_by(AnomalyRecord.created_at.desc()).limit(limit)

    result = await session.execute(stmt)
    anomalies = result.scalars().all()

    for a in anomalies:
        insights.append(InsightResponse(
            kind=f"anomaly:{a.severity}",
            payload=a.description,
            score=a.score,
            created_at=str(a.created_at) if a.created_at else None,
        ))

    return insights


# Helper function for trigger checking
async def _check_triggers(
    session: AsyncSession,
    user_id: Optional[str],
    event_type: str,
    event_data: Dict[str, Any],
):
    """Check and fire matching triggers."""
    stmt = select(WorkflowTrigger).where(
        WorkflowTrigger.enabled == True,
        WorkflowTrigger.condition_type == event_type,
    )
    if user_id:
        stmt = stmt.where(WorkflowTrigger.user_id == user_id)

    result = await session.execute(stmt)
    triggers = result.scalars().all()

    for trigger in triggers:
        config = trigger.condition_config or {}
        
        # Simple condition matching
        should_fire = True
        if event_type == "anomaly":
            min_severity = config.get("min_severity", "low")
            severity_order = ["low", "medium", "high", "critical"]
            event_severity = event_data.get("severity", "low")
            if severity_order.index(event_severity) < severity_order.index(min_severity):
                should_fire = False

        if should_fire:
            trigger.trigger_count += 1
            trigger.last_triggered = datetime.utcnow()
            
            # Fire workflow if configured
            if trigger.workflow_id:
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        await client.post(
                            f"http://workflow_service:8000/workflow/workflows/{trigger.workflow_id}/run",
                            json={"trigger_data": event_data},
                        )
                except httpx.RequestError:
                    pass  # Best effort

            # Phase 3.4: Fire agent session if action_config specifies agent_id
            action_cfg = trigger.action_config or {}
            target_agent_id = action_cfg.get("agent_id")
            if target_agent_id:
                goal_tpl = action_cfg.get("goal", "Investigate anomaly: {description}")
                try:
                    goal = goal_tpl.format(**event_data)
                except (KeyError, IndexError):
                    goal = goal_tpl
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        await client.post(
                            f"http://agent_engine_service:8000/agent-engine/{target_agent_id}/sessions",
                            json={
                                "goal": goal,
                                "context": {
                                    "trigger_source": "cognitive_anomaly",
                                    "trigger_id": str(trigger.id),
                                    "event_type": event_type,
                                    "event_data": event_data,
                                },
                            },
                            headers={"x-user-id": str(user_id or "")},
                        )
                except httpx.RequestError:
                    pass  # Best effort

    await session.commit()


@router.get("/health")
async def health():
    return {"service": "cognitive", "status": "ok"}
