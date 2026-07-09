from datos import cargar_datos
from buscador import buscar
from intenciones import detectar_intencion
from evolution_api import obtener_respuesta_evolution
from utilidades import extraer_busqueda

# Mantiene un unico dataset en memoria para todas las peticiones.
df = cargar_datos()


def _fecha_texto(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor)


def _resumen_fila(fila) -> str:
    return (
        f"Cliente: {fila['CLIENTE']}\n"
        f"Marca: {fila['MARCA']}\n"
        f"Descripcion: {fila['DESCRIPCION']}\n"
        f"Referencia / Modelo: {fila.get('REFERENCIA_MODELO', 'N/E')}\n"
        f"Referencia externa: {fila.get('REFERENCIA_EXTERNA', fila.get('REFERENCIA', 'N/E'))}\n"
        f"Referencia interna: {fila.get('REFERENCIA_INTERNA', fila.get('IDENTIFICACION_INTERNA', 'N/E'))}\n"
        f"Informe: {fila.get('INFORME', 'N/E')}\n"
        f"Cotizacion: {fila.get('COTIZACION', 'N/E')}"
    )


def _formatear_multiples(resultado, intencion: str) -> str:
    bloques = [f"Encontre {len(resultado)} muestra(s):"]

    for i, (_, fila) in enumerate(resultado.iterrows(), start=1):
        fecha = _fecha_texto(fila["FECHA_INGRESO"])
        if intencion == "ubicacion":
            detalle = _resumen_fila(fila)
        elif intencion == "estado":
            detalle = _resumen_fila(fila)
        elif intencion == "fecha":
            detalle = _resumen_fila(fila)
        elif intencion == "cliente":
            detalle = _resumen_fila(fila)
        elif intencion == "descripcion":
            detalle = _resumen_fila(fila)
        elif intencion == "referencia":
            detalle = _resumen_fila(fila)
        elif intencion == "referencia_interna":
            detalle = _resumen_fila(fila)
        elif intencion == "marca":
            detalle = _resumen_fila(fila)
        elif intencion == "informe":
            detalle = _resumen_fila(fila)
        elif intencion == "cotizacion":
            detalle = _resumen_fila(fila)
        else:
            detalle = _resumen_fila(fila)
        bloques.append(f"{i}.\n{detalle}")

    return "\n".join(bloques)


def responder_consulta(consulta: str) -> str:
    if not consulta or not isinstance(consulta, str):
        return "Hola, escribe tu consulta para buscar muestras."

    consulta = consulta.strip()
    if consulta.lower() in {"salir", "exit"}:
        return "Hasta luego 👋"

    if consulta.lower() in {"ayuda", "help"}:
        return (
            "Puedo ayudarte a buscar muestras por cliente, descripcion, referencia, "
            "estado, ubicacion, marca, informe o cotizacion."
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
    if len(resultado) > 1:
        return _formatear_multiples(resultado, intencion)

    fila = resultado.iloc[0]
    if intencion == "ubicacion":
        return _resumen_fila(fila)
    if intencion == "estado":
        return _resumen_fila(fila)
    if intencion == "fecha":
        return _resumen_fila(fila)
    if intencion == "cliente":
        return _resumen_fila(fila)
    if intencion == "descripcion":
        return _resumen_fila(fila)
    if intencion == "referencia":
        return _resumen_fila(fila)
    if intencion == "referencia_interna":
        return _resumen_fila(fila)
    if intencion == "marca":
        return _resumen_fila(fila)
    if intencion == "informe":
        return _resumen_fila(fila)
    if intencion == "cotizacion":
        return _resumen_fila(fila)

    return _resumen_fila(fila)
