import os
import json
import uuid
from datetime import datetime

SNAPSHOTS_FILE = "snapshots.json"

def load_snapshots():
    if not os.path.exists(SNAPSHOTS_FILE):
        return []
    try:
        with open(SNAPSHOTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_snapshot(label, db_type, db_name, coll_name, schema):
    snapshots = load_snapshots()
    
    # Format schema from dict to list of fields to match our logic
    formatted_schema = []
    for field_path, info in schema.items():
        types_list = [{"type": t, "frequency": freq} for t, freq in info.get("types", {}).items()]
        formatted_schema.append({
            "field_path": field_path,
            "types": types_list,
            "presence_percentage": info.get("presence", 0),
            "occurrences": info.get("count", 0)
        })

    new_snap = {
        "snapshot_id": str(uuid.uuid4()),
        "label": label,
        "timestamp": datetime.now().isoformat(),
        "database_type": db_type,
        "database_name": db_name,
        "collection_name": coll_name,
        "schema": formatted_schema
    }
    
    snapshots.append(new_snap)
    
    # Keep only the last 50
    if len(snapshots) > 50:
        snapshots = snapshots[-50:]
        
    with open(SNAPSHOTS_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshots, f, indent=2)

def get_dominant_type(types_list):
    if not types_list:
        return None
    # sort by frequency descending
    sorted_types = sorted(types_list, key=lambda x: x["frequency"], reverse=True)
    return sorted_types[0]["type"]

def determine_severity(drift_type, old_presence, new_presence, field_name):
    field_name_lower = field_name.lower()
    is_critical_name = any(k in field_name_lower for k in ["id", "key", "ref"])
    
    if drift_type == "TYPE_CHANGED" and is_critical_name:
        return "CRITICAL"
    if drift_type == "TYPE_MIXED":
        return "HIGH"
    if drift_type == "PRESENCE_DROPPED" and old_presence == 100 and new_presence < 100:
        return "HIGH"
    if drift_type == "FIELD_ADDED" and new_presence == 100:
        return "MEDIUM"
        
    if drift_type == "FIELD_REMOVED":
        return "CRITICAL" if old_presence >= 100 else "HIGH"
    if drift_type == "TYPE_CHANGED":
        if old_presence >= 100: return "CRITICAL"
        if old_presence > 50: return "HIGH"
        return "MEDIUM"
    if drift_type == "PRESENCE_DROPPED":
        return "MEDIUM"
    if drift_type == "FIELD_ADDED":
        return "INFO" if new_presence < 100 else "MEDIUM"
    if drift_type == "PRESENCE_INCREASED":
        return "INFO"
        
    return "INFO"

def compare_snapshots(snap_a, snap_b):
    results = []
    
    map_a = {f["field_path"]: f for f in snap_a["schema"]}
    map_b = {f["field_path"]: f for f in snap_b["schema"]}
    
    all_fields = set(map_a.keys()).union(set(map_b.keys()))
    
    critical_count = high_count = medium_count = 0
    patterns = set()
    added_fields = []
    removed_fields = []
    
    for field_path in all_fields:
        old_f = map_a.get(field_path)
        new_f = map_b.get(field_path)
        
        name_part = field_path.split(".")[-1]
        
        drift_type = None
        old_val = None
        new_val = None
        pattern = "NONE"
        pattern_details = ""
        
        old_presence = old_f["presence_percentage"] if old_f else 0
        new_presence = new_f["presence_percentage"] if new_f else 0
        
        if old_f and not new_f:
            drift_type = "FIELD_REMOVED"
            old_val = old_f["types"][0]["type"] if old_f["types"] else None
            removed_fields.append(old_f)
        elif not old_f and new_f:
            drift_type = "FIELD_ADDED"
            new_val = new_f["types"][0]["type"] if new_f["types"] else None
            added_fields.append(new_f)
        elif old_f and new_f:
            old_dom = get_dominant_type(old_f["types"])
            new_dom = get_dominant_type(new_f["types"])
            is_type_mixed = False
            
            if old_dom != new_dom:
                drift_type = "TYPE_CHANGED"
                old_val = old_dom
                new_val = new_dom
                if new_presence == 100:
                    pattern = "TYPE_MIGRATION"
                    pattern_details = "Planned migration (low risk)"
                    patterns.add(pattern)
            
            elif len(old_f["types"]) == 1 and len(new_f["types"]) > 1:
                is_type_mixed = True
                drift_type = "TYPE_MIXED"
                old_val = old_dom
                new_val = ", ".join([t["type"] for t in new_f["types"]])
            
            else:
                presence_diff = new_presence - old_presence
                if presence_diff < 0:
                    drift_type = "PRESENCE_DROPPED"
                    old_val = f"{old_presence}%"
                    new_val = f"{new_presence}%"
                    if old_presence == 100:
                        pattern = "SILENT_NULLABLE"
                        pattern_details = "Field became nullable"
                        patterns.add(pattern)
                elif presence_diff > 0:
                    drift_type = "PRESENCE_INCREASED"
                    old_val = f"{old_presence}%"
                    new_val = f"{new_presence}%"

        if drift_type:
            severity = determine_severity(drift_type, old_presence, new_presence, name_part)
            
            if severity == "CRITICAL": critical_count += 1
            elif severity == "HIGH": high_count += 1
            elif severity == "MEDIUM": medium_count += 1
            
            old_occ = old_f["occurrences"] if old_f else 0
            new_occ = new_f["occurrences"] if new_f else 0
            
            old_p_dec = (old_presence or 1) / 100
            new_p_dec = (new_presence or 1) / 100
            total_docs = max(old_occ, new_occ) / max(old_p_dec, new_p_dec)
            
            affected_percent = abs(new_presence - old_presence)
            try:
                impact = int(round(total_docs * (affected_percent / 100)))
            except:
                impact = abs(new_occ - old_occ)
                
            results.append({
                "field_path": field_path,
                "drift_type": drift_type,
                "type_of_old_value": old_val,
                "type_of_new_value": new_val,
                "information_useful_in_inspector": f"{pattern_details} | Impact: {impact}" if pattern_details else f"Impact: {impact}"
            })

    # Pattern: Rename
    for added in added_fields:
        potential = [r for r in removed_fields if get_dominant_type(r["types"]) == get_dominant_type(added["types"]) and abs(r["presence_percentage"] - added["presence_percentage"]) < 5]
        if len(potential) == 1:
            rem = potential[0]
            for res in results:
                if res["field_path"] == added["field_path"]:
                    res["information_useful_in_inspector"] = f"Possible rename: {rem['field_path']} -> {added['field_path']} | {res['information_useful_in_inspector']}"
                    patterns.add("FIELD_RENAME")
                if res["field_path"] == rem["field_path"]:
                    res["information_useful_in_inspector"] = f"Renamed to {added['field_path']} | {res['information_useful_in_inspector']}"

    # Stability Score
    stability_score = 0
    if len(snap_a["schema"]) == len(snap_b["schema"]) and len(results) == 0:
        stability_score = 100
    else:
        if critical_count == 0: stability_score += 40
        if high_count == 0: stability_score += 30
        if medium_count == 0: stability_score += 20
        if len(snap_a["schema"]) == len(snap_b["schema"]): stability_score += 10
        
    return {
        "results": results,
        "stability_score": stability_score,
        "patterns_detected": list(patterns)
    }
