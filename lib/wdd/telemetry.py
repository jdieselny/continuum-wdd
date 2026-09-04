import json
import uuid
import datetime
import os
from pathlib import Path

def emit_event(workorder_id: str, agent_id: str, transition: str, output_dir: str = "mailbox/events") -> str:
    """
    Emit a telemetry event on state transition.
    Returns the path to the written event JSON.
    """
    event_id = str(uuid.uuid4())
    # Format timestamp as ISO 8601
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    event = {
        "event_id": event_id,
        "timestamp": timestamp,
        "workorder_id": workorder_id,
        "agent_id": agent_id,
        "transition": transition
    }
    
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    
    filepath = out_path / f"{event_id}.json"
    
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(event, f, indent=2)
        
    return str(filepath)
