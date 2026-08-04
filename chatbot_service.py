from datos import cargar_datos, obtener_fuente_datos
from buscador import buscar
from intenciones import detectar_intencion
from utilidades import extraer_busqueda
import pandas as pd
import os
import time
import json
import re


_CACHE_DF = None
_CACHE_LOADED_AT = 0.0
_HUMAN_VARIANT_COUNTER = 0
_QUERY_METRICS = {
    "total": 0,
    "no_result": 0,
    "ambiguous": 0,
    "last_latency_ms": 0.0,
    "avg_latency_ms": 0.0,
    "last_query_ts": 0.0,
    "cache_hits": 0,
    "cache_misses": 0,
}


def _append_jsonl(path: str, payload: dict) -> None:
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
        pass


def _registrar_evento_calidad(consulta: str, busqueda: str, resultado_count: int, meta: dict, latency_ms: float) -> None:
    global _QUERY_METRICS
    _QUERY_METRICS["total"] += 1
    _QUERY_METRICS["last_latency_ms"] = round(latency_ms, 2)
    _QUERY_METRICS["last_query_ts"] = time.time()
    prev_avg = float(_QUERY_METRICS["avg_latency_ms"])
    total = int(_QUERY_METRICS["total"])
    _QUERY_METRICS["avg_latency_ms"] = round(((prev_avg * (total - 1)) + latency_ms) / max(1, total), 2)

    if resultado_count == 0:
        _QUERY_METRICS["no_result"] += 1
    if resultado_count > 8:
        _QUERY_METRICS["ambiguous"] += 1

    event = {
        "ts": _QUERY_METRICS["last_query_ts"],
        "consulta": consulta,
        "busqueda": busqueda,
        "resultados": int(resultado_count),
        "match": (meta or {}).get("match", "unknown"),
        "match_field": (meta or {}).get("match_field", ""),
        "latency_ms": round(latency_ms, 2),
        "data_source": obtener_fuente_datos(),
    }
    if resultado_count == 0 or resultado_count > 8:
        log_path = os.getenv("CHATBOT_METRICS_LOG_PATH", "logs/chat_quality.jsonl").strip() or "logs/chat_quality.jsonl"
        _append_jsonl(log_path, event)


def obtener_metricas_chatbot() -> dict:
    return {
        "total_queries": int(_QUERY_METRICS["total"]),
        "no_result_queries": int(_QUERY_METRICS["no_result"]),
        "ambiguous_queries": int(_QUERY_METRICS["ambiguous"]),
        "last_latency_ms": float(_QUERY_METRICS["last_latency_ms"]),
        "avg_latency_ms": float(_QUERY_METRICS["avg_latency_ms"]),
        "last_query_ts": float(_QUERY_METRICS["last_query_ts"]),
        "cache_hits": int(_QUERY_METRICS["cache_hits"]),
        "cache_misses": int(_QUERY_METRICS["cache_misses"]),
        "refresh_mode": _obtener_refresh_mode(),
        "cache_ttl_seconds": _obtener_cache_ttl(),
    }


def _siguiente_indice_plantilla() -> int:
    global _HUMAN_VARIANT_COUNTER
    _HUMAN_VARIANT_COUNTER += 1
    return _HUMAN_VARIANT_COUNTER


def _detectar_tono_usuario(consulta: str) -> str:
    texto = str(consulta or "").strip().lower()
    if any(k in texto for k in ["porfa", "gracias", "oye", "holi", "q", "k"]):
        return "cercano"
    if any(k in texto for k in ["por favor", "cordial", "buen dia", "buenos dias"]):
        return "formal"
    return "neutral"


def _obtener_tono_respuesta(consulta: str) -> str:
    configured = os.getenv("CHATBOT_RESPONSE_TONE", "auto").strip().lower()
    if configured in {"formal", "cercano", "neutral"}:
        return configured
    return _detectar_tono_usuario(consulta)


def _texto_confirmacion(busqueda: str, intencion: str, tono: str) -> str:
    if not busqueda:
        return ""

    campo = {
        "informe": "informe",
        "cotizacion": "cotizacion",
        "referencia": "referencia",
        "referencia_interna": "referencia interna",
        "referencia_externa": "referencia externa",
        "cliente": "cliente",
        "estado": "estado",
        "ubicacion": "ubicacion",
        "marca": "marca",
        "descripcion": "descripcion",
        "fecha": "fecha",
    }.get(intencion, "criterio")

    if intencion in {"criterio", "todo"} and re.fullmatch(r"[\d\s\-_/]+", busqueda):
        if tono == "cercano":
            return f"Voy por {busqueda}."
        return f"Voy a buscar {busqueda}."

    if tono == "cercano":
        return f"Voy por {campo}: {busqueda}."
    return f"Voy a buscar por {campo}: {busqueda}."


