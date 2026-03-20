from datetime import datetime
import uuid

from sqlalchemy import Column, DateTime, Float, Integer, String, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func

from .db import Base


class CognitiveTick(Base):
    """Represents a cognitive tick event for processing."""
    __tablename__ = "cognitive_ticks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    kind = Column(String(64), nullable=False)  # e.g. periodic, anomaly_scan, chat_message
    payload = Column(Text, nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    processed = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AnomalyRecord(Base):
    """Detected anomalies in the system."""
    __tablename__ = "anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    tick_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    severity = Column(String(32), nullable=False)  # low, medium, high, critical
    score = Column(Float, nullable=True)  # Anomaly score 0-1
    description = Column(Text, nullable=False)
    category = Column(String(64), nullable=True)  # behavior, security, performance
    resolved = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class CognitiveCluster(Base):
    """Clusters of related cognitive events."""
    __tablename__ = "cognitive_clusters"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    name = Column(String(128), nullable=True)
    centroid = Column(ARRAY(Float), nullable=True)  # Cluster centroid vector
    member_count = Column(Integer, default=0)
    category = Column(String(64), nullable=True)
    extra_metadata = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class ClusterMembership(Base):
    """Maps ticks to clusters."""
    __tablename__ = "cluster_memberships"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tick_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    cluster_id = Column(UUID(as_uuid=True), index=True, nullable=False)
    distance = Column(Float, nullable=True)  # Distance from centroid
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class WorkflowTrigger(Base):
    """Triggers that connect cognitive events to workflows."""
    __tablename__ = "workflow_triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), index=True, nullable=True)
    name = Column(String(128), nullable=False)
    condition_type = Column(String(64), nullable=False)  # anomaly, cluster, pattern
    condition_config = Column(JSON, nullable=False)  # Trigger conditions
    workflow_id = Column(UUID(as_uuid=True), nullable=True)  # Target workflow
    action_config = Column(JSON, nullable=True)  # Action to take
    enabled = Column(Boolean, default=True)
    last_triggered = Column(DateTime(timezone=True), nullable=True)
    trigger_count = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
