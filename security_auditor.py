"""
security_auditor.py
Module d'audit de vulnérabilités de sécurité pour bases NoSQL.
Fonctionne sur n'importe quelle collection (MongoDB, CouchDB, Firestore).
"""
import re
from typing import Any

# ── CHAMPS SENSIBLES ─────────────────────────────────────────

PASSWORD_FIELDS = {
    "password", "passwd", "pwd", "pass", "mdp",
    "motdepasse", "mot_de_passe", "userpassword", "userpass"
}

PII_FIELDS = {
    "email", "mail", "phone", "telephone", "mobile", "tel",
    "ssn", "nationalid", "cin", "nni",
    "dob", "birthdate", "datenaissance",
    "address", "adresse", "postcode", "zipcode"
}

TOKEN_FIELDS = {
    "token", "apikey", "api_key", "secret", "secretkey",
    "accesstoken", "refreshtoken", "authtoken", "jwt", "bearer"
}

CARD_FIELDS = {
    "card", "creditcard", "cardnumber", "pan",
    "cvv", "cvc", "expiry", "expirydate"
}

ROLE_FIELDS = {"role", "isadmin", "admin", "privilege"}

PERMISSION_FIELDS = {"permissions", "acl", "scope", "rights"}

FINANCIAL_FIELDS = {
    "amount", "balance", "solde", "montant",
    "price", "prix", "total", "credit", "debit"
}

TIMESTAMP_FIELDS = {
    "createdat", "created_at", "updatedat", "updated_at",
    "timestamp", "datecreation", "datemodification"
}

NOSQL_OPERATORS = {
    "$where", "$gt", "$lt", "$gte", "$lte", "$ne",
    "$in", "$nin", "$or", "$and", "$regex", "$exists", "$expr"
}

# ── PATTERNS DE HACHAGE ──────────────────────────────────────

BCRYPT_RE  = re.compile(r'^\$2[ab]\$\d{2}\$.{53}$')
ARGON2_RE  = re.compile(r'^\$argon2(i|d|id)\$')
PBKDF2_RE  = re.compile(r'^pbkdf2\$')
SHA512_RE  = re.compile(r'^[a-fA-F0-9]{128}$')
SHA256_RE  = re.compile(r'^[a-fA-F0-9]{64}$')
MD5_RE     = re.compile(r'^[a-fA-F0-9]{32}$')
JWT_RE     = re.compile(r'^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$')

# ── UTILITAIRES ──────────────────────────────────────────────

def _normalize(field: str) -> str:
    """Dernier segment du champ, en minuscules, sans ponctuation."""
    return field.split(".")[-1].lower().replace("_", "").replace("-", "")


def _mask(value: Any) -> str:
    """Tronque une valeur sensible pour affichage sécurisé."""
    s = str(value)
    if len(s) <= 4:
        return "***"
    return s[:2] + "*" * min(len(s) - 4, 6) + s[-2:]


def _is_hashed(value: str) -> tuple:
    """Retourne (est_haché: bool, algo: str)."""
    if not isinstance(value, str):
        return False, ""
    v = value.strip()
    if BCRYPT_RE.match(v):  return True, "bcrypt"
    if ARGON2_RE.match(v):  return True, "argon2"
    if PBKDF2_RE.match(v):  return True, "pbkdf2"
    if SHA512_RE.match(v):  return True, "sha512"
    if SHA256_RE.match(v):  return True, "sha256"
    if MD5_RE.match(v):     return True, "md5"
    return False, ""


def _get_values(docs: list, field_path: str) -> list:
    """Extrait toutes les valeurs d'un champ (notation pointée) dans les docs."""
    parts = field_path.split(".")
    values = []
    for doc in docs:
        node = doc
        for part in parts:
            if isinstance(node, dict):
                node = node.get(part)
            else:
                node = None
                break
        if node is not None:
            values.append(node)
    return values

# ── RÈGLES DE DÉTECTION ──────────────────────────────────────

