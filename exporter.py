"""
exporter.py
Export du schéma et des rapports de sécurité en JSON, CSV et PDF.
"""
import json
import io
import csv
import datetime
from datetime import date


class SafeJSONEncoder(json.JSONEncoder):
    """Encoder JSON robuste : gère datetime, ObjectId, bytes, etc."""
    def default(self, obj):
        try:
            from bson import ObjectId
            if isinstance(obj, ObjectId):
                return str(obj)
        except ImportError:
            pass
        if isinstance(obj, (datetime.datetime, date)):
            return obj.isoformat()
        if isinstance(obj, bytes):
            return obj.decode("utf-8", errors="replace")
        return str(obj)



# ── JSON ─────────────────────────────────────────────────────

def export_security_report_json(audit_result: dict, collection_name: str = "collection") -> str:
    """Retourne le rapport d'audit au format JSON (str)."""
    report = {
        "collection": collection_name,
        "generated_at": datetime.datetime.now().isoformat(),
        "score": audit_result["score"],
        "summary": audit_result["summary"],
        "findings": audit_result["findings"]
    }
    return json.dumps(report, indent=2, ensure_ascii=False, cls=SafeJSONEncoder)


# ── CSV ──────────────────────────────────────────────────────

def export_security_report_csv(audit_result: dict) -> bytes:
    """Retourne le rapport d'audit au format CSV (bytes)."""
    output = io.StringIO()
    fieldnames = ["field", "rule", "severity", "message", "affected_docs", "sample"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for finding in audit_result["findings"]:
        writer.writerow({k: finding.get(k, "") for k in fieldnames})
    return output.getvalue().encode("utf-8")


# ── PDF ──────────────────────────────────────────────────────

APP_NAME    = "NoSQL Schema Inspector"
APP_VERSION = "2.0"
APP_AUTHOR  = "NoSQL Schema Inspector Team"

# Recommandations par règle
_RECOMMENDATIONS = {
    "English": {
        "PLAINTEXT_PASSWORD":      "Hash passwords with bcrypt or Argon2 before storage.",
        "WEAK_HASH_MD5":           "Replace MD5 with bcrypt ($2b$) or Argon2 for hashing.",
        "PII_EXPOSED":             "Encrypt personal data (AES-256) or use a secure vault.",
        "TOKEN_EXPOSED":           "Store tokens in a secret manager, not in the database.",
        "NOSQL_INJECTION_RISK":    "Validate and sanitize inputs before database insertion.",
        "TYPE_JUGGLING":           "Enforce a strict schema (JSON Schema / Mongoose) for these fields.",
        "CARD_DATA_EXPOSED":       "Never store credit card data in plaintext (PCI-DSS compliance).",
        "MISSING_TIMESTAMPS":      "Add createdAt / updatedAt for traceability.",
        "ROLE_FIELD_EXPOSED":      "Protect role fields with server-side access control.",
        "UNSTRUCTURED_PERMISSIONS":"Structure permissions as an array/object, not a free-form string.",
    },
    "Français": {
        "PLAINTEXT_PASSWORD":      "Hachez les mots de passe avec bcrypt ou Argon2 avant stockage.",
        "WEAK_HASH_MD5":           "Remplacez MD5 par bcrypt ($2b$) ou Argon2 pour le hachage.",
        "PII_EXPOSED":             "Chiffrez les donnees personnelles (AES-256) ou utilisez un vault.",
        "TOKEN_EXPOSED":           "Stockez les tokens dans un secret manager, pas en base.",
        "NOSQL_INJECTION_RISK":    "Validez et assainissez les entrees avant insertion en base.",
        "TYPE_JUGGLING":           "Imposez un schema strict (JSON Schema / Mongoose) pour ces champs.",
        "CARD_DATA_EXPOSED":       "Ne stockez jamais de donnees bancaires en clair (norme PCI-DSS).",
        "MISSING_TIMESTAMPS":      "Ajoutez createdAt / updatedAt pour la tracabilite.",
        "ROLE_FIELD_EXPOSED":      "Protegez les champs de role avec un controle d'acces cote serveur.",
        "UNSTRUCTURED_PERMISSIONS":"Structurez les permissions en array/object, pas en string libre.",
    }
}

PDF_TEXTS = {
    "English": {
        "report_title": "Security Audit Report",
        "meta_subtitle": "Collection: <b>{collection_name}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Date: <b>{now_str}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Tool: <b>{app_name} v{app_version}</b>",
        "sec_score_title": "1. Security Score",
        "good_score_desc": "No critical vulnerability detected.",
        "bad_score_desc": "Vulnerabilities detected. See details below.",
        "summary_title": "2. Summary by Severity",
        "th_severity": "Severity",
        "th_findings": "Findings",
        "th_impact": "Impact",
        "impact_critical": "Immediate exploitation possible",
        "impact_high": "Significant risk",
        "impact_medium": "Recommended improvement",
        "impact_info": "Best practice",
        "details_title": "3. Vulnerability Details",
        "compliant_collection": "No vulnerabilities detected. The collection is compliant.",
        "label_affected_docs": "Affected documents:",
        "label_sample_masked": "Example (masked):",
        "label_reco": "Recommendation:",
        "meta_title": "4. Report Information",
        "th_property": "Property",
        "th_value": "Value",
        "prop_app": "Application",
        "prop_coll": "Analyzed collection",
        "prop_date": "Generation date",
        "prop_findings": "Number of findings",
        "prop_score": "Security score",
        "pdf_footer": "{app_name} v{app_version}  |  Security Report  |  Page {page_num}",
        "sev_critical": "CRITICAL",
        "sev_high": "HIGH",
        "sev_medium": "MEDIUM",
        "sev_info": "INFO",
        "label_good": "GOOD",
        "label_medium": "MEDIUM",
        "label_danger": "DANGER"
    },
    "Français": {
        "report_title": "Rapport d'Audit de Securite",
        "meta_subtitle": "Collection : <b>{collection_name}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Date : <b>{now_str}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Outil : <b>{app_name} v{app_version}</b>",
        "sec_score_title": "1. Score de Securite",
        "good_score_desc": "Aucune vulnerabilite critique detectee.",
        "bad_score_desc": "Des vulnerabilites ont ete detectees. Consultez le detail ci-dessous.",
        "summary_title": "2. Resume par Severite",
        "th_severity": "Severite",
        "th_findings": "Findings",
        "th_impact": "Impact",
        "impact_critical": "Exploitation immediate possible",
        "impact_high": "Risque significatif",
        "impact_medium": "Amelioration recommandee",
        "impact_info": "Bonne pratique",
        "details_title": "3. Detail des Vulnerabilites",
        "compliant_collection": "Aucune vulnerabilite detectee. La collection est conforme.",
        "label_affected_docs": "Documents touches :",
        "label_sample_masked": "Exemple (masque) :",
        "label_reco": "Recommandation :",
        "meta_title": "4. Informations du Rapport",
        "th_property": "Propriete",
        "th_value": "Valeur",
        "prop_app": "Application",
        "prop_coll": "Collection analysee",
        "prop_date": "Date de generation",
        "prop_findings": "Nombre de findings",
        "prop_score": "Score de securite",
        "pdf_footer": "{app_name} v{app_version}  |  Rapport de securite  |  Page {page_num}",
        "sev_critical": "CRITIQUE",
        "sev_high": "ELEVE",
        "sev_medium": "MOYEN",
        "sev_info": "INFO",
        "label_good": "BON",
        "label_medium": "MOYEN",
        "label_danger": "DANGER"
    }
}


def _build_footer(canvas, doc):
    """Pied de page avec numero de page et nom de l'application."""
    canvas.saveState()
    canvas.setFont("Times-Roman", 10)
    from reportlab.lib import colors
    canvas.setFillColor(colors.gray)
    page_num = canvas.getPageNumber()
    lang = getattr(doc, "lang", "English")
    footer_text = PDF_TEXTS.get(lang, PDF_TEXTS["English"])["pdf_footer"].format(
        app_name=APP_NAME, app_version=APP_VERSION, page_num=page_num
    )
    canvas.drawCentredString(
        doc.pagesize[0] / 2, 1.2 * 28.35,
        footer_text
    )
    canvas.restoreState()


def export_security_report_pdf(audit_result: dict, collection_name: str = "collection", lang: str = "English") -> bytes:
    """
    Retourne le rapport d'audit au format PDF (bytes).
    Necessite : pip install reportlab
    """
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
    )

    t_dict = PDF_TEXTS.get(lang, PDF_TEXTS["English"])
    now_str = datetime.datetime.now().strftime("%d/%m/%Y a %H:%M")

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2.5 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
        title=f"Rapport Securite - {collection_name}",
        author=APP_AUTHOR,
        subject=f"Audit de vulnerabilites NoSQL pour la collection {collection_name}",
        creator=f"{APP_NAME} v{APP_VERSION}",
        keywords=[APP_NAME, "securite", "audit", "NoSQL", collection_name],
    )
    doc.lang = lang
    styles = getSampleStyleSheet()

    # ── Styles personnalises ──
    sty_title = ParagraphStyle(
        "RptTitle", parent=styles["Title"],
        fontSize=20, textColor=colors.black,
        spaceAfter=14, fontName="Times-Bold"
    )
    sty_subtitle = ParagraphStyle(
        "RptSubtitle", fontSize=10, textColor=colors.gray,
        spaceAfter=6, fontName="Times-Roman"
    )
    sty_section = ParagraphStyle(
        "RptSection", parent=styles["Heading2"],
        fontSize=15, textColor=colors.black,
        spaceBefore=14, spaceAfter=6, fontName="Times-Bold"
    )
    sty_body = ParagraphStyle(
        "RptBody", parent=styles["Normal"],
        fontName="Times-Roman"
    )

    SEV_COLORS = {
        "CRITICAL": colors.black,
        "HIGH":     colors.black,
        "MEDIUM":   colors.black,
        "INFO":     colors.black,
    }
    SEV_LABELS = {
        "CRITICAL": t_dict["sev_critical"],
        "HIGH":     t_dict["sev_high"],
        "MEDIUM":   t_dict["sev_medium"],
        "INFO":     t_dict["sev_info"],
    }

    story = []

    # ════════════════════════════════════════════════════════════
    #  EN-TETE
    # ════════════════════════════════════════════════════════════
    header_data = [[
        Paragraph(f"<b>{APP_NAME}</b>", ParagraphStyle(
            "HdrLeft", fontSize=13, textColor=colors.black, fontName="Times-Bold"
        )),
        Paragraph(f"<b>v{APP_VERSION}</b>", ParagraphStyle(
            "HdrRight", fontSize=11, textColor=colors.black, alignment=2, fontName="Times-Roman"
        ))
    ]]
    header = Table(header_data, colWidths=[12 * cm, 5 * cm])
    header.setStyle(TableStyle([
        ("LINEBOTTOM", (0, 0), (-1, -1), 1.5, colors.black),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(t_dict["report_title"], sty_title))
    story.append(Paragraph(
        t_dict["meta_subtitle"].format(
            collection_name=collection_name,
            now_str=now_str,
            app_name=APP_NAME,
            app_version=APP_VERSION
        ),
        sty_subtitle
    ))
    story.append(Spacer(1, 0.5 * cm))

    # ════════════════════════════════════════════════════════════
    #  1. SCORE DE SECURITE
    # ════════════════════════════════════════════════════════════
    score = audit_result["score"]
    score_color = colors.black

    score_label = (
        t_dict["label_good"] if score >= 70
        else t_dict["label_medium"] if score >= 40
        else t_dict["label_danger"]
    )
    score_msg = t_dict["good_score_desc"] if score >= 70 else t_dict["bad_score_desc"]

    story.append(Paragraph(t_dict["sec_score_title"], sty_section))

    score_data = [[
        Paragraph(
            f"<font size='28' face='Times-Bold'>{score}</font>"
            f"<font size='14' color='gray' face='Times-Roman'> / 100</font>",
            ParagraphStyle("ScoreNum", alignment=1, textColor=score_color)
        ),
        Paragraph(
            f"<font size='16' face='Times-Bold'>[{score_label}]</font><br/><br/>"
            f"<font size='10' color='gray' face='Times-Roman'>{score_msg}</font>",
            ParagraphStyle("ScoreDesc", alignment=0, textColor=score_color)
        )
    ]]
    score_table = Table(score_data, colWidths=[5 * cm, 12 * cm])
    score_table.setStyle(TableStyle([
        ("BOX", (0, 0), (-1, -1), 0.5, colors.gray),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 0.5 * cm))

    # ════════════════════════════════════════════════════════════
    #  2. RESUME PAR SEVERITE
    # ════════════════════════════════════════════════════════════
    summary = audit_result["summary"]
    story.append(Paragraph(t_dict["summary_title"], sty_section))

    summary_data = [
        [
            Paragraph(f"<b>{t_dict['th_severity']}</b>", ParagraphStyle("TH", textColor=colors.black, fontName="Times-Bold", fontSize=11)),
            Paragraph(f"<b>{t_dict['th_findings']}</b>", ParagraphStyle("TH2", textColor=colors.black, fontName="Times-Bold", fontSize=11, alignment=1)),
            Paragraph(f"<b>{t_dict['th_impact']}</b>", ParagraphStyle("TH3", textColor=colors.black, fontName="Times-Bold", fontSize=11)),
        ],
        [t_dict["sev_critical"], str(summary.get("CRITICAL", 0)), t_dict["impact_critical"]],
        [t_dict["sev_high"],     str(summary.get("HIGH",     0)), t_dict["impact_high"]],
        [t_dict["sev_medium"],   str(summary.get("MEDIUM",   0)), t_dict["impact_medium"]],
        [t_dict["sev_info"],     str(summary.get("INFO",     0)), t_dict["impact_info"]],
    ]

    t = Table(summary_data, colWidths=[5 * cm, 4 * cm, 8 * cm])
    style_cmds = [
        ("LINEBELOW",   (0, 0), (-1, 0), 1, colors.black),
        ("FONTNAME",    (0, 1), (-1, -1), "Times-Roman"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("ALIGN",       (1, 0), (1, -1), "CENTER"),
        ("TOPPADDING",  (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]
    t.setStyle(TableStyle(style_cmds))
    story.append(t)
    story.append(Spacer(1, 0.6 * cm))

    # ════════════════════════════════════════════════════════════
    #  3. DETAIL DES VULNERABILITES
    # ════════════════════════════════════════════════════════════
    findings = audit_result["findings"]

    story.append(Paragraph(t_dict["details_title"], sty_section))

    if not findings:
        story.append(Paragraph(
            t_dict["compliant_collection"],
            sty_body
        ))
    else:
        sev_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "INFO": 3}
        sorted_findings = sorted(findings, key=lambda x: sev_order.get(x["severity"], 99))

        for i, finding in enumerate(sorted_findings, 1):
            sev = finding.get("severity", "INFO")
            sev_color = SEV_COLORS.get(sev, colors.grey)
            sev_label = SEV_LABELS.get(sev, sev)

            # Titre numerote
            finding_title = ParagraphStyle(
                f"FT{i}", fontSize=11, textColor=colors.black,
                fontName="Times-Bold", spaceBefore=8, spaceAfter=2
            )
            story.append(Paragraph(
                f"3.{i}  [{sev_label}]  {finding['rule']}"
                f"  -  champ : <b>{finding['field']}</b>",
                finding_title
            ))

            # Description
            story.append(Paragraph(finding["message"], sty_body))

            # Details en tableau compact
            detail_data = [[
                Paragraph(f"<b>{t_dict['label_affected_docs']}</b> {finding['affected_docs']}", sty_body),
                Paragraph(f"<b>{t_dict['label_sample_masked']}</b> <font face='Courier'>{finding['sample']}</font>", sty_body),
            ]]
            dt = Table(detail_data, colWidths=[8.5 * cm, 8.5 * cm])
            dt.setStyle(TableStyle([
                ("LINEABOVE", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("LINEBELOW", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(dt)

            # Recommandation
            reco = _RECOMMENDATIONS.get(lang, _RECOMMENDATIONS["English"]).get(finding["rule"], "")
            if reco:
                reco_style = ParagraphStyle(
                    f"Reco{i}", fontSize=10, textColor=colors.black,
                    fontName="Times-Italic", spaceBefore=4, spaceAfter=4
                )
                story.append(Paragraph(f"{t_dict['label_reco']} {reco}", reco_style))

            story.append(Spacer(1, 0.4 * cm))

    # ════════════════════════════════════════════════════════════
    #  4. INFORMATIONS DU RAPPORT
    # ════════════════════════════════════════════════════════════
    story.append(Spacer(1, 0.8 * cm))
    story.append(Paragraph(t_dict["meta_title"], sty_section))

    meta_data = [
        [Paragraph(f"<b>{t_dict['th_property']}</b>", ParagraphStyle("THP", textColor=colors.black, fontName="Times-Bold")), 
         Paragraph(f"<b>{t_dict['th_value']}</b>", ParagraphStyle("THV", textColor=colors.black, fontName="Times-Bold"))],
        [t_dict["prop_app"], f"{APP_NAME} v{APP_VERSION}"],
        [t_dict["prop_coll"], collection_name],
        [t_dict["prop_date"], now_str],
        [t_dict["prop_findings"], str(len(findings))],
        [t_dict["prop_score"], f"{score}/100 ({score_label})"],
    ]
    mt = Table(meta_data, colWidths=[6 * cm, 11 * cm])
    mt.setStyle(TableStyle([
        ("LINEBELOW",   (0, 0), (-1, 0), 1, colors.black),
        ("FONTNAME",    (0, 1), (-1, -1), "Times-Roman"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("LINEBELOW",   (0, 1), (-1, -1), 0.5, colors.lightgrey),
        ("TOPPADDING",  (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(mt)

    # ── Build avec footer ──
    doc.build(story, onFirstPage=_build_footer, onLaterPages=_build_footer)
    buffer.seek(0)
    return buffer.read()

