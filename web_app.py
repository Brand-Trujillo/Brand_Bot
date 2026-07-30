import os
from datetime import datetime
from flask import Flask, jsonify, render_template, request, send_from_directory, Response
import pandas as pd

from chatbot_service import obtener_metricas_chatbot, responder_consulta_burbujas
from datos import (
    cargar_datos,
    obtener_alertas_datos,
    obtener_fuente_datos,
    obtener_info_datos_locales,
    obtener_metricas_datos,
)
import evolution_api

app = Flask(__name__)
APP_VERSION = "20260730b"
DEPLOY_COMMIT = os.getenv("RENDER_GIT_COMMIT", "local")

WEEKDAY_LABELS = {
    0: "Lunes",
    1: "Martes",
    2: "Miercoles",
    3: "Jueves",
    4: "Viernes",
}


def _ordenar_dias_desde_hoy(days: list[dict]) -> list[dict]:
    if not days:
        return []

    by_key = {str(day.get("key", "")).strip().lower(): day for day in days}
    weekday = datetime.now().weekday()  # 0=lunes ... 6=domingo
    start_index = weekday if 0 <= weekday <= 4 else 0
    ordered_keys = ["lunes", "martes", "miercoles", "jueves", "viernes"]
    rotated = ordered_keys[start_index:] + ordered_keys[:start_index]

    ordered = []
    for key in rotated:
        day = by_key.get(key)
        if day:
            ordered.append(day)

    for day in days:
        if day not in ordered:
            ordered.append(day)

    return ordered


def _value_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() in {"nan", "nat", "none"}:
        return ""
    return text


def _build_recientes_payload(limit_per_day: int = 20) -> dict:
    limit_per_day = max(1, min(int(limit_per_day or 20), 100))
    df = cargar_datos()

    if "TIPO_REGISTRO" in df.columns:
        tipo = df["TIPO_REGISTRO"].astype(str).str.strip().str.lower()
        df = df[tipo == "muestra"].copy()
    else:
        df = df.copy()

    if "FECHA_INGRESO" not in df.columns:
        return {
            "ok": True,
            "updated_at": datetime.utcnow().isoformat() + "Z",
            "source": obtener_fuente_datos(),
            "total_items": 0,
            "days": [
                {"key": "lunes", "label": "Lunes", "count": 0, "items": []},
                {"key": "martes", "label": "Martes", "count": 0, "items": []},
                {"key": "miercoles", "label": "Miercoles", "count": 0, "items": []},
                {"key": "jueves", "label": "Jueves", "count": 0, "items": []},
                {"key": "viernes", "label": "Viernes", "count": 0, "items": []},
            ],
        }

    df["_fecha_ingreso"] = pd.to_datetime(df["FECHA_INGRESO"], errors="coerce")
    df = df[df["_fecha_ingreso"].notna()].copy()
    df = df[df["_fecha_ingreso"].dt.weekday <= 4].copy()

    if "ITEM" in df.columns:
        df["_item_sort"] = pd.to_numeric(df["ITEM"], errors="coerce")
    else:
        df["_item_sort"] = pd.NA

    df = df.sort_values(by=["_fecha_ingreso", "_item_sort"], ascending=[False, False], na_position="last")

    days = []
    total_items = 0
    for weekday in range(0, 5):
        day_df = df[df["_fecha_ingreso"].dt.weekday == weekday].head(limit_per_day)
        items = []
        for _, row in day_df.iterrows():
            items.append(
                {
                    "fecha": row["_fecha_ingreso"].strftime("%Y-%m-%d"),
                    "fecha_corta": row["_fecha_ingreso"].strftime("%m-%d"),
                    "cliente": _value_text(row.get("CLIENTE")),
                    "descripcion": _value_text(row.get("DESCRIPCION")),
                    "marca": _value_text(row.get("MARCA")),
                    "referencia_modelo": _value_text(row.get("REFERENCIA_MODELO")),
                    "referencia_externa": _value_text(row.get("REFERENCIA_EXTERNA")),
                    "referencia_interna": _value_text(row.get("REFERENCIA_INTERNA")),
                    "informe": _value_text(row.get("INFORME")),
                    "cotizacion": _value_text(row.get("COTIZACION")),
                    "estado": _value_text(row.get("ESTADO")),
                    "numero": _value_text(row.get("NUMERO")),
                }
            )

        total_items += len(items)
        label = WEEKDAY_LABELS[weekday]
        days.append(
            {
                "key": label.lower(),
                "label": label,
                "count": len(items),
                "items": items,
            }
        )

    return {
        "ok": True,
        "updated_at": datetime.utcnow().isoformat() + "Z",
        "source": obtener_fuente_datos(),
        "total_items": total_items,
        "days": _ordenar_dias_desde_hoy(days),
    }


@app.get("/")
def index():
    return render_template("index.html", app_version=APP_VERSION)


