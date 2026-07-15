import pandas as pd
import os
import sys
import io
import urllib.parse
import urllib.request
import unicodedata

# Nombre del archivo de datos (se asume en la misma carpeta que el ejecutable/archivo)
ARCHIVO = "Control de muestras_2026.xlsx"
SHEET_NAME = "CONTROL_MUESTRAS_2026"
DEFAULT_ONEDRIVE_XLSX_URL = (
    "https://ainsp.sharepoint.com/:x:/r/sites/TodoNYCE/nycecolombia/"
    "HSQ%20Interno/Muestras%20en%20custodia/F3T09-03%20Control%20de%20"
    "muestras_2026.xlsx?d=w34336858a30b4b0a98962963a3631f0f&csf=1&web=1&e=r7iItR"
)

# Fuente cargada en memoria para diagnostico
LAST_DATA_SOURCE = "unknown"


def obtener_ruta_archivo_equipos() -> str:
    """Devuelve la ruta del Excel opcional de control de equipos.

    Se usa solo si se define EQUIPOS_XLSX_PATH.
    """
    custom_path = os.getenv("EQUIPOS_XLSX_PATH", "").strip()
    if custom_path:
        return custom_path

    # Auto-detección local para facilitar uso sin variables de entorno.
    # Si existe Equipos.xlsx en la raíz del proyecto, se usa como segunda fuente.
    default_local = _resource_path("Equipos.xlsx")
    if os.path.exists(default_local):
        return default_local
    return ""


def obtener_ruta_archivo_local() -> str:
    """Devuelve la ruta del Excel local usado por la app.

    Si existe la variable DATOS_XLSX_PATH se usa esa ruta explícita.
    Esto permite apuntar al archivo actualizado real (por ejemplo OneDrive sincronizado).
    """
    custom_path = os.getenv("DATOS_XLSX_PATH", "").strip()
    if custom_path:
        return custom_path
    return _resource_path(ARCHIVO)


def _resource_path(rel_path: str) -> str:
    """Devuelve la ruta absoluta del recurso, compatible con PyInstaller onefile.

    En modo desarrollo devuelve la ruta relativa al directorio del script.
    En modo bundle con PyInstaller devuelve la ruta dentro de _MEIPASS.
    """
    if getattr(sys, "frozen", False):
        base_path = sys._MEIPASS  # type: ignore
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, rel_path)


def _onedrive_download_url(url: str) -> str:
    """Convierte una URL de OneDrive/SharePoint a descarga directa cuando es posible."""
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)

    # Share links de OneDrive/SharePoint suelen aceptar download=1
    if "download" not in query:
        query["download"] = ["1"]

    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def _cargar_desde_onedrive(url: str, sheet_name: str = "", header: int = 6) -> pd.DataFrame:
    """Descarga un Excel desde OneDrive y lo carga en memoria.

    Esto evita problemas de bloqueo cuando el archivo esta abierto localmente.
    """
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()

    buffer = io.BytesIO(data)
    df = pd.read_excel(
        buffer,
        sheet_name=sheet_name or 0,
        header=header,
    )
    return df


def _leer_excel_local(path: str, sheet_name: str = "", header: int = 6) -> pd.DataFrame:
    """Lee un Excel local con fallback de hoja cuando no coincide el nombre."""
    if sheet_name:
        try:
            return pd.read_excel(path, sheet_name=sheet_name, header=header)
        except Exception:
            pass

    # Fallback robusto: primera hoja disponible.
    xls = pd.ExcelFile(path)
    if not xls.sheet_names:
        raise ValueError(f"El archivo no contiene hojas: {path}")
    return pd.read_excel(path, sheet_name=xls.sheet_names[0], header=header)


def _texto_normalizado(valor) -> str:
    texto = str(valor or "").strip().upper()
    texto = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    texto = " ".join(texto.split())
    return texto


def _detectar_header_equipos(path: str, sheet_name: str = "") -> tuple[str, int]:
    xls = pd.ExcelFile(path)
    hoja = sheet_name if sheet_name and sheet_name in xls.sheet_names else xls.sheet_names[0]
    preview = pd.read_excel(path, sheet_name=hoja, header=None, nrows=20)
    keywords = {"EQUIPO", "IDENTIFICACION INTERNA", "SERIE", "MARCA", "MODELO"}

    best_idx = 0
    best_score = -1
    for idx in range(len(preview.index)):
        row = [_texto_normalizado(v) for v in preview.iloc[idx].tolist()]
        score = sum(1 for key in keywords if key in row)
        if score > best_score:
            best_score = score
            best_idx = idx
    return hoja, best_idx


