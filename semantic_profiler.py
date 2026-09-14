import os
import re
import io
import json
import csv
import datetime
from dataclasses import dataclass, asdict
from typing import Any, List, Dict, Tuple, Optional
import pandas as pd
from dateutil import parser as date_parser

# ── DATACLASSSES ──────────────────────────────────────────────

@dataclass
class SemanticFinding:
    field_path: str
    rule_name: str
    severity: str  # "CRITICAL" | "HIGH" | "MEDIUM" | "INFO"
    affected_count: int
    total_count: int
    affected_rate: float
    examples: List[str]
    suggestion: str

@dataclass  
class FieldProfile:
    field_path: str
    dominant_type: str
    null_rate: float
    unique_rate: float  # unique values / total
    top_values: List[Any]    # top 5 most frequent values
    min_val: Any
    max_val: Any
    avg_val: Optional[float]
    semantic_type: str  # inferred: EMAIL|PHONE|DATE|ID|PRICE|NAME|TEXT

@dataclass
class SemanticReport:
    collection_name: str
    total_documents: int
    total_fields_analyzed: int
    quality_score: float
    grade: str  # A(90+), B(75+), C(60+), D(40+), F(<40)
    findings: List[SemanticFinding]
    field_profiles: Dict[str, FieldProfile]
    generated_at: datetime.datetime

# ── HELPER FUNCTIONS ──────────────────────────────────────────

