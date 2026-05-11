"""
Shortest-path navigation using Dijkstra's algorithm.
Finds the nearest vacant parking slot from the user's current position
on the parking lot walkway graph.
"""

import heapq
from typing import Dict, List, Optional, Tuple, Set


class ParkingGraph:
    """
    Graph representation of the parking lot walkway.

    Nodes can be:
      - Parking slots (e.g., "S1", "S2", ...)
      - Waypoints / turning points (e.g., "W1", "W2", ...)
      - Entrance gates (e.g., "E1", "E2", ...)

    Edges have weights representing distance (meters or grid cells).
    """

    def __init__(self, graph_data: Dict):
        """
        Args:
            graph_data: Dict with:
                - 'nodes': list of {'id': str, 'type': 'slot'|'waypoint'|'entrance',
                                     'x': float, 'y': float}
                - 'edges': list of {'from': str, 'to': str, 'weight': float}
        """
        self.nodes = {}
        self.adjacency = {}

        for node in graph_data["nodes"]:
            nid = node["id"]
            self.nodes[nid] = node
            self.adjacency[nid] = []

        for edge in graph_data["edges"]:
            src, dst, w = edge["from"], edge["to"], edge["weight"]
            self.adjacency[src].append((dst, w))
            self.adjacency[dst].append((src, w))  # undirected

    def dijkstra(self, start: str) -> Tuple[Dict[str, float], Dict[str, Optional[str]]]:
        """
        Run Dijkstra from a start node.

        Returns:
            dist: dict of shortest distances from start to each node
            prev: dict of previous node in shortest path (for path reconstruction)
        """
        dist = {nid: float("inf") for nid in self.nodes}
        prev = {nid: None for nid in self.nodes}
        dist[start] = 0.0
        visited: Set[str] = set()
        heap = [(0.0, start)]

        while heap:
            d, u = heapq.heappop(heap)
            if u in visited:
                continue
            visited.add(u)

            for v, w in self.adjacency.get(u, []):
                alt = d + w
                if alt < dist[v]:
                    dist[v] = alt
                    prev[v] = u
                    heapq.heappush(heap, (alt, v))

        return dist, prev

    def find_nearest_vacant(self, start: str, vacant_slots: List[str]) -> Dict:
        """
        Find the nearest vacant slot from the start position.

        Per SRS R2: When multiple slots share the same shortest distance,
        choose the slot with the smallest ID (deterministic tie-breaking).

        Args:
            start: Starting node ID (e.g., 'E1' for entrance).
            vacant_slots: List of slot IDs that are currently vacant.

        Returns:
            Dict with:
                - 'target_slot': str, the chosen slot ID (or None if no vacant)
                - 'distance': float, shortest distance
                - 'path': list of node IDs from start to target
        """
        if not vacant_slots:
            return {"target_slot": None, "distance": None, "path": []}

        dist, prev = self.dijkstra(start)

        # Find minimum distance among vacant slots
        min_dist = float("inf")
        for sid in vacant_slots:
            if sid in dist and dist[sid] < min_dist:
                min_dist = dist[sid]

        if min_dist == float("inf"):
            return {"target_slot": None, "distance": None, "path": []}

        # Among slots with min distance, pick the smallest ID (tie-breaking)
        candidates = [sid for sid in vacant_slots
                      if sid in dist and abs(dist[sid] - min_dist) < 1e-9]
        candidates.sort()  # lexicographic sort for deterministic tie-breaking
        target = candidates[0]

        # Reconstruct path
        path = self._reconstruct_path(prev, start, target)

        return {
            "target_slot": target,
            "distance": round(min_dist, 2),
            "path": path,
        }

    @staticmethod
    def _reconstruct_path(prev: Dict[str, Optional[str]],
                          start: str, end: str) -> List[str]:
        """Reconstruct the path from start to end using the prev dict."""
        path = []
        current = end
        while current is not None:
            path.append(current)
            if current == start:
                break
            current = prev.get(current)
        path.reverse()
        return path

    def get_all_distances(self, start: str) -> Dict[str, float]:
        """Get distances from start to all slot nodes."""
        dist, _ = self.dijkstra(start)
        return {nid: d for nid, d in dist.items()
                if self.nodes[nid].get("type") == "slot"}
