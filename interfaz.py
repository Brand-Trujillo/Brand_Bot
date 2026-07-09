import re
import tkinter as tk
from tkinter import scrolledtext

from datos import cargar_datos
from buscador import buscar
from intenciones import detectar_intencion
from evolution_api import obtener_respuesta_evolution

# ======================================
# CARGAR DATOS
# ======================================

df = cargar_datos()

# ======================================
# VARIABLE GLOBAL - MUESTRA ACTUAL
# ======================================

muestra_actual = None

# ======================================
# COLORES - TEMA OSCURO MINIMALISTA
# ======================================

COLOR_FONDO = "#1a1a1a"
COLOR_ENTRADA = "#2d2d2d"
COLOR_TEXTO_CLARO = "#e0e0e0"
COLOR_BOT = "#10A37F"
COLOR_USUARIO = "#2563EB"
COLOR_USUARIO_BG = "#2b2b2b"

# ======================================
# VENTANA
# ======================================

ventana = tk.Tk()

ventana.title("Asistente virtual de muestras")

ventana.geometry("480x560")

ventana.configure(bg=COLOR_FONDO)

ventana.resizable(False, False)

# ======================================
# TITULO MINIMALISTA
# ======================================

# Encabezado superior eliminado por solicitud del usuario

# ======================================
# CHAT
# ======================================

area_chat = scrolledtext.ScrolledText(
    ventana,
    font=("Consolas", 11),
    bg=COLOR_FONDO,
    fg=COLOR_TEXTO_CLARO,
    relief="flat",
    wrap=tk.WORD,
    padx=12,
    pady=12,
    state="disabled",
    insertbackground=COLOR_TEXTO_CLARO
)

area_chat.pack(
    fill="both",
    expand=True,
    padx=15,
    pady=(0, 12)
)

# ======================================
# ENTRADA - CAMPO DE BUSQUEDA
# ======================================

entrada = tk.Entry(
    ventana,
    font=("Consolas", 12),
    relief="flat",
    bd=0,
    bg=COLOR_ENTRADA,
    fg=COLOR_TEXTO_CLARO,
    insertbackground=COLOR_TEXTO_CLARO
)

entrada.pack(
    fill="x",
    padx=15,
    pady=(0, 15)
)

entrada.focus()

# ======================================
# FUNCIONES DEL CHAT
# ======================================

def _resaltar_rango(start, end, tokens, tag="resaltado"):
    if not tokens:
        return
    for t in tokens:
        if not t:
            continue
        idx = start
        while True:
            pos = area_chat.search(t, idx, stopindex=end, nocase=1)
            if not pos:
                break
            area_chat.tag_add(tag, pos, f"{pos}+{len(t)}c")
            idx = f"{pos}+1c"


def escribir_bot(texto, tokens=None):

    area_chat.config(state="normal")

    # Insertar emoji y nombre del bot
    area_chat.insert(tk.END, "\n💬 ", "emoji_bot")
    area_chat.insert(tk.END, "Brand_Bot\n", "bot_nombre")

    # Insertar texto y resaltar si hay tokens
    start = area_chat.index(tk.END)
    area_chat.insert(tk.END, texto + "\n\n", "bot_texto")
    end = area_chat.index(tk.END)
    _resaltar_rango(start, end, tokens)

    area_chat.config(state="disabled")
    area_chat.see(f"{start} -4 lines")


def escribir_usuario(texto):

    area_chat.config(state="normal")

    start = area_chat.index(tk.END)
    area_chat.insert(
        tk.END,
        "\n👨 ",
        "emoji_usuario"
    )
    area_chat.insert(
        tk.END,
        "Tú\n",
        "usuario_nombre"
    )

    area_chat.insert(
        tk.END,
        texto + "\n\n",
        "usuario_texto"
    )

    area_chat.config(state="disabled")
    area_chat.see(start)


# ======================================
# ESTILOS DEL CHAT - TEMA OSCURO CON COLORES
# ======================================

area_chat.tag_config(
    "bot_nombre",
    foreground=COLOR_BOT,
    font=("Consolas", 11, "bold")
)

area_chat.tag_config(
    "usuario_nombre",
    foreground=COLOR_USUARIO,
    font=("Consolas", 11, "bold"),
    background=COLOR_USUARIO_BG
)

area_chat.tag_config(
    "bot_texto",
    foreground=COLOR_TEXTO_CLARO,
    font=("Consolas", 11)
)

# Tag para resaltado de tokens en resultados
area_chat.tag_config("resaltado", foreground="#FFD54F", font=("Consolas", 11, "bold"))
area_chat.tag_config("campo_destacado", foreground="#00E5FF", font=("Consolas", 11, "bold"))