def flatten_dict(d: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """
    Flatten nested dictionary structures using dot notation.
    Lists of dictionaries or primitives are kept as a list key,
    and also expanded with numeric indices to enable easy flat querying.
    """
    flat = {}
    for k, v in d.items():
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            flat.update(flatten_dict(v, key))
        elif isinstance(v, list):
            flat[key] = v
            for i, item in enumerate(v):
                if isinstance(item, dict):
                    flat.update(flatten_dict(item, f"{key}.{i}"))
                else:
                    flat[f"{key}.{i}"] = item
        else:
            flat[key] = v
    return flat

def mask_value(val: Any) -> str:
    """
    Mask sensitive values (e.g. email, phone, etc.) for reporting.
    """
    s = str(val).strip()
    if not s:
        return ""
    if "@" in s:
        parts = s.split("@", 1)
        local, domain = parts[0], parts[1]
        
        if len(local) <= 2:
            masked_local = local[0] + "*"
        else:
            masked_local = local[0] + "*" * (len(local) - 2) + local[-1]
            
        if "." in domain:
            dparts = domain.split(".")
            masked_dparts = []
            for dp in dparts[:-1]:
                if len(dp) <= 2:
                    masked_dparts.append(dp[0] + "*")
                else:
                    masked_dparts.append(dp[0] + "*" * (len(dp) - 2) + dp[-1])
            masked_dparts.append(dparts[-1])
            masked_domain = ".".join(masked_dparts)
        else:
            masked_domain = domain[0] + "*" * (len(domain) - 1)
        return f"{masked_local}@{masked_domain}"
    
    if len(s) <= 4:
        return s[0] + "*" * (len(s) - 1)
    return s[:2] + "*" * (len(s) - 4) + s[-2:]

def parse_date_safely(val: Any) -> Optional[datetime.datetime]:
    """
    Parse date safely, ensuring it is a valid date string.
    """
    dt = None
    if isinstance(val, (datetime.datetime, datetime.date)):
        if isinstance(val, datetime.date) and not isinstance(val, datetime.datetime):
            dt = datetime.datetime.combine(val, datetime.time.min)
        else:
            dt = val
    elif isinstance(val, str) and val.strip():
        if any(c in val for c in ("-", "/", ":", " ")) and not val.isdigit():
            try:
                dt = date_parser.parse(val)
            except Exception:
                pass
    if dt is not None:
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    return None

# ── PROFILER CLASS ────────────────────────────────────────────

class SemanticProfiler:
    """
    Analyzes collection documents to identify semantic anomalies and data quality.
    """
    def __init__(self, documents: List[Dict[str, Any]], collection_name: str):
        self.documents = documents
        self.collection_name = collection_name
        self._flattened_cache: Optional[List[Dict[str, Any]]] = None

    def flatten_documents(self) -> List[Dict[str, Any]]:
        """Flatten nested docs using dot notation, with caching."""
        if self._flattened_cache is not None:
            return self._flattened_cache
        self._flattened_cache = [flatten_dict(doc) for doc in self.documents]
        return self._flattened_cache

    def get_field_sample(self, field_path: str, n: int = 100) -> List[Any]:
        """Extract up to n non-null values for a field."""
        values = []
        for doc in self.documents:
            flat = flatten_dict(doc)
            # Find any keys matching the stripped path
            matched_vals = []
            for k, v in flat.items():
                parts = k.split('.')
                stripped_parts = [p for p in parts if not p.isdigit()]
                if '.'.join(stripped_parts) == field_path:
                    if v is not None:
                        matched_vals.append(v)
            values.extend(matched_vals)
            if len(values) >= n:
                return values[:n]
        return values

    def compute_quality_score(self, findings: List[SemanticFinding]) -> float:
        """
        Score 0-100:
        - Start at 100
        - CRITICAL finding: -15 points each (cap: -40)
        - HIGH finding: -8 points each (cap: -25)
        - MEDIUM finding: -3 points each (cap: -20)
        - INFO finding: -1 point each (cap: -10)
        - Minimum score: 5
        """
        critical_count = sum(1 for f in findings if f.severity == "CRITICAL")
        high_count = sum(1 for f in findings if f.severity == "HIGH")
        medium_count = sum(1 for f in findings if f.severity == "MEDIUM")
        info_count = sum(1 for f in findings if f.severity == "INFO")

        critical_ded = min(40, critical_count * 15)
        high_ded = min(25, high_count * 8)
        medium_ded = min(20, medium_count * 3)
        info_ded = min(10, info_count * 1)

        total_ded = critical_ded + high_ded + medium_ded + info_ded
        return max(5.0, 100.0 - total_ded)

    def _get_grade(self, score: float) -> str:
        """Grade A(90+), B(75+), C(60+), D(40+), F(<40)"""
        if score >= 90:
            return "A"
        elif score >= 75:
            return "B"
        elif score >= 60:
            return "C"
        elif score >= 40:
            return "D"
        else:
            return "F"

    def _get_field_series_and_indices(self, df: pd.DataFrame, field_path: str) -> Tuple[pd.Series, List[str]]:
        """
        Retrieves all values representing field_path from flattened df,
        uniquely matching list elements (e.g. items.0.price maps to items.price).
        Returns a single flat Series of values, and the columns matched.
        """
        matched_cols = []
        for col in df.columns:
            parts = col.split('.')
            stripped_parts = [p for p in parts if not p.isdigit()]
            if '.'.join(stripped_parts) == field_path:
                matched_cols.append(col)
        
        if not matched_cols:
            return pd.Series(dtype=object), []
        
        # Stack all matched columns to form a single series of values
        stacked = df[matched_cols].stack()
        return stacked, matched_cols

    def profile(self) -> SemanticReport:
        """Run all rules, return full report."""
        if not self.documents:
            return SemanticReport(
                collection_name=self.collection_name,
                total_documents=0,
                total_fields_analyzed=0,
                quality_score=100.0,
                grade="A",
                findings=[],
                field_profiles={},
                generated_at=datetime.datetime.now()
            )

        # Flatten and load into pandas DataFrame
        
        flat_docs = self.flatten_documents()
        
        # Batch processing if needed (> 5000 docs)
        # However, for memory/profiling, we load the cached flattened docs.
        df = pd.DataFrame(flat_docs)
        
        total_docs = len(self.documents)

        # 1. Identify distinct stripped field paths
        all_fields_set = set()
        for col in df.columns:
            parts = col.split('.')
            stripped = '.'.join([p for p in parts if not p.isdigit()])
            all_fields_set.add(stripped)
        
        field_paths = sorted(list(all_fields_set))

        # 2. Compute Field Profiles
        field_profiles: Dict[str, FieldProfile] = {}
        for fp in field_paths:
            series, cols = self._get_field_series_and_indices(df, fp)
            if series.empty:
                continue
            
            # Non-null calculations
            non_null_count = len(series)
            null_count = total_docs - len(series.index.get_level_values(0).unique())
            null_rate = float(null_count / total_docs)
            
            # Make sure all elements in the series are hashable before calling nunique/value_counts
            hashable_series = series.map(lambda x: str(x) if isinstance(x, (list, dict)) else x)
            
            # Unique calculation
            unique_count = hashable_series.nunique()
            unique_rate = float(unique_count / non_null_count) if non_null_count > 0 else 0.0
            
            # Top values
            top_vals = hashable_series.value_counts().head(5).index.tolist()
            
            # Numeric stats
            min_val, max_val, avg_val = None, None, None
            # Extract dominant type
            types_counts = series.map(type).value_counts()
            dom_py_type = types_counts.index[0] if not types_counts.empty else str
            dominant_type = dom_py_type.__name__
            
            # Convert to numeric if possible to get stats
            numeric_series = pd.to_numeric(series, errors='coerce').dropna()
            if not numeric_series.empty:
                min_val = float(numeric_series.min())
                max_val = float(numeric_series.max())
                avg_val = float(numeric_series.mean())
            else:
                try:
                    min_val = series.min()
                    max_val = series.max()
                except Exception:
                    pass

            # Infer semantic type
            fp_lower = fp.split('.')[-1].lower().replace('_', '').replace('-', '')
            if fp_lower in ("email", "mail"):
                semantic_type = "EMAIL"
            elif fp_lower in ("phone", "tel", "mobile", "telephone"):
                semantic_type = "PHONE"
            elif any(k in fp_lower for k in ("date", "time", "createdat", "updatedat", "timestamp", "inscription")):
                semantic_type = "DATE"
            elif fp_lower.endswith("id") or fp_lower.endswith("code"):
                semantic_type = "ID"
            elif fp_lower in ("price", "amount", "total", "cost"):
                semantic_type = "PRICE"
            elif any(k in fp_lower for k in ("name", "firstname", "lastname", "title")):
                semantic_type = "NAME"
            elif dominant_type == "str":
                semantic_type = "TEXT"
            else:
                semantic_type = "TEXT"

            field_profiles[fp] = FieldProfile(
                field_path=fp,
                dominant_type=dominant_type,
                null_rate=null_rate,
                unique_rate=unique_rate,
                top_values=top_vals,
                min_val=min_val,
                max_val=max_val,
                avg_val=avg_val,
                semantic_type=semantic_type
            )

        # 3. Run Semantic Rules
        findings: List[SemanticFinding] = []

        # List of rules and matching logic
        for fp in field_paths:
            series, cols = self._get_field_series_and_indices(df, fp)
            if series.empty:
                continue

            last_part = fp.split('.')[-1].lower().replace('_', '').replace('-', '')
            
            # NUMERIC RULES
            # Check if numeric values are present
            numeric_vals = pd.to_numeric(series, errors='coerce').dropna()
            
            # NegativeValue
            if not numeric_vals.empty and last_part in ("price", "total", "amount", "quantity", "qty", "stock", "age", "score", "rating"):
                bad_mask = numeric_vals < 0
                if bad_mask.any():
                    bad_series = numeric_vals[bad_mask]
                    aff_docs = len(bad_series.index.get_level_values(0).unique())
                    examples = [mask_value(v) for v in bad_series.head(3)]
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="NegativeValue",
                        severity="HIGH",
                        affected_count=aff_docs,
                        total_count=total_docs,
                        affected_rate=float(aff_docs / total_docs * 100),
                        examples=examples,
                        suggestion=f"Enforce value validations to block negative entries in field '{fp}'."
                    ))

            # ZeroValue
            if not numeric_vals.empty and last_part in ("price", "total", "amount"):
                bad_mask = numeric_vals == 0
                if bad_mask.any():
                    bad_series = numeric_vals[bad_mask]
                    aff_docs = len(bad_series.index.get_level_values(0).unique())
                    examples = [mask_value(v) for v in bad_series.head(3)]
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="ZeroValue",
                        severity="MEDIUM",
                        affected_count=aff_docs,
                        total_count=total_docs,
                        affected_rate=float(aff_docs / total_docs * 100),
                        examples=examples,
                        suggestion=f"Verify business logic: field '{fp}' should not be zero."
                    ))

            # OutlierValue
            if not numeric_vals.empty and len(numeric_vals) >= 3:
                mean = numeric_vals.mean()
                std = numeric_vals.std()
                if std > 0:
                    bad_mask = (numeric_vals - mean).abs() > 3 * std
                    if bad_mask.any():
                        bad_series = numeric_vals[bad_mask]
                        aff_docs = len(bad_series.index.get_level_values(0).unique())
                        examples = [mask_value(v) for v in bad_series.head(3)]
                        findings.append(SemanticFinding(
                            field_path=fp,
                            rule_name="OutlierValue",
                            severity="INFO",
                            affected_count=aff_docs,
                            total_count=total_docs,
                            affected_rate=float(aff_docs / total_docs * 100),
                            examples=examples,
                            suggestion=f"Statistical outlier detected in '{fp}' (Mean: {mean:.2f}, StdDev: {std:.2f})."
                        ))

            # DATE RULES
            # Try to parse all string/object items as dates if fp matches date rules
            if last_part in ("date", "createdat", "birthdate", "inscription", "orderdate", "paymentdate"):
                # Parse all non-null values
                dates = series.map(parse_date_safely).dropna()
                if not dates.empty:
                    # FutureDate
                    now = datetime.datetime.now()
                    bad_future_mask = dates > now
                    if bad_future_mask.any():
                        bad_future = series[dates[bad_future_mask].index]
                        aff_docs = len(bad_future.index.get_level_values(0).unique())
                        examples = [mask_value(v) for v in bad_future.head(3)]
                        findings.append(SemanticFinding(
                            field_path=fp,
                            rule_name="FutureDate",
                            severity="CRITICAL",
                            affected_count=aff_docs,
                            total_count=total_docs,
                            affected_rate=float(aff_docs / total_docs * 100),
                            examples=examples,
                            suggestion=f"Fix timestamp generation logic; dates in '{fp}' cannot be in the future."
                        ))

                    # AncientDate
                    if last_part in ("orderdate", "createdat", "paymentdate"):
                        ancient_limit = datetime.datetime(2000, 1, 1)
                        bad_ancient_mask = dates < ancient_limit
                        if bad_ancient_mask.any():
                            bad_ancient = series[dates[bad_ancient_mask].index]
                            aff_docs = len(bad_ancient.index.get_level_values(0).unique())
                            examples = [mask_value(v) for v in bad_ancient.head(3)]
                            findings.append(SemanticFinding(
                                field_path=fp,
                                rule_name="AncientDate",
                                severity="MEDIUM",
                                affected_count=aff_docs,
                                total_count=total_docs,
                                affected_rate=float(aff_docs / total_docs * 100),
                                examples=examples,
                                suggestion=f"Date in '{fp}' is before year 2000, verify context accuracy."
                            ))

            # InvalidDateString
            if last_part in ("date", "createdat", "birthdate", "inscription", "orderdate", "paymentdate"):
                # Filter values that are string
                string_vals = series.map(lambda x: x if isinstance(x, str) else None).dropna()
                if not string_vals.empty:
                    invalid_mask = string_vals.map(parse_date_safely).isna()
                    if invalid_mask.any():
                        bad_strings = string_vals[invalid_mask]
                        aff_docs = len(bad_strings.index.get_level_values(0).unique())
                        examples = [mask_value(v) for v in bad_strings.head(3)]
                        findings.append(SemanticFinding(
                            field_path=fp,
                            rule_name="InvalidDateString",
                            severity="HIGH",
                            affected_count=aff_docs,
                            total_count=total_docs,
                            affected_rate=float(aff_docs / total_docs * 100),
                            examples=examples,
                            suggestion=f"Provide consistent ISO 8601 strings for date field '{fp}'."
                        ))

            # STRING / FORMAT RULES
            # MalformedEmail
            if last_part in ("email", "mail"):
                string_vals = series.map(lambda x: x if isinstance(x, str) else None).dropna()
                if not string_vals.empty:
                    email_re = re.compile(r'^[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}$')
                    bad_email_mask = string_vals.map(lambda e: bool(email_re.match(e)) is False)
                    if bad_email_mask.any():
                        bad_emails = string_vals[bad_email_mask]
                        aff_docs = len(bad_emails.index.get_level_values(0).unique())
                        examples = [mask_value(v) for v in bad_emails.head(3)]
                        findings.append(SemanticFinding(
                            field_path=fp,
                            rule_name="MalformedEmail",
                            severity="HIGH",
                            affected_count=aff_docs,
                            total_count=total_docs,
                            affected_rate=float(aff_docs / total_docs * 100),
                            examples=examples,
                            suggestion=f"Format field '{fp}' to strictly follow RFC 5322 structure."
                        ))

            # MalformedPhone
            if last_part in ("phone", "tel", "mobile", "telephone"):
                string_vals = series.map(lambda x: x if isinstance(x, str) else None).dropna()
                if not string_vals.empty:
                    def is_malformed_phone(p: str) -> bool:
                        stripped = re.sub(r'[\s+\-–()]', '', p)
                        return any(c.isalpha() for c in p) or len(stripped) < 8
                    bad_phone_mask = string_vals.map(is_malformed_phone)
                    if bad_phone_mask.any():
                        bad_phones = string_vals[bad_phone_mask]
                        aff_docs = len(bad_phones.index.get_level_values(0).unique())
                        examples = [mask_value(v) for v in bad_phones.head(3)]
                        findings.append(SemanticFinding(
                            field_path=fp,
                            rule_name="MalformedPhone",
                            severity="HIGH",
                            affected_count=aff_docs,
                            total_count=total_docs,
                            affected_rate=float(aff_docs / total_docs * 100),
                            examples=examples,
                            suggestion=f"Sanitize phone field '{fp}' to contain only digits and standard separators."
                        ))

            # EmptyString
            string_vals = series.map(lambda x: x if isinstance(x, str) else None).dropna()
            if not string_vals.empty:
                bad_empty_mask = string_vals.map(lambda s: not s.strip())
                if bad_empty_mask.any():
                    bad_empty = string_vals[bad_empty_mask]
                    aff_docs = len(bad_empty.index.get_level_values(0).unique())
                    examples = [mask_value(v) for v in bad_empty.head(3)]
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="EmptyString",
                        severity="INFO",
                        affected_count=aff_docs,
                        total_count=total_docs,
                        affected_rate=float(aff_docs / total_docs * 100),
                        examples=examples,
                        suggestion=f"Store null or remove empty space elements for field '{fp}'."
                    ))

                # SuspiciousDefault
                suspicious_defaults = {"test", "admin", "n/a", "null", "undefined", "todo", "fixme", "xxx"}
                bad_suspicious_mask = string_vals.map(lambda s: s.strip().lower() in suspicious_defaults)
                if bad_suspicious_mask.any():
                    bad_suspicious = string_vals[bad_suspicious_mask]
                    aff_docs = len(bad_suspicious.index.get_level_values(0).unique())
                    examples = [mask_value(v) for v in bad_suspicious.head(3)]
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="SuspiciousDefault",
                        severity="MEDIUM",
                        affected_count=aff_docs,
                        total_count=total_docs,
                        affected_rate=float(aff_docs / total_docs * 100),
                        examples=examples,
                        suggestion=f"Do not write placeholder values in field '{fp}'."
                    ))

                # TooLong
                bad_long_mask = string_vals.map(lambda s: len(s) > 500)
                if bad_long_mask.any():
                    bad_long = string_vals[bad_long_mask]
                    aff_docs = len(bad_long.index.get_level_values(0).unique())
                    examples = [mask_value(v) for v in bad_long.head(3)]
                    avg_len = string_vals.map(len).mean()
                    max_len = string_vals.map(len).max()
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="TooLong",
                        severity="LOW" if "comment" in fp or "descr" in fp else "MEDIUM",
                        affected_count=aff_docs,
                        total_count=total_docs,
                        affected_rate=float(aff_docs / total_docs * 100),
                        examples=examples,
                        suggestion=f"Limit '{fp}' length (Max observed: {max_len}, Avg: {avg_len:.0f})."
                    ))

            # BOOLEAN RULES
            # FakeBoolean
            is_expected_bool = last_part.startswith(("is", "has", "was")) or last_part in ("active", "enabled", "paid", "admin", "valid")
            if is_expected_bool:
                bad_fake_mask = series.map(lambda x: (isinstance(x, str) and x.strip().lower() in ("true", "false")) or (isinstance(x, (int, float)) and x in (0, 1) and not isinstance(x, bool)))
                if bad_fake_mask.any():
                    bad_fakes = series[bad_fake_mask]
                    aff_docs = len(bad_fakes.index.get_level_values(0).unique())
                    examples = [mask_value(v) for v in bad_fakes.head(3)]
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="FakeBoolean",
                        severity="MEDIUM",
                        affected_count=aff_docs,
                        total_count=total_docs,
                        affected_rate=float(aff_docs / total_docs * 100),
                        examples=examples,
                        suggestion=f"Cast phone/string boolean values (e.g. 0/1, 'true') to valid bool in field '{fp}'."
                    ))

            # ID / REFERENCE RULES
            if last_part.endswith("id") or last_part.endswith("code"):
                # DuplicateID
                valid_ids = series.dropna()
                if not valid_ids.empty:
                    # check dupes
                    dupes = valid_ids[valid_ids.duplicated()]
                    if not dupes.empty:
                        aff_docs = len(valid_ids[valid_ids.isin(dupes)].index.get_level_values(0).unique())
                        examples = [mask_value(v) for v in dupes.head(3)]
                        findings.append(SemanticFinding(
                            field_path=fp,
                            rule_name="DuplicateID",
                            severity="CRITICAL",
                            affected_count=aff_docs,
                            total_count=total_docs,
                            affected_rate=float(aff_docs / total_docs * 100),
                            examples=examples,
                            suggestion=f"Enforce unique constraints on index key '{fp}'."
                        ))
                
                # NullID (where flat values are None or empty string)
                # For document level, check how many docs lack this key or have it empty
                null_id_count = 0
                null_examples = []
                for idx, doc in enumerate(self.documents):
                    val = doc.get(fp)  # simple nested lookup
                    if val is None or (isinstance(val, str) and not val.strip()):
                        null_id_count += 1
                        if len(null_examples) < 3:
                            null_examples.append("None" if val is None else '""')
                if null_id_count > 0:
                    findings.append(SemanticFinding(
                        field_path=fp,
                        rule_name="NullID",
                        severity="CRITICAL",
                        affected_count=null_id_count,
                        total_count=total_docs,
                        affected_rate=float(null_id_count / total_docs * 100),
                        examples=null_examples,
                        suggestion=f"Constraint check failed: identifier field '{fp}' cannot be empty."
                    ))

        # CROSS-FIELD RULES (processed document by document)
        age_birth_bad = 0
        age_birth_ex = []
        paid_amount_bad = 0
        paid_amount_ex = []
        status_date_bad = 0
        status_date_ex = []

        current_year = datetime.datetime.now().year

        for doc in self.documents:
            flat = flatten_dict(doc)
            
            # 1. AgeVsBirthdate
            # Look for keys ending in 'age' and 'birthdate'/'birth_date'
            age_key = next((k for k in flat if k.split('.')[-1].lower() == 'age'), None)
            birth_key = next((k for k in flat if k.split('.')[-1].lower() in ('birthdate', 'birth_date')), None)
            if age_key and birth_key:
                age_val = flat[age_key]
                birth_val = flat[birth_key]
                parsed_birth = parse_date_safely(birth_val)
                if parsed_birth and isinstance(age_val, (int, float)):
                    diff_year = current_year - parsed_birth.year
                    if abs(age_val - diff_year) > 1:
                        age_birth_bad += 1
                        if len(age_birth_ex) < 3:
                            age_birth_ex.append(f"Age: {age_val}, Birth: {birth_val}")
            
            # 2. PaidVsAmount
            # Look for keys ending in 'paid' and 'total'/'amount'/'price'
            paid_key = next((k for k in flat if k.split('.')[-1].lower() == 'paid'), None)
            total_key = next((k for k in flat if k.split('.')[-1].lower() in ('total', 'amount', 'price')), None)
            if paid_key and total_key:
                paid_val = flat[paid_key]
                total_val = flat[total_key]
                # is paid True/truthy
                is_paid = paid_val is True or (isinstance(paid_val, str) and paid_val.lower() == 'true')
                try:
                    num_total = float(total_val) if total_val is not None else 0.0
                except ValueError:
                    num_total = 0.0
                if is_paid and num_total == 0.0:
                    paid_amount_bad += 1
                    if len(paid_amount_ex) < 3:
                        paid_amount_ex.append(f"Paid: {paid_val}, Total: {total_val}")
                        
            # 3. StatusVsDate
            # Look for keys ending in 'status' and 'deliverydate'/'delivery_date'/'deliveredat'/'delivered_at'
            status_key = next((k for k in flat if k.split('.')[-1].lower() == 'status'), None)
            delivery_key = next((k for k in flat if k.split('.')[-1].lower() in ('deliverydate', 'delivery_date', 'deliveredat', 'delivered_at')), None)
            if status_key:
                status_val = str(flat[status_key]).strip().lower()
                if status_val == 'delivered':
                    has_delivery_date = False
                    if delivery_key and flat[delivery_key] is not None:
                        has_delivery_date = True
                    if not has_delivery_date:
                        status_date_bad += 1
                        if len(status_date_ex) < 3:
                            status_date_ex.append(f"Status: delivered, Date: None")

        # InconsistentTotal
        inconsistent_total_bad = 0
        inconsistent_total_ex = []
        for doc in self.documents:
            # Check items array and total field
            total_val = doc.get("total")
            items_list = doc.get("items")
            if total_val is not None and isinstance(items_list, list) and len(items_list) > 0:
                expected_total = 0.0
                has_items_data = False
                for item in items_list:
                    if isinstance(item, dict):
                        price = item.get("price")
                        qty = item.get("qty") or item.get("quantity") or 1.0
                        if price is not None:
                            try:
                                expected_total += float(price) * float(qty)
                                has_items_data = True
                            except (ValueError, TypeError):
                                pass
                if has_items_data:
                    try:
                        actual_total = float(total_val)
                        if actual_total > 0.0:
                            diff_rate = abs(actual_total - expected_total) / actual_total
                            if diff_rate > 0.01:
                                inconsistent_total_bad += 1
                                if len(inconsistent_total_ex) < 3:
                                    inconsistent_total_ex.append(f"Total: {actual_total}, Expected: {expected_total:.2f}")
                    except (ValueError, TypeError):
                        pass

        # Append Cross-field / InconsistentTotal findings
        if age_birth_bad > 0:
            findings.append(SemanticFinding(
                field_path="age, birth_date",
                rule_name="AgeVsBirthdate",
                severity="HIGH",
                affected_count=age_birth_bad,
                total_count=total_docs,
                affected_rate=float(age_birth_bad / total_docs * 100),
                examples=age_birth_ex,
                suggestion="Validate and align age values with birth_date birth year."
            ))
        if paid_amount_bad > 0:
            findings.append(SemanticFinding(
                field_path="paid, total",
                rule_name="PaidVsAmount",
                severity="CRITICAL",
                affected_count=paid_amount_bad,
                total_count=total_docs,
                affected_rate=float(paid_amount_bad / total_docs * 100),
                examples=paid_amount_ex,
                suggestion="Verify transaction records: paid flag should match total transaction price > 0."
            ))
        if status_date_bad > 0:
            findings.append(SemanticFinding(
                field_path="status, delivery_date",
                rule_name="StatusVsDate",
                severity="HIGH",
                affected_count=status_date_bad,
                total_count=total_docs,
                affected_rate=float(status_date_bad / total_docs * 100),
                examples=status_date_ex,
                suggestion="Add delivered timestamps to track delivered packages."
            ))
        if inconsistent_total_bad > 0:
            findings.append(SemanticFinding(
                field_path="items, total",
                rule_name="InconsistentTotal",
                severity="HIGH",
                affected_count=inconsistent_total_bad,
                total_count=total_docs,
                affected_rate=float(inconsistent_total_bad / total_docs * 100),
                examples=inconsistent_total_ex,
                suggestion="Align document total field with the aggregate sum of item prices and quantities."
            ))

        # Compute Quality Score & Grade
        quality_score = self.compute_quality_score(findings)
        grade = self._get_grade(quality_score)

        return SemanticReport(
            collection_name=self.collection_name,
            total_documents=total_docs,
            total_fields_analyzed=len(field_profiles),
            quality_score=quality_score,
            grade=grade,
            findings=findings,
            field_profiles=field_profiles,
            generated_at=datetime.datetime.now()
        )

