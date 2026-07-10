import os
from flask import Flask, jsonify, render_template, request

from chatbot_service import responder_consulta_burbujas
from datos import obtener_fuente_datos, obtener_info_datos_locales
import evolution_api

app = Flask(__name__)
APP_VERSION = "20260710a"


@app.get("/")
def index():
    return render_template("index.html", app_version=APP_VERSION)


@app.get("/health")
def health():
    return jsonify({"status": "ok", "version": APP_VERSION, "data_source": obtener_fuente_datos()})


@app.get("/api/version")
def api_version():
    info_local = obtener_info_datos_locales()
    return jsonify(
        {
            "status": "ok",
            "version": APP_VERSION,
            "data_source": obtener_fuente_datos(),
            "data_local": info_local,
            "cwd": os.getcwd(),
            "entry": "web_app:app",
            "evolution_api_file": getattr(evolution_api, "__file__", "unknown"),
            "evolution_api_key_loaded": bool(getattr(evolution_api, "EVOLUTION_API_KEY", None)),
        }
    )


@app.post("/api/chat")
def chat_api():
    payload = request.get_json(silent=True) or {}
    consulta = (payload.get("message") or "").strip()

    if not consulta:
        return jsonify({"ok": False, "error": "Debes enviar un mensaje."}), 400

    replies = responder_consulta_burbujas(consulta)
    # Compatibilidad: mantenemos 'reply' con el primer bloque o concatenado.
    reply_text = "\n\n".join(replies) if replies else ""
    return jsonify({"ok": True, "reply": reply_text, "replies": replies, "version": APP_VERSION})


@app.after_request
def add_no_cache_headers(response):
    # Evita que navegador/proxy conserven versiones antiguas de HTML/JS.
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
