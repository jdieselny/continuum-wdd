import os
import json
import jsonschema
from datetime import datetime, timezone

def validate_all():
    directories = ["mailbox", "workorders"]
    all_valid = True
    
    for directory in directories:
        if not os.path.exists(directory):
            continue
            
        for root, _, files in os.walk(directory):
            for file in files:
                if file.endswith(".json"):
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                            
                        if "$schema" not in data:
                            # If no schema is specified, we can't validate it against one
                            continue
                            
                        schema_ref = data["$schema"]
                        if schema_ref.startswith("https://wdd.jdieselny.com/schemas/"):
                            schema_filename = schema_ref.split("/")[-1]
                            schema_path = os.path.join("schemas", schema_filename)
                        else:
                            schema_path = os.path.normpath(os.path.join(os.path.dirname(file_path), schema_ref))
                        
                        if not os.path.exists(schema_path):
                            print(f"FAIL: Schema missing for {file_path}: {schema_path}")
                            all_valid = False
                            continue
                            
                        with open(schema_path, "r", encoding="utf-8") as sf:
                            schema_data = json.load(sf)
                            
                        jsonschema.validate(instance=data, schema=schema_data)
                        
                        if "expires_at" in data:
                            expires_at_str = data["expires_at"]
                            try:
                                expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
                                if expires_at_dt < datetime.now(timezone.utc):
                                    print(f"FAIL: Workorder expired {file_path}: {expires_at_str}")
                                    all_valid = False
                                    continue
                            except ValueError as e:
                                print(f"FAIL: Invalid expiry format in {file_path}: {e}")
                                all_valid = False
                                continue

                        print(f"PASS: {file_path}")
                    except json.JSONDecodeError as e:
                        print(f"FAIL: Malformed JSON in {file_path}: {e}")
                        all_valid = False
                    except jsonschema.exceptions.ValidationError as e:
                        print(f"FAIL: Validation failed for {file_path}: {e.message}")
                        all_valid = False
                    except Exception as e:
                        print(f"FAIL: Unexpected error in {file_path}: {e}")
                        all_valid = False

    return all_valid