def _texto_apertura(tipo: str, cantidad: int, tono: str) -> str:
    idx = _siguiente_indice_plantilla()
    if tipo == "ninguno":
        opciones_formal = ["No encontré coincidencias.", "No vi resultados con ese criterio."]
        opciones_cercano = ["Todavía no me aparece esa coincidencia.", "No la encontré por ahora."]
        opciones_neutral = ["No encontré coincidencias.", "No aparecen resultados con esa búsqueda."]
    elif tipo == "uno":
        opciones_formal = ["Ya tengo el resultado.", "Le comparto el resultado encontrado."]
        opciones_cercano = ["Ya lo tengo.", "Listo, te paso el resultado."]
        opciones_neutral = ["Encontré 1 coincidencia.", "Tengo 1 resultado para ti."]
    else:
        opciones_formal = [f"Encontré {cantidad} coincidencias.", f"Hay {cantidad} resultados para usted."]
        opciones_cercano = [f"Te salieron {cantidad} coincidencias.", f"Te encontré {cantidad} resultados."]
        opciones_neutral = [f"Encontré {cantidad} coincidencias.", f"Tengo {cantidad} resultados."]

    if tono == "formal":
        return opciones_formal[idx % len(opciones_formal)]
    if tono == "cercano":
        return opciones_cercano[idx % len(opciones_cercano)]
    return opciones_neutral[idx % len(opciones_neutral)]


def _texto_cierre(intencion: str, cantidad: int, tono: str) -> str:
    if cantidad == 0:
        if tono == "formal":
            return "Si desea, lo intentamos por informe, cotización o referencia exacta."
        if tono == "cercano":
            return "Si quieres, lo intentamos por informe, cotización o referencia exacta."
        return "Si quieres, probamos por informe, cotización o referencia exacta."

    if cantidad == 1:
        return ""

    if intencion in {"informe", "cotizacion", "referencia", "referencia_interna", "referencia_externa"}:
        return "Si quieres, lo afinamos por cliente o estado."
    return "Si quieres, lo refinamos por informe, cotización, estado o cliente."


def _join_clean(parts: list[str]) -> str:
    return "\n".join([p for p in parts if p and str(p).strip()])


def _list_clean(parts: list[str]) -> list[str]:
    return [p for p in parts if p and str(p).strip()]


def _obtener_refresh_mode() -> str:
    mode = os.getenv("CHATBOT_DATA_REFRESH_MODE", "fast").strip().lower()
    return "fast" if mode == "fast" else "strict"


def _obtener_cache_ttl() -> float:
    raw = os.getenv("CHATBOT_DATA_CACHE_TTL_SECONDS", "300").strip()
    try:
        ttl = float(raw)
    except (TypeError, ValueError):
        return 15.0
    return max(1.0, ttl)


def _obtener_dataframe_consulta():
    """Obtiene datos con modo estricto o modo rápido (microcaché)."""
    global _CACHE_DF, _CACHE_LOADED_AT

    mode = _obtener_refresh_mode()
    now = time.monotonic()

    if mode == "fast" and _CACHE_DF is not None:
        ttl = _obtener_cache_ttl()
        if (now - _CACHE_LOADED_AT) <= ttl:
            _QUERY_METRICS["cache_hits"] += 1
            return _CACHE_DF

    try:
        _QUERY_METRICS["cache_misses"] += 1
        df = cargar_datos()
    except Exception:
        # En modo rapido permitimos fallback a cache previa para mantener respuesta.
        if mode == "fast" and _CACHE_DF is not None:
            _QUERY_METRICS["cache_hits"] += 1
            return _CACHE_DF
        raise

    _CACHE_DF = df
    _CACHE_LOADED_AT = now
    return df


def _ordenar_primera_muestra(resultado):
    if resultado is None or resultado.empty:
        return resultado

    ordenado = resultado.copy()
    if 'FECHA_INGRESO' in ordenado.columns:
        ordenado['_fecha_orden'] = pd.to_datetime(ordenado['FECHA_INGRESO'], errors='coerce')
    else:
        ordenado['_fecha_orden'] = pd.NaT

    if 'ITEM' in ordenado.columns:
        ordenado['_item_orden'] = pd.to_numeric(ordenado['ITEM'], errors='coerce')
    else:
        ordenado['_item_orden'] = pd.NA

    ordenado = ordenado.sort_values(
        by=['_fecha_orden', '_item_orden'],
        ascending=[True, True],
        na_position='last',
    )
    return ordenado.drop(columns=['_fecha_orden', '_item_orden'])


