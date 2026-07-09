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
    fecha = _fecha_texto(fila["FECHA_INGRESO"])
    return (
        f"Cliente: {fila['CLIENTE']}\n"
        f"Marca: {fila['MARCA']}\n"
        f"Descripcion: {fila['DESCRIPCION']}\n"
        f"Referencia: {fila['REFERENCIA']}\n"
        f"Ubicacion: {fila['UBICACION']}\n"
        f"Estado: {fila['ESTADO']}\n"
        f"Fecha: {fecha}"
    )


def _formatear_multiples(resultado, intencion: str) -> str:
    bloques = [f"Encontre {len(resultado)} muestra(s):"]

    for i, (_, fila) in enumerate(resultado.iterrows(), start=1):
        fecha = _fecha_texto(fila["FECHA_INGRESO"])
        if intencion == "ubicacion":
            detalle = f"Marca: {fila['MARCA']} | Ubicacion: {fila['UBICACION']}"
        elif intencion == "estado":
            detalle = f"Marca: {fila['MARCA']} | Estado: {fila['ESTADO']}"
        elif intencion == "fecha":
            detalle = f"Marca: {fila['MARCA']} | Fecha: {fecha}"
        elif intencion == "cliente":
            detalle = f"Cliente: {fila['CLIENTE']}"
        elif intencion == "descripcion":
            detalle = f"Descripcion: {fila['DESCRIPCION']}"
        elif intencion == "referencia":
            detalle = f"Referencia: {fila['REFERENCIA']}"
        elif intencion == "marca":
            detalle = f"Marca: {fila['MARCA']}"
        elif intencion == "informe":
            detalle = f"Informe: {fila.get('INFORME', 'N/E')} | Referencia: {fila['REFERENCIA']}"
        elif intencion == "cotizacion":
            detalle = f"Cotizacion: {fila.get('COTIZACION', 'N/E')} | Referencia: {fila['REFERENCIA']}"
        else:
            detalle = (
                f"Cliente: {fila['CLIENTE']} | Marca: {fila['MARCA']} | "
                f"Referencia: {fila['REFERENCIA']} | Ubicacion: {fila['UBICACION']} | Estado: {fila['ESTADO']}"
            )
        bloques.append(f"{i}. {detalle}")

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
        return f"La muestra esta en: {fila['UBICACION']}"
    if intencion == "estado":
        return f"El estado es: {fila['ESTADO']}"
    if intencion == "fecha":
        return f"La fecha de ingreso es: {_fecha_texto(fila['FECHA_INGRESO'])}"
    if intencion == "cliente":
        return f"El cliente es: {fila['CLIENTE']}"
    if intencion == "descripcion":
        return f"La descripcion es: {fila['DESCRIPCION']}"
    if intencion == "referencia":
        return f"La referencia es: {fila['REFERENCIA']}"
    if intencion == "marca":
        return f"La marca es: {fila['MARCA']}"
    if intencion == "informe":
        return f"Informe: {fila.get('INFORME', 'N/E')}"
    if intencion == "cotizacion":
        return f"Cotizacion: {fila.get('COTIZACION', 'N/E')}"

    return _resumen_fila(fila)
