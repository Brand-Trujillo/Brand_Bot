import os
import html
import json
import urllib.error
import urllib.request
from flask import Flask, jsonify, request, Response

from datos import cargar_datos
from buscador import buscar
from intenciones import detectar_intencion
from evolution_api import obtener_respuesta_evolution
from utilidades import extraer_busqueda

app = Flask(__name__)
df = cargar_datos()

META_VERIFY_TOKEN = os.getenv("META_VERIFY_TOKEN", "")
META_ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN", "")
META_PHONE_NUMBER_ID = os.getenv("META_PHONE_NUMBER_ID", "")
META_API_VERSION = os.getenv("META_API_VERSION", "v20.0")


def _enviar_mensaje_meta(destino: str, texto: str) -> tuple[bool, str]:
    """Envía un mensaje de texto por WhatsApp Cloud API."""
    if not META_ACCESS_TOKEN or not META_PHONE_NUMBER_ID:
        return False, "Faltan META_ACCESS_TOKEN o META_PHONE_NUMBER_ID."

    endpoint = (
        f"https://graph.facebook.com/{META_API_VERSION}/"
        f"{META_PHONE_NUMBER_ID}/messages"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": destino,
        "type": "text",
        "text": {"body": texto[:4096]},
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "Authorization": f"Bearer {META_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            _ = resp.read().decode("utf-8")
        return True, "ok"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        return False, f"HTTP {exc.code}: {detail}"
    except Exception as exc:
        return False, str(exc)


def responder_consulta(consulta: str) -> str:
    if not consulta or not isinstance(consulta, str):
        return "Hola, escribe tu consulta para buscar muestras."

    consulta = consulta.strip()
    if consulta.lower() in {"salir", "exit"}:
        return "Hasta luego 👋"

    if consulta.lower() in {"ayuda", "help"}:
        return (
            "Puedo ayudarte a buscar muestras por cliente, descripción, referencia, "
            "estado, ubicación, marca, informe o cotización."
        )

    busqueda = extraer_busqueda(consulta)
    resultado, meta = buscar(df, busqueda)

    if resultado.empty:
        return obtener_respuesta_evolution(
            consulta,
            system_prompt=(
                "Eres un asistente de soporte para un sistema de control de muestras de laboratorio. "
                "Responde de forma amable y clara cuando no encuentres una muestra local."
            ),
        )

    intencion = detectar_intencion(consulta)
    if intencion == "ubicacion":
        fila = resultado.iloc[0]
        return f"La muestra está en: {fila['UBICACION']}"
    if intencion == "estado":
        fila = resultado.iloc[0]
        return f"El estado es: {fila['ESTADO']}"
    if intencion == "fecha":
        fila = resultado.iloc[0]
        fecha = fila["FECHA_INGRESO"]
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")
        return f"La fecha de ingreso es: {fecha}"
    if intencion == "cliente":
        fila = resultado.iloc[0]
        return f"El cliente es: {fila['CLIENTE']}"
    if intencion == "descripcion":
        fila = resultado.iloc[0]
        return f"La descripción es: {fila['DESCRIPCION']}"
    if intencion == "referencia":
        fila = resultado.iloc[0]
        return f"La referencia es: {fila['REFERENCIA']}"
    if intencion == "marca":
        fila = resultado.iloc[0]
        return f"La marca es: {fila['MARCA']}"
    if intencion == "informe":
        fila = resultado.iloc[0]
        return f"Informe: {fila.get('INFORME', 'N/E')}"
    if intencion == "cotizacion":
        fila = resultado.iloc[0]
        return f"Cotización: {fila.get('COTIZACION', 'N/E')}"

    fila = resultado.iloc[0]
    fecha = fila["FECHA_INGRESO"]
    if hasattr(fecha, "strftime"):
        fecha = fecha.strftime("%d/%m/%Y")
    return (
        f"Encontré una muestra para {fila['CLIENTE']}\n"
        f"Marca: {fila['MARCA']}\n"
        f"Descripción: {fila['DESCRIPCION']}\n"
        f"Referencia: {fila['REFERENCIA']}\n"
        f"Ubicación: {fila['UBICACION']}\n"
        f"Estado: {fila['ESTADO']}\n"
        f"Fecha: {fecha}"
    )


@app.get("/")
def home():
    return jsonify({"status": "ok", "message": "Bot listo para WhatsApp"})


@app.get("/health")
def health():
    return jsonify({"status": "ok"})


@app.get("/webhook")
def webhook_verify():
    mode = request.args.get("hub.mode", "")
    verify_token = request.args.get("hub.verify_token", "")
    challenge = request.args.get("hub.challenge", "")

    if mode == "subscribe" and verify_token == META_VERIFY_TOKEN and challenge:
        return Response(challenge, status=200, mimetype="text/plain")

    return Response("forbidden", status=403)


@app.post("/webhook")
def webhook_incoming():
    payload = request.get_json(silent=True) or {}

    # Soporte para Twilio Sandbox para WhatsApp
    body = None
    if isinstance(payload, dict):
        body = payload.get("Body") or payload.get("body")

    if not body:
        if request.form:
            body = request.form.get("Body") or request.form.get("body")

    if not body and isinstance(payload, dict):
        entry = payload.get("entry", [])
        if entry:
            changes = entry[0].get("changes", [])
            if changes:
                value = changes[0].get("value", {})
                messages = value.get("messages", [])
                if messages:
                    mensaje = messages[0]
                    body = mensaje.get("text", {}).get("body")
                    from_number = mensaje.get("from")

                    if not body:
                        body = "ayuda"

                    reply = responder_consulta(body)
                    ok, detail = _enviar_mensaje_meta(from_number, reply)
                    if not ok:
                        app.logger.error("Error enviando respuesta Meta: %s", detail)
                    return jsonify({"status": "ok"})

    if not body:
        return jsonify({"status": "ok", "reply": ""})

    reply = responder_consulta(body)

    # Twilio expects XML
    if request.form or request.content_type == "application/x-www-form-urlencoded":
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Response><Message>' + html.escape(reply) + '</Message></Response>'
        )
        return Response(xml, mimetype="application/xml")

    return jsonify({"status": "ok", "reply": reply})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
