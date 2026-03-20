"""Cluster detection engine for cognitive service."""

import math
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime


class ClusterEngine:
    """Simple clustering engine for cognitive events."""

    def __init__(self):
        self.min_cluster_size = 3
        self.similarity_threshold = 0.7

    def generate_feature_vector(self, payload: str, kind: str) -> List[float]:
        """Generate a simple feature vector from payload and kind."""
        # Simple hash-based feature vector (use proper embeddings in production)
        combined = f"{kind}:{payload}"
        hash_bytes = hashlib.sha256(combined.encode()).digest()
        
        # Create 64-dimensional vector
        vector = []
        for i in range(64):
            byte_idx = i % len(hash_bytes)
            value = (hash_bytes[byte_idx] / 127.5) - 1.0
            value = value * math.cos(i * 0.1)
            vector.append(value)
        
        # Normalize
        magnitude = math.sqrt(sum(x * x for x in vector))
        if magnitude > 0:
            vector = [x / magnitude for x in vector]
        
        return vector

    def cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(vec1) != len(vec2):
            return 0.0

        dot_product = sum(a * b for a, b in zip(vec1, vec2))
        magnitude1 = math.sqrt(sum(a * a for a in vec1))
        magnitude2 = math.sqrt(sum(b * b for b in vec2))

        if magnitude1 == 0 or magnitude2 == 0:
            return 0.0

        return dot_product / (magnitude1 * magnitude2)

    def euclidean_distance(self, vec1: List[float], vec2: List[float]) -> float:
        """Calculate Euclidean distance between two vectors."""
        if len(vec1) != len(vec2):
            return float('inf')
        return math.sqrt(sum((a - b) ** 2 for a, b in zip(vec1, vec2)))

    def find_nearest_cluster(
        self,
        vector: List[float],
        centroids: List[Tuple[str, List[float]]],
    ) -> Optional[Tuple[str, float]]:
        """Find the nearest cluster for a vector.
        
        Returns (cluster_id, distance) or None if no cluster is close enough.
        """
        if not centroids:
            return None

        best_cluster = None
        best_similarity = -1

        for cluster_id, centroid in centroids:
            similarity = self.cosine_similarity(vector, centroid)
            if similarity > best_similarity:
                best_similarity = similarity
                best_cluster = cluster_id

        if best_similarity >= self.similarity_threshold:
            distance = 1.0 - best_similarity  # Convert similarity to distance
            return (best_cluster, distance)

        return None

    def update_centroid(
        self,
        current_centroid: List[float],
        new_vector: List[float],
        member_count: int,
    ) -> List[float]:
        """Update cluster centroid with a new member."""
        if not current_centroid:
            return new_vector

        # Incremental centroid update
        new_centroid = []
        for i in range(len(current_centroid)):
            old_val = current_centroid[i]
            new_val = new_vector[i] if i < len(new_vector) else 0
            updated = (old_val * member_count + new_val) / (member_count + 1)
            new_centroid.append(updated)

        # Normalize
        magnitude = math.sqrt(sum(x * x for x in new_centroid))
        if magnitude > 0:
            new_centroid = [x / magnitude for x in new_centroid]

        return new_centroid

    def suggest_cluster_name(self, kind: str, payloads: List[str]) -> str:
        """Suggest a name for a cluster based on its members."""
        if not payloads:
            return f"Cluster-{kind}"

        # Find common words
        word_counts: Dict[str, int] = {}
        for payload in payloads:
            words = payload.lower().split()
            for word in words:
                if len(word) > 3:  # Skip short words
                    word_counts[word] = word_counts.get(word, 0) + 1

        if word_counts:
            top_word = max(word_counts, key=word_counts.get)
            return f"{kind}-{top_word}"

        return f"Cluster-{kind}"

    def detect_emerging_patterns(
        self,
        recent_events: List[Dict[str, Any]],
        window_size: int = 10,
    ) -> List[Dict[str, Any]]:
        """Detect emerging patterns in recent events."""
        if len(recent_events) < window_size:
            return []

        patterns = []
        
        # Group by kind
        by_kind: Dict[str, List[Dict]] = {}
        for event in recent_events:
            kind = event.get("kind", "unknown")
            if kind not in by_kind:
                by_kind[kind] = []
            by_kind[kind].append(event)

        # Check for unusual concentrations
        total = len(recent_events)
        for kind, events in by_kind.items():
            ratio = len(events) / total
            if ratio > 0.5 and len(events) >= 3:
                patterns.append({
                    "type": "concentration",
                    "kind": kind,
                    "count": len(events),
                    "ratio": ratio,
                    "description": f"High concentration of '{kind}' events ({ratio:.0%})",
                })

        return patterns


cluster_engine = ClusterEngine()