def _normalizar_dataframe_equipos(path: str, sheet_name: str = "") -> pd.DataFrame:
    hoja, header_idx = _detectar_header_equipos(path, sheet_name)
    df = pd.read_excel(path, sheet_name=hoja, header=header_idx)
    df = df.dropna(how="all").reset_index(drop=True)

    rename_map = {}
    for col in df.columns:
        norm = _texto_normalizado(col)
        if norm == "EQUIPO":
            rename_map[col] = "EQUIPO"
        elif norm == "IDENTIFICACION INTERNA":
            rename_map[col] = "REFERENCIA_INTERNA"
        elif norm == "SERIE":
            rename_map[col] = "SERIE"
        elif norm == "MARCA":
            rename_map[col] = "MARCA"
        elif norm == "MODELO":
            rename_map[col] = "REFERENCIA_MODELO"
        elif norm in {"ULTIMA CALIBRACION", "ULTIMA CALIBRACION "}:
            rename_map[col] = "ULTIMA_CALIBRACION"
        elif norm == "CALIBRADO POR":
            rename_map[col] = "CALIBRADO_POR"
        elif norm == "PROXIMA CALIBRACION":
            rename_map[col] = "PROXIMA_CALIBRACION"
        elif norm == "TIEMPO DE ALARMA":
            rename_map[col] = "TIEMPO_ALARMA"
        elif norm == "ESTADO DE CALIBRACION":
            rename_map[col] = "ESTADO_CALIBRACION"

    df = df.rename(columns=rename_map)

    for col in [
        "EQUIPO",
        "REFERENCIA_INTERNA",
        "SERIE",
        "MARCA",
        "MAGNITUD",
        "REFERENCIA_MODELO",
        "ULTIMA_CALIBRACION",
        "CALIBRADO_POR",
        "PROXIMA_CALIBRACION",
        "TIEMPO_ALARMA",
        "ESTADO_CALIBRACION",
    ]:
        if col not in df.columns:
            df[col] = "N/E"

    # Alias para reutilizar buscador actual.
    df["CLIENTE"] = df["EQUIPO"]
    df["DESCRIPCION"] = df["EQUIPO"]
    df["REFERENCIA_EXTERNA"] = df["SERIE"]
    df["IDENTIFICACION_INTERNA"] = df["REFERENCIA_INTERNA"]
    df["MAGNITUD"] = df.get("MAGNITUD", "N/E")
    df["ESTADO"] = df["ESTADO_CALIBRACION"]
    df["INFORME"] = df.get("INFORME", "N/E")
    df["COTIZACION"] = df.get("COTIZACION", "N/E")
    df["UBICACION"] = df.get("UBICACION", "N/E")
    df["NUMERO"] = df.get("NUMERO", "N/E")
    df["FECHA_INGRESO"] = df.get("FECHA_INGRESO", pd.NA)
    df["TIPO_REGISTRO"] = "equipo"

    return df


