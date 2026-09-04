import os
import json
import re

def get_workorder_statuses(mailbox_dir):
    """Mock logic to read mailbox and determine statuses."""
    statuses = {}
    if not os.path.exists(mailbox_dir):
        return statuses
        
    for root, _, files in os.walk(mailbox_dir):
        for file in files:
            if file.endswith('.json'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if 'workorder_id' in data:
                            statuses[data['workorder_id']] = data.get('status', 'OPEN')
                except Exception:
                    pass
    return statuses

def update_holemap(docs_dir, statuses):
    """Updates docs/HOLEMAP.md with the new statuses."""
    holemap_path = os.path.join(docs_dir, 'HOLEMAP.md')
    if not os.path.exists(holemap_path):
        return

    with open(holemap_path, 'r', encoding='utf-8') as f:
        content = f.read()

    def replacer(match):
        wo_id = match.group(1)
        rest_of_line = match.group(2)
        current_status = match.group(3)
        
        new_status = statuses.get(wo_id, current_status)
        return f"| **{wo_id}**{rest_of_line}| {new_status} |"

    pattern = re.compile(r'\|\s*\*\*([A-Z0-9-]+)\*\*(.*?)\|\s*([A-Z]+)\s*\|')
    new_content = pattern.sub(replacer, content)

    with open(holemap_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

def main():
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mailbox_dir = os.path.join(base_dir, 'mailbox')
    docs_dir = os.path.join(base_dir, 'docs')
    
    statuses = get_workorder_statuses(mailbox_dir)
    update_holemap(docs_dir, statuses)

if __name__ == '__main__':
    main()
