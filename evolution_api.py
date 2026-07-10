import json
import os
import urllib.error
import urllib.request

EVOLUTION_API_URL = os.getenv(
    "EVOLUTION_API_URL",
    "https://api.evolution.ai/v1/chat/completions"
)
EVOLUTION_API_KEY = os.getenv("EVOLUTION_API_KEY")
EVOLUTION_API_MODEL = os.getenv("EVOLUTION_API_MODEL", "evolution-1")


def _get_headers():
    if not EVOLUTION_API_KEY:
        raise RuntimeError(
            "El asistente externo no está configurado. Define la variable de entorno EVOLUTION_API_KEY."
        )
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {EVOLUTION_API_KEY}",
    }


def obtener_respuesta_evolution(prompt, system_prompt=None, max_tokens=512):
    """Envía una consulta a Evolution API y devuelve la respuesta de texto."""
    if not EVOLUTION_API_KEY:
        return (
            "No encontré esa muestra ahora. "
            "Prueba con cliente, referencia o informe y te ayudo al instante."
        )

    payload = {
        "model": EVOLUTION_API_MODEL,
        "messages": [],
        "max_tokens": max_tokens,
    }
    if system_prompt:
        payload["messages"].append({"role": "system", "content": system_prompt})
    payload["messages"].append({"role": "user", "content": prompt})

    request_data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        EVOLUTION_API_URL,
        data=request_data,
        headers=_get_headers(),
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_text = response.read().decode("utf-8")
            response_json = json.loads(response_text)

            # Ajusta esta extracción según el formato de Evolution API.
            if "choices" in response_json:
                choice = response_json["choices"][0]
                if isinstance(choice, dict):
                    message = choice.get("message") or choice.get("text")
                    if isinstance(message, dict):
                        return message.get("content", "")
                    return message or ""

            return response_json.get("text", "Respuesta no disponible desde Evolution API.")
    except urllib.error.HTTPError as exc:
        return f"Error de Evolution API: {exc.code} {exc.reason}"
    except urllib.error.URLError as exc:
        return f"No se pudo conectar a Evolution API: {exc.reason}"
    except Exception as exc:
        return f"Error inesperado al usar Evolution API: {exc}"