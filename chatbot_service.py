from datos import cargar_datos
from buscador import buscar
from intenciones import detectar_intencion
from evolution_api import obtener_respuesta_evolution
from utilidades import extraer_busqueda

# Mantiene un unico dataset en memoria para todas las peticiones.
df = cargar_datos()


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
    if intencion == "ubicacion":
        fila = resultado.iloc[0]
        return f"La muestra esta en: {fila['UBICACION']}"
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
        return f"La descripcion es: {fila['DESCRIPCION']}"
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
        return f"Cotizacion: {fila.get('COTIZACION', 'N/E')}"

    fila = resultado.iloc[0]
    fecha = fila["FECHA_INGRESO"]
    if hasattr(fecha, "strftime"):
        fecha = fecha.strftime("%d/%m/%Y")
    return (
        f"Encontre una muestra para {fila['CLIENTE']}\n"
        f"Marca: {fila['MARCA']}\n"
        f"Descripcion: {fila['DESCRIPCION']}\n"
        f"Referencia: {fila['REFERENCIA']}\n"
        f"Ubicacion: {fila['UBICACION']}\n"
        f"Estado: {fila['ESTADO']}\n"
        f"Fecha: {fecha}"
    )
