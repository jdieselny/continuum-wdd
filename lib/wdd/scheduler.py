"""
scheduler.py
Topological scheduler for WDD envelopes based on dependencies.
"""
from typing import List, Dict, Any

def schedule_envelopes(envelopes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Performs a topological sort of envelopes based on their 'dependencies'.
    Raises ValueError if a cycle is detected.
    """
    graph: Dict[str, List[str]] = {}
    in_degree: Dict[str, int] = {}
    by_id: Dict[str, Dict[str, Any]] = {}

    for env in envelopes:
        env_id = env.get("workorder_id", env.get("id"))
        if not env_id:
            continue
        by_id[env_id] = env
        if env_id not in in_degree:
            in_degree[env_id] = 0
        if env_id not in graph:
            graph[env_id] = []

    for env in envelopes:
        env_id = env.get("workorder_id", env.get("id"))
        if not env_id:
            continue
        for dep in env.get("dependencies", []):
            if dep not in graph:
                graph[dep] = []
            if dep not in in_degree:
                in_degree[dep] = 0
            
            # dep -> env_id
            graph[dep].append(env_id)
            in_degree[env_id] += 1

    queue = [n for n in in_degree if in_degree[n] == 0]
    sorted_order = []

    while queue:
        curr = queue.pop(0)
        sorted_order.append(curr)
        for neighbor in graph[curr]:
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    if len(sorted_order) != len(in_degree):
        raise ValueError("Cycle detected in envelope dependencies.")

    return [by_id[node] for node in sorted_order if node in by_id]
