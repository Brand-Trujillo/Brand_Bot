from datos import cargar_datos
from buscador import buscar
from intenciones import detectar_intencion
from evolution_api import obtener_respuesta_evolution
from utilidades import extraer_busqueda
import pandas as pd


def _ordenar_recientes(resultado):
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
        ascending=[False, False],
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


def _resumen_fila(fila) -> str:
    return (
        f"Cliente: {_valor_texto(fila.get('CLIENTE'))}\n"
        f"Marca: {_marca_texto(fila)}\n"
        f"Descripcion: {_valor_texto(fila.get('DESCRIPCION'))}\n"
        f"Referencia / Modelo: {_valor_texto(fila.get('REFERENCIA_MODELO'))}\n"
        f"Referencia externa: {_valor_texto(fila.get('REFERENCIA_EXTERNA'))}\n"
        f"Referencia interna: {_valor_texto(fila.get('REFERENCIA_INTERNA'))}\n"
        f"N° muestras: {_valor_texto(fila.get('NUMERO'))}\n"
        f"Informe: {_valor_texto(fila.get('INFORME'))}\n"
        f"Cotizacion: {_valor_texto(fila.get('COTIZACION'))}"
    )


def _campo_por_intencion(fila, intencion: str) -> str:
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
        return f"Informe: {_valor_texto(fila.get('INFORME'))}"
    if intencion == "cotizacion":
        return f"Cotizacion: {_valor_texto(fila.get('COTIZACION'))}"

    return (
        f"Estado: {_valor_texto(fila.get('ESTADO'))} | "
        f"Ubicacion: {_valor_texto(fila.get('UBICACION'))} | "
        f"Fecha ingreso: {fecha}"
    )


def _resumen_corto(fila, intencion: str) -> str:
    return (
        f"Cliente: {_valor_texto(fila.get('CLIENTE'))} | "
        f"Ref. interna: {_valor_texto(fila.get('REFERENCIA_INTERNA') or fila.get('ID'))} | "
        f"Informe: {_valor_texto(fila.get('INFORME'))} | "
        f"Cotizacion: {_valor_texto(fila.get('COTIZACION'))}\n"
        f"{_campo_por_intencion(fila, intencion)}"
    )


def _formatear_multiples(resultado, intencion: str) -> str:
    total = len(resultado)
    max_items = 8
    ordenado = _ordenar_recientes(resultado)
    recorte = ordenado.head(max_items)
    bloques = [f"Encontre {total} muestra(s) que coinciden."]
    if total > max_items:
        bloques.append(f"Te muestro las primeras {max_items}. Si quieres, te ayudo a filtrar por cliente, estado, informe o cotizacion.")

    for i, (_, fila) in enumerate(recorte.iterrows(), start=1):
        detalle = _resumen_corto(fila, intencion)
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

    # Recarga en cada consulta para reflejar cambios del Excel al instante.
    df = cargar_datos()

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

    return (
        "Encontre 1 muestra que coincide.\n"
        f"{_resumen_corto(fila, intencion)}"
    )


def responder_consulta_burbujas(consulta: str):
    if not consulta or not isinstance(consulta, str):
        return ["Hola, escribe tu consulta para buscar muestras."]

    consulta = consulta.strip()
    if consulta.lower() in {"salir", "exit"}:
        return ["Hasta luego 👋"]

    if consulta.lower() in {"ayuda", "help"}:
        return [
            "Puedo ayudarte a buscar muestras por cliente, descripcion, referencia, estado, ubicacion, marca, informe o cotizacion."
        ]

    # Recarga en cada consulta para reflejar cambios del Excel al instante.
    df = cargar_datos()

    busqueda = extraer_busqueda(consulta)
    resultado, _meta = buscar(df, busqueda)

    if resultado.empty:
        return [
            obtener_respuesta_evolution(
                consulta,
                system_prompt=(
                    "Eres un asistente de soporte para un sistema de control de muestras de laboratorio. "
                    "Responde de forma amable y clara cuando no encuentres una muestra local."
                ),
            )
        ]

    intencion = detectar_intencion(consulta)
    if len(resultado) > 1:
        total = len(resultado)
        max_items = 8
        ordenado = _ordenar_recientes(resultado)
        recorte = ordenado.head(max_items)
        bloques = [f"Encontre {total} muestra(s) que coinciden."]
        if total > max_items:
            bloques.append(
                f"Te muestro las primeras {max_items}. Si quieres, te ayudo a filtrar por cliente, estado, informe o cotizacion."
            )
        for i, (_, fila) in enumerate(recorte.iterrows(), start=1):
            bloques.append(f"{i}.\n{_resumen_fila(fila)}")
        return bloques

    fila = resultado.iloc[0]
    return ["Encontre 1 muestra que coincide.", _resumen_fila(fila), _campo_por_intencion(fila, intencion)]