AUDIT_MESSAGES = {
    "English": {
        "PLAINTEXT_PASSWORD": "The field '{field}' contains plaintext passwords (not hashed).",
        "WEAK_HASH_MD5": "The field '{field}' uses MD5, a deprecated algorithm vulnerable to rainbow tables.",
        "PII_EXPOSED": "The field '{field}' contains personally identifiable information (PII) stored in plaintext.",
        "TOKEN_EXPOSED": "The field '{field}' contains plaintext tokens/API keys.",
        "NOSQL_INJECTION_RISK": "The field '{field}' contains NoSQL operators in its values (injection risk).",
        "TYPE_JUGGLING": "The sensitive field '{field}' has mixed types ({types}), type juggling risk.",
        "CARD_DATA_EXPOSED": "The field '{field}' potentially exposes credit card data (PCI-DSS violation).",
        "MISSING_TIMESTAMPS": "The collection lacks traceability fields (createdAt/updatedAt). Audit trail is impossible.",
        "ROLE_FIELD_EXPOSED": "The field '{field}' exposes roles/privileges in plaintext without protection.",
        "UNSTRUCTURED_PERMISSIONS": "The field '{field}' stores permissions as an unstructured string (bypass risk)."
    },
    "Français": {
        "PLAINTEXT_PASSWORD": "Le champ '{field}' contient des mots de passe en clair (non hachés).",
        "WEAK_HASH_MD5": "Le champ '{field}' utilise MD5, un algorithme déprécié et vulnérable aux rainbow tables.",
        "PII_EXPOSED": "Le champ '{field}' contient des données personnelles (PII) stockées en clair.",
        "TOKEN_EXPOSED": "Le champ '{field}' contient des tokens/clés API en clair.",
        "NOSQL_INJECTION_RISK": "Le champ '{field}' contient des opérateurs NoSQL dans ses valeurs (risque d'injection).",
        "TYPE_JUGGLING": "Le champ sensible '{field}' a des types mixtes ({types}), risque de type juggling.",
        "CARD_DATA_EXPOSED": "Le champ '{field}' expose potentiellement des données bancaires (violation PCI-DSS).",
        "MISSING_TIMESTAMPS": "La collection n'a pas de champs de traçabilité (createdAt/updatedAt). L'audit trail est impossible.",
        "ROLE_FIELD_EXPOSED": "Le champ '{field}' expose les rôles/privilèges en clair sans protection.",
        "UNSTRUCTURED_PERMISSIONS": "Le champ '{field}' stocke les permissions en string non structurée (risque de bypass)."
    }
}

def _msg(rule: str, lang: str, **kwargs) -> str:
    """Helper to safely retrieve and format localized rules messages."""
    template = AUDIT_MESSAGES.get(lang, AUDIT_MESSAGES["English"]).get(rule, "")
    return template.format(**kwargs)


def _rule_password(docs, schema, lang="English"):
    """Règles 1 & 2 : mot de passe en clair / haché avec MD5."""
    findings = []
    for field in schema:
        if _normalize(field) not in PASSWORD_FIELDS:
            continue
        values = _get_values(docs, field)
        plaintext, md5_vals = [], []
        for v in values:
            if not isinstance(v, str):
                continue
            hashed, algo = _is_hashed(v)
            if not hashed:
                plaintext.append(v)
            elif algo == "md5":
                md5_vals.append(v)
        if plaintext:
            findings.append({
                "field": field, "rule": "PLAINTEXT_PASSWORD",
                "severity": "CRITICAL",
                "message": _msg("PLAINTEXT_PASSWORD", lang, field=field),
                "affected_docs": len(plaintext),
                "sample": _mask(plaintext[0])
            })
        if md5_vals:
            findings.append({
                "field": field, "rule": "WEAK_HASH_MD5",
                "severity": "HIGH",
                "message": _msg("WEAK_HASH_MD5", lang, field=field),
                "affected_docs": len(md5_vals),
                "sample": _mask(md5_vals[0])
            })
    return findings


def _rule_pii(docs, schema, lang="English"):
    """Règle 3 : données personnelles (PII) stockées en clair."""
    findings = []
    for field in schema:
        if _normalize(field) not in PII_FIELDS:
            continue
        values = _get_values(docs, field)
        exposed = [v for v in values if isinstance(v, str) and v.strip()]
        if exposed:
            findings.append({
                "field": field, "rule": "PII_EXPOSED",
                "severity": "HIGH",
                "message": _msg("PII_EXPOSED", lang, field=field),
                "affected_docs": len(exposed),
                "sample": _mask(exposed[0])
            })
    return findings


def _rule_token(docs, schema, lang="English"):
    """Règle 4 : tokens / clés API non protégés."""
    findings = []
    for field in schema:
        if _normalize(field) not in TOKEN_FIELDS:
            continue
        values = _get_values(docs, field)
        exposed = []
        for v in values:
            if not isinstance(v, str):
                continue
            hashed, _ = _is_hashed(v)
            if not hashed and not JWT_RE.match(v.strip()):
                exposed.append(v)
        if exposed:
            findings.append({
                "field": field, "rule": "TOKEN_EXPOSED",
                "severity": "HIGH",
                "message": _msg("TOKEN_EXPOSED", lang, field=field),
                "affected_docs": len(exposed),
                "sample": _mask(exposed[0])
            })
    return findings


def _rule_nosql_injection(docs, schema, lang="English"):
    """Règle 5 : valeurs contenant des opérateurs NoSQL."""
    findings = []
    for field, info in schema.items():
        if "string" not in info.get("types", {}):
            continue
        values = _get_values(docs, field)
        suspicious = [
            v for v in values
            if isinstance(v, str) and any(op in v for op in NOSQL_OPERATORS)
        ]
        if suspicious:
            findings.append({
                "field": field, "rule": "NOSQL_INJECTION_RISK",
                "severity": "MEDIUM",
                "message": _msg("NOSQL_INJECTION_RISK", lang, field=field),
                "affected_docs": len(suspicious),
                "sample": _mask(suspicious[0])
            })
    return findings