def _normalizar_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza estructura y aliases esperados por el buscador/chat."""
    # Eliminar las dos filas que sobran
    df = df.iloc[2:]
    # Reiniciar el índice
    df = df.reset_index(drop=True)

    # Renombrar columnas según la estructura real del libro.
    # En el formato actual hay 16 columnas útiles.
    # Mapeo validado contra filas recientes del archivo.
    if len(df.columns) == 16:
        df.columns = [
            "ITEM",
            "FECHA_INGRESO",
            "CLIENTE",
            "DESCRIPCION",
            "MARCA",
            "REFERENCIA_MODELO",
            "REFERENCIA_EXTERNA",
            "REFERENCIA_INTERNA",
            "ID",
            "AÑO",
            "INFORME",
            "NUMERO",
            "COTIZACION",
            "UBICACION",
            "ESTADO",
            "OBSERVACIONES",
        ]
    else:
        # Compatibilidad con estructuras antiguas o empaquetadas.
        columnas_base = [
            "ITEM",
            "FECHA_INGRESO",
            "CLIENTE",
            "DESCRIPCION",
            "MARCA",
            "REFERENCIA",
            "SERIE",
            "ID",
            "AÑO",
            "INFORME",
            "NUMERO",
            "COTIZACION",
            "UBICACION",
            "ESTADO",
            "FECHA_ENTREGA",
            "OBSERVACIONES",
        ]
        n = len(df.columns)
        if n <= len(columnas_base):
            df.columns = columnas_base[:n]
        else:
            extra = [f"EXTRA_{i}" for i in range(n - len(columnas_base))]
            df.columns = columnas_base + extra

    # limpiar los nombres de las columnas
    df.columns = df.columns.str.strip()

    # Normalizar MARCA: quitar espacios en blanco y usar N/E cuando no haya valor
    if "MARCA" not in df.columns:
        df["MARCA"] = "N/E"
    df["MARCA"] = df["MARCA"].astype("string").str.strip()
    df["MARCA"] = df["MARCA"].replace({"": pd.NA}).fillna("N/E")

    # Alias de compatibilidad para el resto del sistema.
    if "REFERENCIA" not in df.columns and "REFERENCIA_EXTERNA" in df.columns:
        df["REFERENCIA"] = df["REFERENCIA_EXTERNA"]
    if "SERIE" not in df.columns and "REFERENCIA_INTERNA" in df.columns:
        df["SERIE"] = df["REFERENCIA_INTERNA"]
    if "REFERENCIA_MODELO" not in df.columns:
        df["REFERENCIA_MODELO"] = "N/E"
    if "REFERENCIA_EXTERNA" not in df.columns and "REFERENCIA" in df.columns:
        df["REFERENCIA_EXTERNA"] = df["REFERENCIA"]
    if "REFERENCIA_INTERNA" not in df.columns and "SERIE" in df.columns:
        df["REFERENCIA_INTERNA"] = df["SERIE"]
    if "IDENTIFICACION_INTERNA" not in df.columns and "REFERENCIA_INTERNA" in df.columns:
        df["IDENTIFICACION_INTERNA"] = df["REFERENCIA_INTERNA"]

    # Normaliza referencias internas tipo 'yyyy-mm-dd-xx' al anio real de FECHA_INGRESO.
    if "REFERENCIA_INTERNA" in df.columns and "FECHA_INGRESO" in df.columns:
        fechas = pd.to_datetime(df["FECHA_INGRESO"], errors="coerce")
        serie_ref = df["REFERENCIA_INTERNA"].astype(str)
        mask = serie_ref.str.lower().str.startswith("yyyy-") & fechas.notna()
        if mask.any():
            years = fechas.dt.year.astype("Int64").astype(str)
            sufijo = serie_ref[mask].str[4:]
            df.loc[mask, "REFERENCIA_INTERNA"] = years[mask] + sufijo
            df.loc[mask, "IDENTIFICACION_INTERNA"] = df.loc[mask, "REFERENCIA_INTERNA"]

            df["TIPO_REGISTRO"] = "muestra"

    return df


def cargar_datos():
    global LAST_DATA_SOURCE
    # Por defecto usamos el archivo local para que coincida con el Excel del equipo.
    # Para usar OneDrive, definir ONEDRIVE_XLSX_URL explicitamente.
    onedrive_url = os.getenv("ONEDRIVE_XLSX_URL", "").strip()
    equipos_onedrive_url = os.getenv("EQUIPOS_ONEDRIVE_XLSX_URL", "").strip()

    if onedrive_url:
        try:
            df = _cargar_desde_onedrive(_onedrive_download_url(onedrive_url), sheet_name=SHEET_NAME, header=6)
            LAST_DATA_SOURCE = "onedrive"
        except Exception:
            # Fallback seguro: continuar con archivo local si la URL falla.
            archivo_path = obtener_ruta_archivo_local()
            df = _leer_excel_local(archivo_path, sheet_name=SHEET_NAME, header=6)
            LAST_DATA_SOURCE = "local_fallback"
    else:
        archivo_path = obtener_ruta_archivo_local()
        df = _leer_excel_local(archivo_path, sheet_name=SHEET_NAME, header=6)
        LAST_DATA_SOURCE = "local"

    df = _normalizar_dataframe(df)

    # Carga opcional de un segundo Excel (control de equipos) y lo une al dataset principal.
    if equipos_onedrive_url:
        try:
            equipos_sheet = os.getenv("EQUIPOS_SHEET_NAME", SHEET_NAME).strip()
            equipos_buffer = _cargar_desde_onedrive(
                _onedrive_download_url(equipos_onedrive_url),
                sheet_name=equipos_sheet,
                header=0,
            )
            df_equipos = equipos_buffer.dropna(how="all").reset_index(drop=True)
            df_equipos = df_equipos.rename(columns={col: col for col in df_equipos.columns})
            temp_path = None
            rename_map = {}
            for col in df_equipos.columns:
                norm = _texto_normalizado(col)
                if norm == "EQUIPO":
                    rename_map[col] = "EQUIPO"
                elif norm == "IDENTIFICACION INTERNA":
                    rename_map[col] = "REFERENCIA_INTERNA"
                elif norm == "SERIE":
                    rename_map[col] = "SERIE"
                elif norm == "MARCA":
                    rename_map[col] = "MARCA"
                elif norm == "MAGNITUD":
                    rename_map[col] = "MAGNITUD"
                elif norm == "MODELO":
                    rename_map[col] = "REFERENCIA_MODELO"
                elif norm in {"ULTIMA CALIBRACION", "ULTIMA CALIBRACION "}:
                    rename_map[col] = "ULTIMA_CALIBRACION"
                elif norm == "CALIBRADO POR":
                    rename_map[col] = "CALIBRADO_POR"
                elif norm == "PROXIMA CALIBRACION":
                    rename_map[col] = "PROXIMA_CALIBRACION"
                elif norm == "TIEMPO DE ALARMA":
                    rename_map[col] = "TIEMPO_ALARMA"
                elif norm == "ESTADO DE CALIBRACION":
                    rename_map[col] = "ESTADO_CALIBRACION"

            df_equipos = df_equipos.rename(columns=rename_map)
            for col in [
                "EQUIPO",
                "REFERENCIA_INTERNA",
                "SERIE",
                "MARCA",
                "MAGNITUD",
                "REFERENCIA_MODELO",
                "ULTIMA_CALIBRACION",
                "CALIBRADO_POR",
                "PROXIMA_CALIBRACION",
                "TIEMPO_ALARMA",
                "ESTADO_CALIBRACION",
            ]:
                if col not in df_equipos.columns:
                    df_equipos[col] = "N/E"

            df_equipos["CLIENTE"] = df_equipos["EQUIPO"]
            df_equipos["DESCRIPCION"] = df_equipos["EQUIPO"]
            df_equipos["REFERENCIA_EXTERNA"] = df_equipos["SERIE"]
            df_equipos["IDENTIFICACION_INTERNA"] = df_equipos["REFERENCIA_INTERNA"]
            df_equipos["MAGNITUD"] = df_equipos.get("MAGNITUD", "N/E")
            df_equipos["ESTADO"] = df_equipos["ESTADO_CALIBRACION"]
            df_equipos["INFORME"] = df_equipos.get("INFORME", "N/E")
            df_equipos["COTIZACION"] = df_equipos.get("COTIZACION", "N/E")
            df_equipos["UBICACION"] = df_equipos.get("UBICACION", "N/E")
            df_equipos["NUMERO"] = df_equipos.get("NUMERO", "N/E")
            df_equipos["FECHA_INGRESO"] = df_equipos.get("FECHA_INGRESO", pd.NA)
            df_equipos["TIPO_REGISTRO"] = "equipo"
            df = pd.concat([df, df_equipos], ignore_index=True, sort=False)
            LAST_DATA_SOURCE = f"{LAST_DATA_SOURCE}+equipos_onedrive"
        except Exception:
            LAST_DATA_SOURCE = f"{LAST_DATA_SOURCE}+equipos_onedrive_error"
    else:
        equipos_path = obtener_ruta_archivo_equipos()
        if equipos_path:
            try:
                equipos_sheet = os.getenv("EQUIPOS_SHEET_NAME", SHEET_NAME).strip()
                df_equipos = _normalizar_dataframe_equipos(equipos_path, sheet_name=equipos_sheet)
                df = pd.concat([df, df_equipos], ignore_index=True, sort=False)
                LAST_DATA_SOURCE = f"{LAST_DATA_SOURCE}+equipos"
            except Exception:
                LAST_DATA_SOURCE = f"{LAST_DATA_SOURCE}+equipos_error"

    return df


def obtener_fuente_datos() -> str:
    return LAST_DATA_SOURCE


def obtener_info_datos_locales() -> dict:
    """Información diagnóstica básica del archivo local de datos."""
    ruta = obtener_ruta_archivo_local()
    existe = os.path.exists(ruta)
    mtime = os.path.getmtime(ruta) if existe else None
    ruta_equipos = obtener_ruta_archivo_equipos()
    equipos_existe = os.path.exists(ruta_equipos) if ruta_equipos else False
    equipos_mtime = os.path.getmtime(ruta_equipos) if equipos_existe else None
    return {
        "ruta": ruta,
        "existe": existe,
        "mtime": mtime,
        "ruta_equipos": ruta_equipos,
        "equipos_existe": equipos_existe,
        "equipos_mtime": equipos_mtime,
    }