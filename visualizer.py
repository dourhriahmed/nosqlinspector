import plotly.graph_objects as go
from i18n import get_text

def build_tree_figure(schema, collection_name="collection"):
    labels = [f"<b>{collection_name}</b>"]
    parents = [""]
    values = [100]
    colors = ["#1e3a5f"]
    texts = [get_text("root_label")]

    # Regrouper les champs par niveau
    top_fields = {}
    nested = {}

    for field, info in schema.items():
        parts = field.split(".")
        if len(parts) == 1:
            top_fields[field] = info
        else:
            parent = ".".join(parts[:-1])
            if parent not in nested:
                nested[parent] = {}
            nested[parent][field] = info

    def get_color(presence, types):
        type_keys = list(types.keys())
        if len(type_keys) > 1:
            return "#f59e0b"   # orange = type mixte
        if presence == 100:
            return "#10b981"   # vert = obligatoire
        elif presence >= 50:
            return "#3b82f6"   # bleu = fréquent
        else:
            return "#6b7280"   # gris = rare

    def get_icon(types):
        t = list(types.keys())[0] if types else "unknown"
        icons = {
            "string": "[str]",
            "integer": "[int]",
            "float": "[float]",
            "boolean": "[bool]",
            "object": "[obj]",
            "array": "[arr]",
            "null": "[null]"
        }
        return icons.get(t, "")

    # Ajouter les champs de premier niveau
    for field, info in sorted(top_fields.items()):
        presence = info["presence"]
        types = info["types"]
        icon = get_icon(types)
        types_str = ", ".join(types.keys())
        label = f"<b>{field}</b>"

        labels.append(label)
        parents.append(f"<b>{collection_name}</b>")
        values.append(max(presence, 10))
        colors.append(get_color(presence, types))
        texts.append(f"{icon}  {types_str} | {presence}%")

    # Ajouter les champs imbriqués
    for field, info in sorted(schema.items()):
        parts = field.split(".")
        if len(parts) < 2:
            continue

        presence = info["presence"]
        types = info["types"]
        icon = get_icon(types)
        types_str = ", ".join(types.keys())

        parent_field = ".".join(parts[:-1])
        parent_label = f"<b>{parent_field}</b>" if parent_field in top_fields else f"<b>{parts[-2]}</b>"

        label = f"<b>{parts[-1]}</b>"
        if label in labels:
            label = f"<b>{field}</b>"

        labels.append(label)
        parents.append(parent_label)
        values.append(max(presence, 10))
        colors.append(get_color(presence, types))
        texts.append(f"{icon}  {types_str} | {presence}%")

    fig = go.Figure(go.Treemap(
        labels=labels,
        parents=parents,
        values=values,
        text=texts,
        textinfo="label+text",
        textposition="middle center",
        hovertemplate="<b>%{label}</b><br>%{text}<extra></extra>",
        marker=dict(
            colors=colors,
            line=dict(width=2, color="#ffffff")
        ),
        pathbar=dict(visible=True),
        root_color="#ffffff"
    ))

    fig.update_layout(
        margin=dict(t=30, l=10, r=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(color="#334155", size=15, family="monospace"),
        height=600
    )

    return fig


def build_security_gauge(score: int) -> go.Figure:
    """
    Jauge arc Plotly pour le score de sécurité (0–100).
    Rouge → Orange → Vert selon le score.
    """
    if score >= 70:
        bar_color = "#10b981"   # vert
        label     = get_text("score_good")
    elif score >= 40:
        bar_color = "#f59e0b"   # orange
        label     = get_text("score_medium")
    else:
        bar_color = "#ef4444"   # rouge
        label     = get_text("score_danger")

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        align="center",
        domain={"x": [0, 1], "y": [0, 1]},
        title={
            "text": (
                f"{get_text('security_score_title')}<br>"
                f"<span style='font-size:0.85em;color:{bar_color}'>{label}</span>"
            ),
            "font": {"size": 16, "color": "#0f172a"}
        },
        number={
            "suffix": " / 100",
            "font": {"size": 20, "color": bar_color}
        },
        gauge={
            "axis": {
                "range": [0, 100],
                "tickwidth": 1,
                "tickcolor": "#64748b",
                "tickfont": {"color": "#64748b"}
            },
            "bar": {"color": bar_color, "thickness": 0.25},
            "bgcolor": "#f1f5f9",
            "borderwidth": 2,
            "bordercolor": "#cbd5e1",
            "steps": [
                {"range": [0,  40], "color": "#fef2f2"},
                {"range": [40, 70], "color": "#fff7ed"},
                {"range": [70, 100], "color": "#f0fdf4"},
            ]
        }
    ))

    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#0f172a"},
        height=280,
        margin=dict(t=60, b=20, l=20, r=20)
    )

    return fig