def _rule_type_juggling(docs, schema, lang="English"):
    """Règle 6 : champs financiers/rôles avec types mixtes (type juggling)."""
    sensitive = FINANCIAL_FIELDS | {"role", "isadmin", "admin"}
    findings = []
    for field, info in schema.items():
        if _normalize(field) not in sensitive:
            continue
        types = info.get("types", {})
        if len(types) > 1:
            findings.append({
                "field": field, "rule": "TYPE_JUGGLING",
                "severity": "MEDIUM",
                "message": _msg("TYPE_JUGGLING", lang, field=field, types=", ".join(types.keys())),
                "affected_docs": info.get("count", 0),
                "sample": "-"
            })
    return findings


def _rule_card_data(docs, schema, lang="English"):
    """Règle 7 : données de carte bancaire exposées."""
    findings = []
    for field in schema:
        if _normalize(field) not in CARD_FIELDS:
            continue
        values = _get_values(docs, field)
        exposed = [v for v in values if v is not None]
        if exposed:
            findings.append({
                "field": field, "rule": "CARD_DATA_EXPOSED",
                "severity": "CRITICAL",
                "message": _msg("CARD_DATA_EXPOSED", lang, field=field),
                "affected_docs": len(exposed),
                "sample": _mask(str(exposed[0]))
            })
    return findings


def _rule_missing_timestamps(docs, schema, lang="English"):
    """Règle 8 : absence de champs de traçabilité."""
    fields_norm = {_normalize(f) for f in schema}
    if not any(f in TIMESTAMP_FIELDS for f in fields_norm):
        return [{
            "field": "-", "rule": "MISSING_TIMESTAMPS",
            "severity": "INFO",
            "message": _msg("MISSING_TIMESTAMPS", lang),
            "affected_docs": len(docs),
            "sample": "-"
        }]
    return []


def _rule_role_exposed(docs, schema, lang="English"):
    """Règle 9 : champs role/isAdmin exposés en clair."""
    findings = []
    for field in schema:
        if _normalize(field) not in ROLE_FIELDS:
            continue
        values = _get_values(docs, field)
        exposed = [v for v in values if v is not None]
        if exposed:
            findings.append({
                "field": field, "rule": "ROLE_FIELD_EXPOSED",
                "severity": "MEDIUM",
                "message": _msg("ROLE_FIELD_EXPOSED", lang, field=field),
                "affected_docs": len(exposed),
                "sample": _mask(str(exposed[0]))
            })
    return findings


def _rule_unstructured_permissions(docs, schema, lang="English"):
    """Règle 10 : permissions/ACL stockées en string non structurée."""
    findings = []
    for field, info in schema.items():
        if _normalize(field) not in PERMISSION_FIELDS:
            continue
        if "string" in info.get("types", {}):
            values = _get_values(docs, field)
            plain = [v for v in values if isinstance(v, str)]
            if plain:
                findings.append({
                    "field": field, "rule": "UNSTRUCTURED_PERMISSIONS",
                    "severity": "MEDIUM",
                    "message": _msg("UNSTRUCTURED_PERMISSIONS", lang, field=field),
                    "affected_docs": len(plain),
                    "sample": _mask(plain[0])
                })
    return findings

# ── SCORE DE SÉCURITÉ ─────────────────────────────────────────

PENALTY = {"CRITICAL": 20, "HIGH": 10, "MEDIUM": 5, "INFO": 2}

def compute_score(findings: list) -> int:
    """Score de sécurité de 0 à 100."""
    return max(0, 100 - sum(PENALTY.get(f["severity"], 0) for f in findings))

# ── POINT D'ENTRÉE ────────────────────────────────────────────

_RULES = [
    _rule_password,
    _rule_pii,
    _rule_token,
    _rule_nosql_injection,
    _rule_type_juggling,
    _rule_card_data,
    _rule_missing_timestamps,
    _rule_role_exposed,
    _rule_unstructured_permissions,
]


def run_audit(docs: list, schema: dict, lang: str = "English") -> dict:
    """
    Lance l'audit de sécurité sur une collection.

    Args:
        docs:   liste de documents bruts (dicts Python)
        schema: schéma inféré par infer_schema()
        lang:   langue active ("English" ou "Français")

    Returns:
        {
            "findings": [liste de vulnérabilités],
            "score":    int (0–100),
            "summary":  {"CRITICAL": n, "HIGH": n, "MEDIUM": n, "INFO": n}
        }
    """
    if not docs:
        return {"findings": [], "score": 100,
                "summary": {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "INFO": 0}}

    findings = []
    for rule_fn in _RULES:
        findings.extend(rule_fn(docs, schema, lang=lang))

    summary = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "INFO": 0}
    for f in findings:
        summary[f.get("severity", "INFO")] = summary.get(f.get("severity", "INFO"), 0) + 1

    return {
        "findings": findings,
        "score": compute_score(findings),
        "summary": summary
    }