def _valor_texto(valor) -> str:
    # Mostrar el contenido tal como viene de la celda.
    # Solo evitamos imprimir literales tecnicos de pandas para celdas vacias.
    if valor is None:
        return ""
    texto = str(valor)
    if texto.lower() in {"nan", "nat", "none"}:
        return ""
    return texto


def _fecha_texto(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def _numero_muestras_texto(fila) -> str:
    claves_directas = [
        "NUMERO",
        "N_MUESTRAS",
        "NUM_MUESTRAS",
        "CANTIDAD_MUESTRAS",
        "MUESTRAS",
        "CANTIDAD",
        "CANT",
        "NUM",
    ]
    for clave in claves_directas:
        valor = _campo_valor_texto(fila, clave)
        if valor != "N/E":
            return valor

    for clave in fila.index:
        clave_norm = re.sub(r"[^A-Z0-9]", "", str(clave).upper())
        if any(palabra in clave_norm for palabra in ["MUESTRA", "CANTIDAD", "NUMERO", "NUM"]):
            valor = _valor_texto(fila.get(clave))
            if valor:
                return valor

    return "N/E"


def _campo_valor_texto(fila, *campos: str) -> str:
    objetivos = []
    for campo in campos:
        campo_norm = re.sub(r"[^a-z0-9]", "", str(campo).lower())
        if campo_norm and campo_norm not in objetivos:
            objetivos.append(campo_norm)

    for columna in fila.index:
        columna_norm = re.sub(r"[^a-z0-9]", "", str(columna).lower())
        if not columna_norm:
            continue
        if any(
            columna_norm == objetivo
            or columna_norm.startswith(objetivo)
            or objetivo.startswith(columna_norm)
            or objetivo in columna_norm
            for objetivo in objetivos
        ):
            valor = _valor_texto(fila.get(columna))
            if valor:
                return valor
    return "N/E"


def _marca_texto(fila) -> str:
    marca = _valor_texto(fila.get("MARCA"))
    cliente = _valor_texto(fila.get("CLIENTE"))
    referencia_modelo = _valor_texto(fila.get("REFERENCIA_MODELO"))

    # Si la marca parece un prefijo técnico del modelo (ej. VTA-84529),
    # mostramos el cliente como marca visible para evitar confusión.
    if (
        marca
        and cliente
        and marca.isupper()
        and len(marca) <= 4
        and referencia_modelo.upper().startswith(f"{marca}-")
    ):
        return cliente

    if not marca:
        return cliente
    return marca


def _es_registro_equipo(fila) -> bool:
    return _valor_texto(fila.get("TIPO_REGISTRO")).lower() == "equipo"


def _resumen_fila_equipo(fila) -> str:
    return (
        f"Equipo: {_valor_texto(fila.get('EQUIPO'))}\n"
        f"Identificacion interna: {_valor_texto(fila.get('REFERENCIA_INTERNA'))}\n"
        f"Serie: {_valor_texto(fila.get('SERIE'))}\n"
        f"Marca: {_valor_texto(fila.get('MARCA'))}\n"
        f"Magnitud: {_valor_texto(fila.get('MAGNITUD'))}\n"
        f"Modelo: {_valor_texto(fila.get('REFERENCIA_MODELO'))}\n"
        f"Ultima calibracion: {_fecha_texto(fila.get('ULTIMA_CALIBRACION'))}\n"
        f"Calibrado por: {_valor_texto(fila.get('CALIBRADO_POR'))}\n"
        f"Proxima calibracion: {_fecha_texto(fila.get('PROXIMA_CALIBRACION'))}\n"
        f"Tiempo de alarma: {_fecha_texto(fila.get('TIEMPO_ALARMA'))}\n"
        f"Estado de calibracion: {_valor_texto(fila.get('ESTADO_CALIBRACION'))}"
    )


def _resumen_fila(fila) -> str:
    if _es_registro_equipo(fila):
        return _resumen_fila_equipo(fila)

    fecha = _fecha_texto(fila.get("FECHA_INGRESO", "N/E"))

    return (
        f"Cliente: {_valor_texto(fila.get('CLIENTE'))}\n"
        f"Marca: {_marca_texto(fila)}\n"
        f"Descripcion: {_valor_texto(fila.get('DESCRIPCION'))}\n"
        f"Referencia / Modelo: {_valor_texto(fila.get('REFERENCIA_MODELO'))}\n"
        f"Referencia externa: {_valor_texto(fila.get('REFERENCIA_EXTERNA'))}\n"
        f"Referencia interna: {_valor_texto(fila.get('REFERENCIA_INTERNA'))}\n"
        f"N° muestras: {_numero_muestras_texto(fila)}\n"
        f"Informe: {_campo_valor_texto(fila, 'INFORME', 'NUMERO_INFORME', 'numeroInforme')}\n"
        f"Cotizacion: {_campo_valor_texto(fila, 'COTIZACION', 'NUMERO_COTIZACION', 'numeroCotizacion')}\n"
        f"Estado: {_valor_texto(fila.get('ESTADO'))}\n"
        f"Ubicacion: {_valor_texto(fila.get('UBICACION'))}\n"
        f"Fecha recepcion: {fecha}"
    )


def _campo_por_intencion(fila, intencion: str) -> str:
    if _es_registro_equipo(fila):
        return f"Estado de calibracion: {_valor_texto(fila.get('ESTADO_CALIBRACION'))}"

    fecha = _fecha_texto(fila.get("FECHA_INGRESO", "N/E"))

    if intencion == "ubicacion":
        return f"Ubicacion: {_valor_texto(fila.get('UBICACION'))}"
    if intencion == "estado":
        return f"Estado: {_valor_texto(fila.get('ESTADO'))}"
    if intencion == "fecha":
        return f"Fecha ingreso: {fecha}"
    if intencion == "cliente":
        return f"Cliente: {_valor_texto(fila.get('CLIENTE'))}"
    if intencion == "descripcion":
        return f"Descripcion: {_valor_texto(fila.get('DESCRIPCION'))}"
    if intencion == "referencia":
        return f"Referencia externa: {_valor_texto(fila.get('REFERENCIA_EXTERNA'))}"
    if intencion == "referencia_interna":
        return f"Referencia interna: {_valor_texto(fila.get('REFERENCIA_INTERNA'))}"
    if intencion == "referencia_externa":
        return f"Referencia externa: {_valor_texto(fila.get('REFERENCIA_EXTERNA'))}"
    if intencion == "marca":
        return f"Marca: {_valor_texto(fila.get('MARCA'))}"
    if intencion == "informe":
        return f"Informe: {_campo_valor_texto(fila, 'INFORME', 'NUMERO_INFORME', 'numeroInforme')}"
    if intencion == "cotizacion":
        return f"Cotizacion: {_campo_valor_texto(fila, 'COTIZACION', 'NUMERO_COTIZACION', 'numeroCotizacion')}"

    return (
        f"Estado: {_valor_texto(fila.get('ESTADO'))} | "
        f"Ubicacion: {_valor_texto(fila.get('UBICACION'))} | "
        f"Fecha ingreso: {fecha}"
    )


def _resumen_corto(fila, intencion: str) -> str:
    if _es_registro_equipo(fila):
        return (
            f"Equipo: {_valor_texto(fila.get('EQUIPO'))} | "
            f"Id interna: {_valor_texto(fila.get('REFERENCIA_INTERNA'))} | "
            f"Serie: {_valor_texto(fila.get('SERIE'))}\n"
            f"Marca: {_valor_texto(fila.get('MARCA'))} | Magnitud: {_valor_texto(fila.get('MAGNITUD'))} | "
            f"Modelo: {_valor_texto(fila.get('REFERENCIA_MODELO'))} | "
            f"Estado calibracion: {_valor_texto(fila.get('ESTADO_CALIBRACION'))}"
        )

    return (
        f"Cliente: {_valor_texto(fila.get('CLIENTE'))} | "
        f"Ref. interna: {_valor_texto(fila.get('REFERENCIA_INTERNA') or fila.get('ID'))} | "
        f"N° muestras: {_numero_muestras_texto(fila)} | "
        f"Informe: {_campo_valor_texto(fila, 'INFORME', 'NUMERO_INFORME', 'numeroInforme')} | "
        f"Cotizacion: {_campo_valor_texto(fila, 'COTIZACION', 'NUMERO_COTIZACION', 'numeroCotizacion')}\n"
        f"{_campo_por_intencion(fila, intencion)}"
    )


def _resumen_muestra_multiple(fila) -> str:
    fecha = _fecha_texto(fila.get("FECHA_INGRESO", "N/E"))
    return (
        f"Cliente: {_valor_texto(fila.get('CLIENTE'))}\n"
        f"Marca: {_marca_texto(fila)}\n"
        f"Descripcion: {_valor_texto(fila.get('DESCRIPCION'))}\n"
        f"Referencia / Modelo: {_valor_texto(fila.get('REFERENCIA_MODELO'))}\n"
        f"Referencia externa: {_valor_texto(fila.get('REFERENCIA_EXTERNA'))}\n"
        f"Referencia interna: {_valor_texto(fila.get('REFERENCIA_INTERNA') or fila.get('ID'))}\n"
        f"N° muestras: {_numero_muestras_texto(fila)}\n"
        f"Informe: {_campo_valor_texto(fila, 'INFORME', 'NUMERO_INFORME', 'numeroInforme')}\n"
        f"Cotizacion: {_campo_valor_texto(fila, 'COTIZACION', 'NUMERO_COTIZACION', 'numeroCotizacion')}\n"
        f"Estado: {_valor_texto(fila.get('ESTADO'))}\n"
        f"Ubicacion: {_valor_texto(fila.get('UBICACION'))}\n"
        f"Fecha recepcion: {fecha}"
    )


def _formatear_multiples(resultado, intencion: str) -> str:
    total = len(resultado)
    max_items = 8
    recorte = _ordenar_primera_muestra(resultado).head(max_items)
    bloques = []
    if total > max_items:
        bloques.append(f"Te muestro las {max_items} coincidencias mas relevantes. Si quieres, te ayudo a filtrar por cliente, estado, informe o cotizacion.")

    for i, (_, fila) in enumerate(recorte.iterrows(), start=1):
        detalle = _resumen_muestra_multiple(fila)
        bloques.append(f"{i}.\n{detalle}")

    return "\n".join(bloques)


def _formatear_multiples_equipos(resultado) -> list[str]:
    total = len(resultado)
    max_items = 8
    recorte = _ordenar_primera_muestra(resultado).head(max_items)
    bloques = []
    if total > max_items:
        bloques.append(
            f"Te muestro los {max_items} equipos mas relevantes. Si quieres, te ayudo a filtrar por cliente, estado o marca."
        )

    for i, (_, fila) in enumerate(recorte.iterrows(), start=1):
        bloques.append(f"{i}.\n{_resumen_fila_equipo(fila)}")

    return bloques


def _mensaje_sin_coincidencias(consulta: str = "", busqueda: str = "") -> str:
    tono = _obtener_tono_respuesta(consulta)
    consulta_txt = str(consulta or "").strip()
    busqueda_txt = str(busqueda or "").strip()
    if tono == "formal":
        base = "No encontre coincidencias locales por el momento."
    elif tono == "cercano":
        base = "Todavia no me aparece esa coincidencia en la base."
    else:
        base = "No encontre coincidencias locales por ahora."

    sugerencias = [
        "1) Prueba solo el informe (ej: I 0704).",
        "2) Prueba solo la cotizacion (ej: C 0704).",
        "3) Prueba referencia exacta sin texto extra.",
    ]
    if consulta_txt and busqueda_txt and consulta_txt != busqueda_txt:
        sugerencias.append(f"4) Consulta depurada usada por el bot: {busqueda_txt}")

    return _join_clean([
        base,
        "\n".join(sugerencias),
        _texto_cierre("", 0, tono),
    ])


def responder_consulta(consulta: str) -> str:
    started_at = time.perf_counter()
    if not consulta or not isinstance(consulta, str):
        return "Hola, escribe tu consulta para buscar muestras."

    consulta = consulta.strip()
    tono = _obtener_tono_respuesta(consulta)
    if consulta.lower() in {"salir", "exit"}:
        return "Hasta luego"

    if consulta.lower() in {"ayuda", "help"}:
        return (
            "Puedo ayudarte a buscar muestras por cliente, descripcion, referencia, "
            "estado, ubicacion, marca, informe o cotizacion."
        )

    # Modo strict: recarga en cada consulta. Modo fast: usa microcache TTL.
    df = _obtener_dataframe_consulta()

    busqueda = extraer_busqueda(consulta)
    resultado, meta = buscar(df, busqueda)
    latency_ms = (time.perf_counter() - started_at) * 1000.0
    _registrar_evento_calidad(consulta, busqueda, len(resultado), meta, latency_ms)
    intencion = detectar_intencion(consulta)
    confirmacion = _texto_confirmacion(busqueda, intencion, tono)

    if resultado.empty:
        return _join_clean([confirmacion, _mensaje_sin_coincidencias(consulta, busqueda)])

    if len(resultado) > 1:
        if all(_es_registro_equipo(fila) for _, fila in resultado.iterrows()):
            bloques = _formatear_multiples_equipos(resultado)
            return _join_clean([
                "\n".join(bloques),
                _texto_apertura("multi", len(resultado), tono),
                confirmacion,
                _texto_cierre(intencion, len(resultado), tono),
            ])
        return _join_clean([
            _formatear_multiples(resultado, intencion),
            _texto_apertura("multi", len(resultado), tono),
            confirmacion,
            _texto_cierre(intencion, len(resultado), tono),
        ])

    fila = resultado.iloc[0]

    if _es_registro_equipo(fila):
        return _join_clean([
            _texto_apertura("uno", 1, tono),
            confirmacion,
            _resumen_fila_equipo(fila),
            _texto_cierre(intencion, 1, tono),
        ])

    return _join_clean([
        _texto_apertura("uno", 1, tono),
        confirmacion,
        _resumen_corto(fila, intencion),
        _texto_cierre(intencion, 1, tono),
    ])


def responder_consulta_burbujas(consulta: str):
    started_at = time.perf_counter()
    if not consulta or not isinstance(consulta, str):
        return ["Hola, escribe tu consulta para buscar muestras."]

    consulta = consulta.strip()
    tono = _obtener_tono_respuesta(consulta)
    if consulta.lower() in {"salir", "exit"}:
        return ["Hasta luego"]

    if consulta.lower() in {"ayuda", "help"}:
        return [
            "Puedo ayudarte a buscar muestras por cliente, descripcion, referencia, estado, ubicacion, marca, informe o cotizacion."
        ]

    # Modo strict: recarga en cada consulta. Modo fast: usa microcache TTL.
    df = _obtener_dataframe_consulta()

    busqueda = extraer_busqueda(consulta)
    resultado, meta = buscar(df, busqueda)
    latency_ms = (time.perf_counter() - started_at) * 1000.0
    _registrar_evento_calidad(consulta, busqueda, len(resultado), meta, latency_ms)
    intencion = detectar_intencion(consulta)
    confirmacion = _texto_confirmacion(busqueda, intencion, tono)

    if resultado.empty:
        return _list_clean([confirmacion, _mensaje_sin_coincidencias(consulta, busqueda)])

    if len(resultado) > 1:
        if all(_es_registro_equipo(fila) for _, fila in resultado.iterrows()):
            total = len(resultado)
            max_items = 8
            recorte = _ordenar_primera_muestra(resultado).head(max_items)
            bloques = []
            if total > max_items:
                bloques.append(
                    f"Te muestro los {max_items} equipos mas relevantes. Si quieres, te ayudo a filtrar por cliente, estado o marca."
                )
            for i, (_, fila) in enumerate(recorte.iterrows(), start=1):
                bloques.append(f"{i}.\n{_resumen_fila_equipo(fila)}")
            bloques.extend([
                _texto_apertura("multi", total, tono),
                confirmacion,
                _texto_cierre(intencion, total, tono),
            ])
            return bloques
        total = len(resultado)
        max_items = 8
        recorte = _ordenar_primera_muestra(resultado).head(max_items)
        bloques = []
        if total > max_items:
            bloques.append(
                f"Te muestro las {max_items} coincidencias mas relevantes. Si quieres, te ayudo a filtrar por cliente, estado, informe o cotizacion."
            )
        for i, (_, fila) in enumerate(recorte.iterrows(), start=1):
            if _es_registro_equipo(fila):
                bloques.append(f"{i}.\n{_resumen_fila(fila)}")
            else:
                bloques.append(f"{i}.\n{_resumen_muestra_multiple(fila)}")
        bloques.extend([
            _texto_apertura("multi", total, tono),
            confirmacion,
            _texto_cierre(intencion, total, tono),
        ])
        return bloques

    fila = resultado.iloc[0]
    if _es_registro_equipo(fila):
        return _list_clean([_texto_apertura("uno", 1, tono), confirmacion, _resumen_fila_equipo(fila), _texto_cierre(intencion, 1, tono)])

    return _list_clean([_texto_apertura("uno", 1, tono), confirmacion, _resumen_fila(fila), _texto_cierre(intencion, 1, tono)])
