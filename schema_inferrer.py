import datetime

def get_type(value):
    if isinstance(value, bool):
        return "boolean"
    elif isinstance(value, int):
        return "integer"
    elif isinstance(value, float):
        return "float"
    elif isinstance(value, str):
        return "string"
    elif isinstance(value, list):
        return "array"
    elif isinstance(value, dict):
        return "object"
    elif value is None:
        return "null"
    else:
        return "unknown"


def analyze_document(doc, schema=None, prefix=""):
    if schema is None:
        schema = {}

    for key, value in doc.items():
        full_key = f"{prefix}.{key}" if prefix else key
        type_found = get_type(value)

        if full_key not in schema:
            schema[full_key] = {"types": {}, "count": 0, "samples": []}

        schema[full_key]["count"] += 1

        if type_found not in schema[full_key]["types"]:
            schema[full_key]["types"][type_found] = 0
        schema[full_key]["types"][type_found] += 1

        # Collecter des exemples de valeurs (max 3, primitives uniquement)
        if value is not None and not isinstance(value, (dict, list)):
            if len(schema[full_key]["samples"]) < 3:
                # Convertir les types non-JSON (datetime, ObjectId...) en string
                if isinstance(value, (str, int, float, bool)):
                    schema[full_key]["samples"].append(value)
                else:
                    schema[full_key]["samples"].append(str(value))

        # Si c'est un objet imbriqué => on descend récursivement
        if isinstance(value, dict):
            analyze_document(value, schema, prefix=full_key)

        # Si c'est un tableau d'objets => on analyse chaque élément
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    analyze_document(item, schema, prefix=full_key)

    return schema


def infer_schema(documents):
    total = len(documents)
    schema = {}

    for doc in documents:
        analyze_document(doc, schema)

    # Calculer le pourcentage de présence de chaque champ
    result = {}
    for field, info in schema.items():
        result[field] = {
            "types": info["types"],
            "count": info["count"],
            "presence": round((info["count"] / total) * 100, 1),
            "samples": info.get("samples", [])  # valeurs d'exemple pour l'audit
        }

    return result


def display_schema(schema):
    print(f"\n{'='*55}")
    print(f"  SCHÉMA INFÉRÉ - {len(schema)} champs détectés")
    print(f"{'='*55}")
    print(f"{'Champ':<30} {'Type(s)':<15} {'Présence'}")
    print(f"{'-'*55}")
    for field, info in sorted(schema.items()):
        types_str = ", ".join(
            f"{t}({n})" for t, n in info["types"].items()
        )
        print(f"{field:<30} {types_str:<15} {info['presence']}%")
    print(f"{'='*55}\n")