import os
from flask import Flask, jsonify, render_template, request

from chatbot_service import responder_consulta

app = Flask(__name__)


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.post("/api/chat")
def chat_api():
    payload = request.get_json(silent=True) or {}
    consulta = (payload.get("message") or "").strip()

    if not consulta:
        return jsonify({"ok": False, "error": "Debes enviar un mensaje."}), 400

    respuesta = responder_consulta(consulta)
    return jsonify({"ok": True, "reply": respuesta})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