# ── EXPORT FUNCTIONS ──────────────────────────────────────────

def export_report_json(report: SemanticReport) -> str:
    """Format semantic report data to JSON string representation."""
    report_dict = {
        "collection_name": report.collection_name,
        "total_documents": report.total_documents,
        "total_fields_analyzed": report.total_fields_analyzed,
        "quality_score": report.quality_score,
        "grade": report.grade,
        "findings": [asdict(f) for f in report.findings],
        "field_profiles": {k: asdict(v) for k, v in report.field_profiles.items()},
        "generated_at": report.generated_at.isoformat()
    }
    return json.dumps(report_dict, indent=2, ensure_ascii=False)

def export_report_csv(report: SemanticReport) -> pd.DataFrame:
    """Format findings from semantic report to a Pandas DataFrame."""
    rows = []
    for f in report.findings:
        rows.append({
            "field_path": f.field_path,
            "rule_name": f.rule_name,
            "severity": f.severity,
            "affected_count": f.affected_count,
            "total_count": f.total_count,
            "affected_rate": f.affected_rate,
            "examples": ", ".join(f.examples),
            "suggestion": f.suggestion
        })
    return pd.DataFrame(rows)

def generate_pdf_report(report: SemanticReport) -> bytes:
    """
    Generate professional data quality PDF report using ReportLab.
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
        title=f"Data Quality Report - {report.collection_name}",
        author="NoSQL Schema Inspector",
        creator="NoSQL Schema Inspector"
    )

    def draw_footer(canvas, d):
        canvas.saveState()
        canvas.setFont("Times-Roman", 10)
        from reportlab.lib import colors
        canvas.setFillColor(colors.gray)
        page_num = canvas.getPageNumber()
        canvas.drawCentredString(
            d.pagesize[0] / 2, 1.2 * 28.35,
            f"NoSQL Schema Inspector  |  Data Quality Report  |  Page {page_num}"
        )
        canvas.restoreState()

    styles = getSampleStyleSheet()

    # Define custom styles
    sty_title = ParagraphStyle(
        "DocTitle", parent=styles["Title"],
        fontSize=20, textColor=colors.black,
        spaceAfter=12, fontName="Times-Bold"
    )
    sty_subtitle = ParagraphStyle(
        "DocSubtitle", fontSize=10, textColor=colors.gray,
        spaceAfter=6, fontName="Times-Roman"
    )
    sty_section = ParagraphStyle(
        "DocSection", parent=styles["Heading2"],
        fontSize=14, textColor=colors.black,
        spaceBefore=12, spaceAfter=6, fontName="Times-Bold"
    )
    sty_body = ParagraphStyle(
        "DocBody", parent=styles["Normal"], fontName="Times-Roman"
    )
    sty_table_header = ParagraphStyle(
        "THeader", textColor=colors.black, fontSize=10, fontName="Times-Bold"
    )
    sty_table_cell = ParagraphStyle(
        "TCell", fontSize=9, leading=11, fontName="Times-Roman"
    )

    story = []

    # Title Banner Header
    header_data = [[
        Paragraph("<b>NoSQL Schema Inspector</b>", ParagraphStyle("HdrL", fontSize=12, textColor=colors.black, fontName="Times-Bold")),
        Paragraph("<b>Data Quality Suite</b>", ParagraphStyle("HdrR", fontSize=10, textColor=colors.black, alignment=2, fontName="Times-Roman"))
    ]]
    header = Table(header_data, colWidths=[11 * cm, 6 * cm])
    header.setStyle(TableStyle([
        ("LINEBOTTOM", (0, 0), (-1, -1), 1.5, colors.black),
        ("PADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.4 * cm))

    # Report meta
    now_str = report.generated_at.strftime("%Y-%m-%d %H:%M:%S")
    story.append(Paragraph("Data Quality & Semantic Profiling Report", sty_title))
    story.append(Paragraph(
        f"Collection: <b>{report.collection_name}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Generated At: <b>{now_str}</b> &nbsp;&nbsp;|&nbsp;&nbsp; "
        f"Total Documents: <b>{report.total_documents}</b>",
        sty_subtitle
    ))
    story.append(Spacer(1, 0.5 * cm))

    # 1. Score block
    score = report.quality_score
    score_color = colors.black
    
    score_data = [[
        Paragraph(f"<font size='32' face='Times-Bold'>{score:.1f}</font><font size='14' color='gray' face='Times-Roman'> / 100</font>", ParagraphStyle("ScoreVal", alignment=1, textColor=score_color)),
        Paragraph(f"<font size='16' face='Times-Bold'>Grade {report.grade}</font><br/><br/><font size='10' color='gray' face='Times-Roman'>Semantic profile indicates data quality stands at {score:.1f}% with grade {report.grade}. Details of quality checks are cataloged below.</font>", ParagraphStyle("ScoreDesc", alignment=0))
    ]]
    score_table = Table(score_data, colWidths=[5 * cm, 12 * cm])
    score_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
        ("PADDING", (0, 0), (-1, -1), 15),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(Paragraph("1. Data Quality Score", sty_section))
    story.append(score_table)
    story.append(Spacer(1, 0.4 * cm))

    # 2. Findings
    story.append(Paragraph("2. Quality Violations & Findings", sty_section))
    if not report.findings:
        story.append(Paragraph("No quality anomalies detected. Your collection has clean semantic structures.", sty_body))
    else:
        findings_table_data = [
            [
                Paragraph("Field Path", sty_table_header),
                Paragraph("Rule Viol", sty_table_header),
                Paragraph("Sev", sty_table_header),
                Paragraph("Rate %", sty_table_header),
                Paragraph("Examples", sty_table_header),
                Paragraph("Actionable Suggestion", sty_table_header),
            ]
        ]
        
        SEV_COLORS = {
            "CRITICAL": colors.black,
            "HIGH": colors.black,
            "MEDIUM": colors.black,
            "INFO": colors.black,
        }

        for f in report.findings:
            findings_table_data.append([
                Paragraph(f.field_path, sty_table_cell),
                Paragraph(f.rule_name, sty_table_cell),
                Paragraph(f"<b>{f.severity}</b>", sty_table_cell),
                Paragraph(f"{f.affected_rate:.1f}% ({f.affected_count})", sty_table_cell),
                Paragraph(", ".join(f.examples), sty_table_cell),
                Paragraph(f.suggestion, sty_table_cell),
            ])
            
        t_find = Table(findings_table_data, colWidths=[2.5 * cm, 2.5 * cm, 2 * cm, 2.2 * cm, 3.8 * cm, 4 * cm])
        t_find.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
            ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.lightgrey),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 4),
        ]))
        story.append(t_find)
        
    story.append(Spacer(1, 0.4 * cm))

    # 3. Field Profiles
    story.append(Paragraph("3. Field Semantics & Statistics Profiles", sty_section))
    profiles_table_data = [
        [
            Paragraph("Field Path", sty_table_header),
            Paragraph("Dominant Type", sty_table_header),
            Paragraph("Null Rate", sty_table_header),
            Paragraph("Unique Rate", sty_table_header),
            Paragraph("Min / Max / Avg", sty_table_header),
            Paragraph("Semantic Inferred", sty_table_header),
            Paragraph("Top Values", sty_table_header),
        ]
    ]
    
    for path, p in sorted(report.field_profiles.items()):
        min_max_avg = "-"
        if p.min_val is not None or p.max_val is not None:
            avg_str = f"{p.avg_val:.2f}" if p.avg_val is not None else "-"
            min_max_avg = f"Min: {p.min_val}<br/>Max: {p.max_val}<br/>Avg: {avg_str}"
            
        profiles_table_data.append([
            Paragraph(p.field_path, sty_table_cell),
            Paragraph(p.dominant_type, sty_table_cell),
            Paragraph(f"{p.null_rate * 100:.1f}%", sty_table_cell),
            Paragraph(f"{p.unique_rate * 100:.1f}%", sty_table_cell),
            Paragraph(min_max_avg, sty_table_cell),
            Paragraph(p.semantic_type, sty_table_cell),
            Paragraph(", ".join(str(v) for v in p.top_values[:3]), sty_table_cell),
        ])
        
    t_prof = Table(profiles_table_data, colWidths=[2.8 * cm, 2.2 * cm, 1.8 * cm, 1.8 * cm, 3.2 * cm, 2.7 * cm, 2.5 * cm])
    t_prof.setStyle(TableStyle([
        ("LINEBELOW", (0, 0), (-1, 0), 1, colors.black),
        ("LINEBELOW", (0, 1), (-1, -1), 0.5, colors.lightgrey),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t_prof)

    doc.build(story, onFirstPage=draw_footer, onLaterPages=draw_footer)
    buffer.seek(0)
    return buffer.read()