area_chat.tag_config(
    "usuario_texto",
    foreground=COLOR_TEXTO_CLARO,
    font=("Consolas", 11),
    background=COLOR_USUARIO_BG
)

# Colores para emojis
area_chat.tag_config("emoji_cliente", foreground="#3B82F6")      # Azul
area_chat.tag_config("emoji_descripcion", foreground="#F59E0B")  # Naranja
area_chat.tag_config("emoji_marca", foreground="#22C55E")        # Verde claro
area_chat.tag_config("emoji_ubicacion", foreground="#EF4444")    # Rojo
area_chat.tag_config("emoji_estado", foreground="#A855F7")       # Purpura
area_chat.tag_config("emoji_fecha", foreground="#06B6D4")        # Cyan
area_chat.tag_config("emoji_usuario", foreground="#2563EB")      # Azul oscuro
area_chat.tag_config("emoji_usuario", background=COLOR_USUARIO_BG)
area_chat.tag_config("emoji_bot", foreground="#10A37F")          # Verde
area_chat.tag_config("emoji_informe", foreground="#8B5CF6")     # Lila
area_chat.tag_config("emoji_cotizacion", foreground="#F97316")  # Naranja fuerte
area_chat.tag_config("emoji_info", foreground="#94A3B8")  # Gris informativo

# ======================================
# MENSAJE DE BIENVENIDA
# ======================================

def bienvenida():
    escribir_bot("Hola, soy el asistente virtual de Brandon.\nÉl me creo para ayudarte a buscar información sobre las muestras que se encuentran en el laboratorio.\n\n" \
    "Puedes consultarme sobre:\n• Cliente\n• Muestra\n• Marca\n• Estado\n• Ubicacion\n• Fecha de ingreso\n• Informe\n• Cotización")

# ======================================
# ESCRIBIR MENSAJE CON EMOJIS COLOREADOS
# ======================================

def escribir_bot_colores(lineas, tokens=None, meta=None):
    """Escribe un mensaje del bot con emojis coloreados.
    lineas: lista de tuplas (emoji_tag, emoji_texto, texto)
    tokens: lista de tokens a resaltar dentro del bloque insertado
    """
    area_chat.config(state="normal")

    # Insertar emoji y nombre del bot
    area_chat.insert(tk.END, "\n💬 ", "emoji_bot")
    area_chat.insert(tk.END, "Brand_Bot\n", "bot_nombre")
    
    start = area_chat.index(tk.END)
    for emoji_tag, emoji_texto, texto in lineas:
        area_chat.insert(tk.END, emoji_texto, emoji_tag)
        area_chat.insert(tk.END, texto, "bot_texto")

    area_chat.insert(tk.END, "\n")
    end = area_chat.index(tk.END)
    _resaltar_rango(start, end, tokens)

    area_chat.config(state="disabled")
    area_chat.see(f"{start} -4 lines")
    return start, end


def pregunta_contiene_identificador(pregunta):
    texto = pregunta.lower()

    # Si hay palabra de muestra/referencia/informe + número, hablamos de otra muestra
    if re.search(r'\b(?:muestra|referencia|ref|informe|informe tecnico|cotizacion|cotización|presupuesto|marca|cliente|descripcion)\b', texto) and re.search(r'\d+', texto):
        return True

    # Patrones directos de identificador
    if re.search(r'(?i)\b[iI]\s*0*(\d+)\b', pregunta):
        return True
    if re.search(r'(?i)\b[cC]\s*0*(\d+)\b', pregunta):
        return True

    # Cambio de muestra explícito
    if re.search(r'\b(otra|nuevo|nueva|cambiar|cambia|cambio)\b', texto) and re.search(r'\d+', texto):
        return True

    return False

# ======================================
# CONSULTAR INFORMACION - CONVERSACION CONTINUA
# ======================================