@app.get("/recientes")
def recientes():
    return render_template("recientes.html", app_version=APP_VERSION)


@app.get("/favicon.ico")
def favicon_ico():
    # Compatibilidad robusta: intenta archivos locales y, si faltan,
    # responde un SVG embebido para evitar 404 en producción.
    for filename, mimetype in (
        ("favicon.ico", "image/x-icon"),
    ):
        if os.path.exists(os.path.join(app.static_folder, filename)):
            return send_from_directory(app.static_folder, filename, mimetype=mimetype)

    fallback_svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'>
<rect width='64' height='64' rx='14' fill='#104CFF'/>
<circle cx='32' cy='32' r='24' fill='#27C8FF'/>
<text x='32' y='41' text-anchor='middle' font-size='28' font-family='Arial' fill='white'>B</text>
</svg>"""
    return Response(fallback_svg, mimetype="image/svg+xml")


@app.get("/health")
def health():
    data_metrics = obtener_metricas_datos()
    chat_metrics = obtener_metricas_chatbot()
    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "data_source": obtener_fuente_datos(),
            "data_last_load_ms": data_metrics.get("last_load_duration_ms"),
            "data_last_rows": data_metrics.get("last_load_rows"),
            "chat_last_latency_ms": chat_metrics.get("last_latency_ms"),
            "deploy_commit": DEPLOY_COMMIT,
        }
    )


@app.get("/api/ops-health")
def ops_health():
    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "deploy_commit": DEPLOY_COMMIT,
            "data": obtener_metricas_datos(),
            "chat": obtener_metricas_chatbot(),
            "alerts": obtener_alertas_datos(limit=10),
        }
    )


@app.get("/api/version")
def api_version():
    info_local = obtener_info_datos_locales()
    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "data_source": obtener_fuente_datos(),
            "data_local": info_local,
            "deploy_commit": DEPLOY_COMMIT,
            "cwd": os.getcwd(),
            "entry": "web_app:app",
            "evolution_api_file": getattr(evolution_api, "__file__", "unknown"),
            "evolution_api_key_loaded": bool(getattr(evolution_api, "EVOLUTION_API_KEY", None)),
        }
    )


@app.get("/api/data-diagnostic")
def api_data_diagnostic():
    """Diagnóstico rápido para verificar recarga de muestras en producción."""
    probes = request.args.getlist("probe")
    if not probes:
        probes = ["21961", "I 0704", "C 0704"]

    info_local_before = obtener_info_datos_locales()
    source_before = obtener_fuente_datos()

    try:
        df = cargar_datos()
    except Exception as exc:
        return jsonify(
            {
                "status": "error",
                "version": APP_VERSION,
                "source_before": source_before,
                "data_local": info_local_before,
                "error": str(exc),
            }
        ), 500

    source_after = obtener_fuente_datos()
    info_local_after = obtener_info_datos_locales()

    if "FECHA_INGRESO" in df.columns:
        fechas = pd.to_datetime(df["FECHA_INGRESO"], errors="coerce")
        max_fecha = None if fechas.isna().all() else str(fechas.max())
    else:
        max_fecha = None

    probe_result = {}
    df_texto = df.astype(str)
    for probe in probes:
        mask = df_texto.apply(
            lambda row: row.str.contains(probe, case=False, regex=False, na=False).any(),
            axis=1,
        )
        probe_result[probe] = int(mask.sum())

    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "source_before": source_before,
            "source_after": source_after,
            "rows": int(len(df)),
            "columns": int(len(df.columns)),
            "max_fecha_ingreso": max_fecha,
            "probe_matches": probe_result,
            "data_local": info_local_after,
        }
    )


@app.get("/api/recentes")
def api_recentes():
    try:
        limit = request.args.get("limit", default=20, type=int)
        payload = _build_recientes_payload(limit_per_day=limit)
        payload["version"] = APP_VERSION
        payload["deploy_commit"] = DEPLOY_COMMIT
        return jsonify(payload)
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Error interno del servidor: {exc}", "version": APP_VERSION}), 500


@app.post("/api/chat")
def chat_api():
    try:
        payload = request.get_json(silent=True) or {}
        consulta = (payload.get("message") or "").strip()

        if not consulta:
            return jsonify({"ok": False, "error": "Debes enviar un mensaje."}), 400

        replies = responder_consulta_burbujas(consulta)
        # Compatibilidad: mantenemos 'reply' con el primer bloque o concatenado.
        reply_text = "\n\n".join(replies) if replies else ""
        return jsonify({"ok": True, "reply": reply_text, "replies": replies, "version": APP_VERSION})
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Error interno del servidor: {exc}"}), 500


@app.after_request
def add_no_cache_headers(response):
    # Evita que navegador/proxy conserven versiones antiguas de HTML/JS.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
