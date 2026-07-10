import re

def extraer_busqueda(texto):
    if not texto or not isinstance(texto, str):
        return ""

    consulta = texto.strip()
    if not consulta:
        return ""

    # Si la consulta es solo un número, mantenemos ese comportamiento.
    if re.fullmatch(r"\d+", consulta):
        return consulta

    # En cualquier otro caso, preservamos el texto completo para no perder contexto
    # de campo (ej. "informe 406", "cotizacion 502", "referencia SPN1516").
    return consulta