def consultar(event=None):
    global muestra_actual

    pregunta = entrada.get().strip()

    if pregunta == "":
        return

    escribir_usuario(pregunta)
    entrada.delete(0, tk.END)

    # Palabras clave para preguntas sobre la muestra actual
    palabras_clave_muestra = [
        "donde", "dónde", "ubicacion", "ubicación", "esta", "está", 
        "estado", "cuando", "cuándo", "fecha", "ingreso", "marca", "y el", "y la"
    ]
    # aceptar también consultas directas sobre informe y cotizacion
    palabras_clave_muestra += ["informe", "cotizacion", "cotización", "presupuesto", "marca"]
    
    # Detectar si es una pregunta sobre la muestra actual
    es_pregunta_muestra = any(palabra in pregunta.lower() for palabra in palabras_clave_muestra)
    es_pregunta_muestra_actual = (
        muestra_actual is not None
        and es_pregunta_muestra
        and not pregunta_contiene_identificador(pregunta)
    )
    
    # Si tiene muestra actual y es una pregunta sobre ella
    if es_pregunta_muestra_actual:
        intencion = detectar_intencion(pregunta)
        
        fecha = muestra_actual.get("FECHA_INGRESO")
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")
        
        if intencion == "ubicacion":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {muestra_actual['UBICACION']}\n")
            ]
            escribir_bot_colores(lineas)

        elif intencion == "estado":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {muestra_actual['ESTADO']}\n")
            ]
            escribir_bot_colores(lineas)

        elif intencion == "fecha":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            escribir_bot_colores(lineas)
        elif intencion == "cliente":
            lineas = [
                ("emoji_cliente", "👨 ", f"Cliente: {muestra_actual['CLIENTE']}\n")
            ]
            escribir_bot_colores(lineas)
        elif intencion == "descripcion":
            lineas = [
                ("emoji_descripcion", "📋 ", f"Descripcion: {muestra_actual['DESCRIPCION']}\n")
            ]
            escribir_bot_colores(lineas)
        elif intencion == "referencia":
            lineas = [
                ("emoji_descripcion", "🔗 ", f"Referencia: {muestra_actual['REFERENCIA']}\n")
            ]
            escribir_bot_colores(lineas)
        elif intencion == "marca":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n")
            ]
            escribir_bot_colores(lineas)
        elif intencion == "informe":
            lineas = [
                ("emoji_informe", "📄 ", f"Informe: {muestra_actual.get('INFORME','')}\n"),
                ("emoji_cliente", "👨 ", f"Cliente: {muestra_actual['CLIENTE']}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_descripcion", "📋 ", f"Descripcion: {muestra_actual['DESCRIPCION']}\n"),
                ("emoji_descripcion", "🔗 ", f"Referencia: {muestra_actual['REFERENCIA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {muestra_actual['UBICACION']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {muestra_actual['ESTADO']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            start, end = escribir_bot_colores(lineas)
            _resaltar_rango(start, end, [str(muestra_actual.get('INFORME',''))], tag="campo_destacado")
        elif intencion == "cotizacion":
            lineas = [
                ("emoji_cotizacion", "💰 ", f"Cotizacion: {muestra_actual.get('COTIZACION','')}\n"),
                ("emoji_cliente", "👨 ", f"Cliente: {muestra_actual['CLIENTE']}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_descripcion", "📋 ", f"Descripcion: {muestra_actual['DESCRIPCION']}\n"),
                ("emoji_descripcion", "🔗 ", f"Referencia: {muestra_actual['REFERENCIA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {muestra_actual['UBICACION']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {muestra_actual['ESTADO']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            start, end = escribir_bot_colores(lineas)
            _resaltar_rango(start, end, [str(muestra_actual.get('COTIZACION',''))], tag="campo_destacado")
        
        else:
            lineas = [
                ("emoji_cliente", "👨 ", f"Cliente: {muestra_actual['CLIENTE']}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_descripcion", "📋 ", f"Descripcion: {muestra_actual['DESCRIPCION']}\n"),
                ("emoji_informe", "📄 ", f"Informe: {muestra_actual.get('INFORME','')}\n"),
                ("emoji_cotizacion", "💰 ", f"Cotizacion: {muestra_actual.get('COTIZACION','')}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {muestra_actual['MARCA']}\n"),
                ("emoji_descripcion", "🔗 ", f"Referencia: {muestra_actual['REFERENCIA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {muestra_actual['UBICACION']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {muestra_actual['ESTADO']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            escribir_bot_colores(lineas)
        return
    
    # Si no, detectar intención y manejar respuestas conversacionales primero
    intencion = detectar_intencion(pregunta)

    # Manejar intenciones conversacionales antes de buscar en los datos
    if intencion == "saludo":
        escribir_bot("Hola 👋 ¿En qué puedo ayudarte?")
        return
    if intencion == "despedida":
        escribir_bot("Hasta luego 👋")
        return
    if intencion == "agradecimiento":
        escribir_bot("Por nada, para eso me crearon 😊")
        return
    if intencion == "ayuda":
        escribir_bot("Brandon me creo para ayudarte a buscar muestras por Cliente, Referencia, Descripcion, Estado o Ubicacion. Prueba: '¿dónde está la muestra X?' o 'estado de la muestra referencia Y'")
        return

    # Buscar en el Excel
    resultado, meta = buscar(df, pregunta)

    # Si no encuentra nada, usar Evolution API como fallback para preguntas generales
    if resultado.empty:
        respuesta_api = obtener_respuesta_evolution(
            pregunta,
            system_prompt=(
                "Eres un asistente de soporte para un sistema de control de muestras de laboratorio. "
                "Responde con amabilidad y explica que no encontraste una muestra local si corresponde."
            )
        )
        escribir_bot(respuesta_api)
        return

    # Mostrar resultados
    for _, fila in resultado.iterrows():
        
        # Guardar muestra actual
        muestra_actual = {
            "CLIENTE": fila["CLIENTE"],
            "MARCA": fila["MARCA"],
            "DESCRIPCION": fila["DESCRIPCION"],
            "INFORME": fila.get("INFORME", ""),
            "COTIZACION": fila.get("COTIZACION", ""),
            "REFERENCIA": fila["REFERENCIA"],
            "UBICACION": fila["UBICACION"],
            "ESTADO": fila["ESTADO"],
            "FECHA_INGRESO": fila["FECHA_INGRESO"]
        }

        fecha = fila["FECHA_INGRESO"]
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")

        if intencion == "ubicacion":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {fila['UBICACION']}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)

        elif intencion == "estado":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {fila['ESTADO']}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)

        elif intencion == "fecha":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)
        elif intencion == "cliente":
            lineas = [
                ("emoji_cliente", "👨 ", f"Cliente: {fila['CLIENTE']}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)
        elif intencion == "descripcion":
            lineas = [
                ("emoji_descripcion", "📋 ", f"Descripcion: {fila['DESCRIPCION']}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)
        elif intencion == "referencia":
            lineas = [
                ("emoji_descripcion", "🔗 ", f"Referencia: {fila['REFERENCIA']}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)
        elif intencion == "marca":
            lineas = [
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)
        elif intencion == "informe":
            lineas = [
                ("emoji_informe", "📄 ", f"Informe: {fila.get('INFORME','')}\n"),
                ("emoji_cliente", "👨 ", f"Cliente: {fila['CLIENTE']}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n"),
                ("emoji_descripcion", "📋 ", f"Descripcion: {fila['DESCRIPCION']}\n"),
                ("emoji_cotizacion", "💰 ", f"Cotizacion: {fila.get('COTIZACION','')}\n"),
                ("emoji_descripcion", "🔗 ", f"Referencia: {fila['REFERENCIA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {fila['UBICACION']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {fila['ESTADO']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            start, end = escribir_bot_colores(lineas, tokens=meta.get('tokens'))
            _resaltar_rango(start, end, [str(fila.get('INFORME',''))], tag="campo_destacado")
        elif intencion == "cotizacion":
            lineas = [
                ("emoji_cotizacion", "💰 ", f"Cotizacion: {fila.get('COTIZACION','')}\n"),
                ("emoji_cliente", "👨 ", f"Cliente: {fila['CLIENTE']}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n"),
                ("emoji_descripcion", "📋 ", f"Descripcion: {fila['DESCRIPCION']}\n"),
                ("emoji_descripcion", "🔗 ", f"Referencia: {fila['REFERENCIA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {fila['UBICACION']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {fila['ESTADO']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            start, end = escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)
            _resaltar_rango(start, end, [str(fila.get('COTIZACION',''))], tag="campo_destacado")

        else:
            lineas = [
                ("emoji_cliente", "👨 ", f"Cliente: {fila['CLIENTE']}\n"),
                ("emoji_marca", "🔖 ", f"Marca: {fila['MARCA']}\n"),
                ("emoji_descripcion", "📋 ", f"Descripcion: {fila['DESCRIPCION']}\n"),
                ("emoji_informe", "📄 ", f"Informe: {fila.get('INFORME','')}\n"),
                ("emoji_cotizacion", "💰 ", f"Cotizacion: {fila.get('COTIZACION','')}\n"),
                ("emoji_descripcion", "🔗 ", f"Referencia: {fila['REFERENCIA']}\n"),
                ("emoji_ubicacion", "📌 ", f"Ubicacion: {fila['UBICACION']}\n"),
                ("emoji_estado", "⚡ ", f"Estado: {fila['ESTADO']}\n"),
                ("emoji_fecha", "🕐 ", f"Fecha: {fecha}\n")
            ]
            escribir_bot_colores(lineas, tokens=meta.get('tokens'), meta=meta)

# ======================================
# VINCULAR ENTRADA
# ======================================

entrada.bind("<Return>", consultar)

# ======================================
# INICIAR CHATBOT
# ======================================

bienvenida()

ventana.mainloop()
