def detectar_intencion(texto):
    """Detecta la intención principal en un texto dado.

    Normaliza acentos y puntuación, tokeniza y busca palabras clave
    para varias intenciones comunes. Devuelve una etiqueta de intención.
    """
    import unicodedata
    import re

    if not texto or not isinstance(texto, str):
        return "todo"

    # Normalizar: pasar a minúsculas, eliminar acentos y quitar puntuación
    texto_original = texto
    texto = texto.lower()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = re.sub(r"[^a-z0-9\s]", " ", texto)
    palabras = texto.split()

    # Listas ampliadas de palabras clave (incluir variantes y sin acentos)
    saludo = [
        "hola", "buenos", "buenos dias", "buenas", "buenas tardes",
        "buenas noches", "saludos", "hey", "buen dia"
    ]
    despedida = [
        "adios", "chao", "hasta luego", "nos vemos", "bye", "ciao",
        "hasta mañana", "hasta pronto", "nos vemos luego", "nos vemos mañana",
        "nos vemos pronto"
    ]
    agradecimiento = ["gracias", "muchas gracias", "mil gracias", "agradecido"]
    ayuda = [
        "ayuda", "ayudame", "como", "como puedo", "puedes ayudar", "instrucciones",
        "soporte", "necesito ayuda", "qué hago", "que hago"
    ]

    ubicacion = [
        "donde", "dondeesta", "donde estas", "ubicacion", "encuentra",
        "localizacion", "direccion", "sitio", "ubicado", "ubicada",
        "ubicados", "ubicadas", "ubicame", "donde esta", "donde se encuentra",
        "se encuentra", "esta", "en que lugar", "en que parte", "en que sección",
        "cual es la ubicacion", "en donde", "en donde esta", "en donde esta", "ubicación",
        "cuál es la ubicación", "posición", "lugar", "en qué lugar", "en qué parte",
        "en qué sección"
    ]

    estado = [
        "estado", "custodia", "almacenado", "almacenamiento", "proceso",
        "terminado", "finalizado", "pendiente", "enviado", "entregado",
        "recibido", "procesado", "en proceso"
    ]

    fecha = [
        "cuando", "cuándo", "fecha", "ingreso", "ingresó", "llego", "llegó",
        "recibio", "recibió", "recibida", "recibido", "recibieron",
        "entrada", "entró", "registro", "registró", "registrada", "registrado",
        "fecha ingreso", "fecha de ingreso", "fecha llegada", "fecha de llegada",
        "fecha recepción", "fecha de recepción", "cuando llegó", "cuándo llegó",
        "cuando ingreso", "cuándo ingresó", "cuando fue recibida", "cuándo fue recibida",
        "desde cuando", "desde cuándo", "día de ingreso", "día que llegó",
        "día de llegada", "momento de ingreso", "hora de ingreso",
        "cuando la recibieron", "qué día ingresó", "qué fecha tiene"
    ]

    cliente = [
        "cliente", "cliente de", "nombre", "quien es el cliente", "quien es cliente",
        "cliente es", "usuario"
    ]
    descripcion = [
        "descripcion", "detalle", "detalles", "producto", "equipo", "articulo",
        "tipo", "descripción"
    ]
    referencia = [
        "referencia", "ref", "codigo", "código", "folio", "modelo"
    ]
    referencia_externa = [
        "referencia externa", "externa", "codigo externo", "código externo"
    ]
    referencia_interna = [
        "referencia interna", "identificacion interna", "identificación interna",
        "id interna", "interna", "codigo interno", "código interno"
    ]
    informe = ["informe", "informe tecnico", "reporte", "reporte tecnico", "report", "I", "i"]
    cotizacion = ["cotizacion", "cotización", "presupuesto", "valor", "cotizar"]
    marca = ["marca", "etiqueta", "brand"]

    # Comprueba intenciones más específicas primero (saludo, despedida, gracias, ayuda)
    texto_join = " ".join(palabras)
    def contiene_lista(lista):
        # Coincidencia por palabra completa para elementos simples,
        # y coincidencia por frase para entradas que contienen espacios.
        for item in lista:
            if not item:
                continue
            if " " in item:
                if item in texto_join:
                    return True
            else:
                if item in palabras:
                    return True
        return False

    if contiene_lista(saludo):
        return "saludo"
    if contiene_lista(despedida):
        return "despedida"
    if contiene_lista(agradecimiento):
        return "agradecimiento"
    if contiene_lista(ayuda):
        return "ayuda"

    # Intenciones informativas
    if contiene_lista(ubicacion):
        return "ubicacion"
    if contiene_lista(estado):
        return "estado"
    if contiene_lista(fecha):
        return "fecha"
    if contiene_lista(cliente):
        return "cliente"
    if contiene_lista(descripcion):
        return "descripcion"
    if contiene_lista(referencia_interna):
        return "referencia_interna"
    if contiene_lista(referencia_externa):
        return "referencia_externa"
    if contiene_lista(referencia):
        return "referencia"
    if contiene_lista(marca):
        return "marca"
    if contiene_lista(informe):
        return "informe"
    if contiene_lista(cotizacion):
        return "cotizacion"

    # Si no se reconoce nada, devolver 'todo' como fallback
    return "todo"