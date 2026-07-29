import pandas as pd
import os
import sys
import io
import json
import sqlite3
import tempfile
import time
import urllib.parse
import urllib.request
import unicodedata
import re
import html

# Nombre del archivo de datos (se asume en la misma carpeta que el ejecutable/archivo)
ARCHIVO = "Control de muestras_2026.xlsx"
SHEET_NAME = "CONTROL_MUESTRAS_2026"
DEFAULT_REMOTE_XLSX_URL = (
    "https://docs.google.com/spreadsheets/d/"
    "18IQ-OmkwgfDTUxxfXPOxzcXu-NpAIR2D/edit?usp=drive_link&ouid="
    "116660029921044598774&rtpof=true&sd=true"
)


def _env_first(*names: str, default: str = "") -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return default
DEFAULT_REMOTE_DB_URL = (
    "https://ainsp.sharepoint.com/:u:/s/TodoNYCE/nycecolombia/"
    "IQDYcP46FHm-Tqi8DXyQ5PSpAV_sE58gk4BOLVN5_V_v9y4?"
    "email=brandon.trujillo%40nycecolombia.co&e=4ivaex"
)
DEFAULT_LOCAL_DB_PATHS = [
    # Nueva ruta principal sincronizada para base de muestras.
    (
        r"C:\Users\RentAdvisor\OneDrive - QIMA\Todo NYCE\nycecolombia\Laboratorio\Técnico"
        r"\7.8 INFORMES DE ENSAYO\BASES DE DATOS (Informe de ensayos)\BD_Control_Muestras\lencdb.db"
    ),
    # Ruta heredada: se conserva como fallback para no romper entornos previos.
    (
        r"C:\Users\RentAdvisor\QIMA\NYCE COLOMBIA - Laboratorio (1)\Técnico\7.8 INFORMES DE ENSAYO"
        r"\BASES DE DATOS (Informe de ensayos)\BD_Control_Muestras\lencdb.db"
    ),
]

# Fuente cargada en memoria para diagnostico
LAST_DATA_SOURCE = "unknown"
LAST_MAIN_ERROR = ""
LAST_EQUIPOS_ERROR = ""
LAST_LOAD_TS = 0.0
LAST_LOAD_DURATION_MS = 0.0
LAST_LOAD_ROWS = 0
LAST_LOAD_COLUMNS = 0
LAST_ALERTS = []
_PREV_SUCCESS_ROWS = 0
_ALERT_LAST_SENT = {}


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _append_jsonl(path: str, payload: dict) -> None:
    try:
        folder = os.path.dirname(path)
        if folder:
            os.makedirs(folder, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, ensure_ascii=True) + "\n")
    except OSError:
        pass


def _emit_alert(code: str, message: str, severity: str = "warning", extra: dict | None = None) -> None:
    global LAST_ALERTS, _ALERT_LAST_SENT
    cooldown_seconds = _int_env("ALERT_COOLDOWN_SECONDS", 300)
    now = time.time()
    last_sent = _ALERT_LAST_SENT.get(code, 0.0)
    if (now - last_sent) < max(0, cooldown_seconds):
        return
    _ALERT_LAST_SENT[code] = now

    alert = {
        "ts": now,
        "severity": severity,
        "code": code,
        "message": message,
        "source": LAST_DATA_SOURCE,
    }
    if extra:
        alert["extra"] = extra

    LAST_ALERTS.append(alert)
    LAST_ALERTS = LAST_ALERTS[-20:]

    log_path = os.getenv("DATOS_ALERT_LOG_PATH", "logs/data_alerts.jsonl").strip() or "logs/data_alerts.jsonl"
    _append_jsonl(log_path, alert)

    webhook_url = os.getenv("ALERT_WEBHOOK_URL", "").strip()
    if not webhook_url:
        return

    try:
        body = json.dumps(alert, ensure_ascii=True).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": "BrandBot/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=8):
            pass
    except Exception:
        pass


def _evaluar_alertas_carga(rows: int, source: str) -> None:
    global _PREV_SUCCESS_ROWS

    if source not in {"google_sheets", "remote_xlsx", "google_drive_sqlite"}:
        _emit_alert(
            code="fallback_source",
            message=f"Fuente de datos en fallback: {source}",
            severity="warning",
            extra={"rows": rows},
        )

    min_prev_rows = _int_env("ALERT_MIN_PREV_ROWS", 200)
    min_ratio = _float_env("ALERT_MIN_ROWS_DROP_RATIO", 0.70)
    min_ratio = min(0.99, max(0.10, min_ratio))
    if _PREV_SUCCESS_ROWS >= min_prev_rows and rows < int(_PREV_SUCCESS_ROWS * min_ratio):
        _emit_alert(
            code="rows_drop",
            message="Disminucion anomala de filas en la carga de muestras",
            severity="warning",
            extra={"previous_rows": _PREV_SUCCESS_ROWS, "current_rows": rows, "ratio": round(rows / max(_PREV_SUCCESS_ROWS, 1), 3)},
        )

    _PREV_SUCCESS_ROWS = rows


def _registrar_carga_exitosa(df: pd.DataFrame, started_at: float) -> pd.DataFrame:
    global LAST_LOAD_TS, LAST_LOAD_DURATION_MS, LAST_LOAD_ROWS, LAST_LOAD_COLUMNS
    LAST_LOAD_TS = time.time()
    LAST_LOAD_DURATION_MS = (time.perf_counter() - started_at) * 1000.0
    LAST_LOAD_ROWS = int(len(df))
    LAST_LOAD_COLUMNS = int(len(df.columns)) if hasattr(df, "columns") else 0
    _evaluar_alertas_carga(LAST_LOAD_ROWS, LAST_DATA_SOURCE)
    return df


def obtener_metricas_datos() -> dict:
    return {
        "source": LAST_DATA_SOURCE,
        "main_error": LAST_MAIN_ERROR,
        "equipos_error": LAST_EQUIPOS_ERROR,
        "last_load_ts": LAST_LOAD_TS,
        "last_load_duration_ms": round(LAST_LOAD_DURATION_MS, 2),
        "last_load_rows": LAST_LOAD_ROWS,
        "last_load_columns": LAST_LOAD_COLUMNS,
    }


def obtener_alertas_datos(limit: int = 10) -> list[dict]:
    return LAST_ALERTS[-max(1, limit):]


def _descargar_bytes_con_reintentos(url: str, timeout: int = 45) -> bytes:
    attempts = max(1, _int_env("DATOS_RETRY_ATTEMPTS", 3))
    delay_ms = max(0, _int_env("DATOS_RETRY_DELAY_MS", 700))
    last_exc = None

    for intento in range(1, attempts + 1):
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "*/*",
                "Cache-Control": "no-cache",
                "Pragma": "no-cache",
            },
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = response.read()
                resolved_url = response.geturl()
                content_type = (response.headers.get("Content-Type") or "").lower()

                follow_up = _drive_followup_download_url(data, resolved_url, content_type)
                if follow_up and follow_up not in {url, resolved_url}:
                    return _descargar_bytes_con_reintentos(follow_up, timeout=timeout)

                return data
        except Exception as exc:
            last_exc = exc
            if intento < attempts and delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

    if last_exc is not None:
        raise last_exc
    raise RuntimeError("No se pudo descargar el recurso remoto")


def _drive_followup_download_url(data: bytes, resolved_url: str, content_type: str) -> str:
    """Detecta respuestas HTML intermedias de Google Drive y extrae URL de descarga real."""
    if not data:
        return ""

    parsed = urllib.parse.urlparse(resolved_url)
    host = parsed.netloc.lower()
    if "drive.google.com" not in host and "drive.usercontent.google.com" not in host:
        return ""

    sample = data[:2048].lstrip().lower()
    looks_html = (
        "text/html" in content_type
        or sample.startswith(b"<!doctype html")
        or sample.startswith(b"<html")
        or b"<html" in sample
    )
    if not looks_html:
        return ""

    text = data.decode("utf-8", errors="ignore")

    # Caso típico: link de confirmación en HTML con href="/uc?export=download..."
    href_match = re.search(r'href="([^"]*?/uc\?export=download[^"]*)"', text)
    if href_match:
        href = html.unescape(href_match.group(1))
        return urllib.parse.urljoin("https://drive.google.com", href)

    # Fallback: algunos flujos incluyen parámetros en campos ocultos.
    id_match = re.search(r'name="id"\s+value="([^"]+)"', text)
    confirm_match = re.search(r'name="confirm"\s+value="([^"]+)"', text)
    if id_match and confirm_match:
        file_id = urllib.parse.quote(id_match.group(1))
        confirm = urllib.parse.quote(confirm_match.group(1))
        return f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm}"

    return ""


def obtener_ruta_archivo_equipos() -> str:
    """Devuelve la ruta del Excel opcional de control de equipos.

    Se usa solo si se define EQUIPOS_XLSX_PATH.
    """
    custom_path = os.getenv("EQUIPOS_XLSX_PATH", "").strip()
    if custom_path:
        return custom_path
    return ""


def obtener_ruta_db_local() -> str:
    """Devuelve la ruta de la base SQLite local si existe."""
    custom_path = os.getenv("DATOS_DB_PATH", "").strip()
    if custom_path:
        # Soporta rutas relativas al proyecto para despliegues (ej. DATOS_DB_PATH=lencdb.db).
        if os.path.isabs(custom_path):
            return custom_path
        return _resource_path(custom_path)

    # Prioridad local del proyecto (útil para despliegues sin acceso a red interna).
    project_db = _resource_path("lencdb.db")
    if os.path.exists(project_db):
        return project_db

    for db_path in DEFAULT_LOCAL_DB_PATHS:
        if os.path.exists(db_path):
            return db_path
    return ""


def obtener_url_db() -> str:
    """Devuelve URL de la base SQLite de muestras (opcional)."""
    custom_url = os.getenv("DATOS_DB_URL", "").strip()
    if custom_url:
        return custom_url
    return DEFAULT_REMOTE_DB_URL


def obtener_ruta_archivo_local() -> str:
    """Devuelve la ruta del Excel local usado por la app.

    Si existe la variable DATOS_XLSX_PATH se usa esa ruta explícita.
    Esto permite apuntar al archivo actualizado real (por ejemplo una copia sincronizada).
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


def _remote_xlsx_download_url(url: str) -> str:
    """Convierte una URL compartida o Google Sheets a descarga directa."""
    parsed = urllib.parse.urlparse(url)
    
    # Google Sheets compartido en modo "edit" -> export directo en formato Excel.
    if "docs.google.com" in parsed.netloc and "/spreadsheets/d/" in parsed.path:
        parts = [p for p in parsed.path.split("/") if p]
        sheet_id = ""
        if "d" in parts:
            idx = parts.index("d")
            if idx + 1 < len(parts):
                sheet_id = parts[idx + 1]

        if sheet_id:
            query = urllib.parse.parse_qs(parsed.query)
            export_params = {"format": "xlsx"}
            # Importante: no forzar gid=0, porque algunos links compartidos
            # devuelven HTTP 400 cuando el gid no corresponde a una hoja válida.
            if query.get("gid"):
                export_params["gid"] = query["gid"][0]
            export_query = urllib.parse.urlencode(export_params)
            return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?{export_query}"

    # Google Drive file compartido -> descarga directa del archivo binario.
    # Ejemplo: /file/d/<id>/view?...  =>  /uc?export=download&id=<id>
    if "drive.google.com" in parsed.netloc and "/file/d/" in parsed.path:
        parts = [p for p in parsed.path.split("/") if p]
        file_id = ""
        if "d" in parts:
            idx = parts.index("d")
            if idx + 1 < len(parts):
                file_id = parts[idx + 1]
        if file_id:
            return f"https://drive.google.com/uc?export=download&id={urllib.parse.quote(file_id)}"

    query = urllib.parse.parse_qs(parsed.query)

    # Enlaces compartidos suelen aceptar download=1
    if "download" not in query:
        query["download"] = ["1"]

    new_query = urllib.parse.urlencode(query, doseq=True)
    return urllib.parse.urlunparse(
        (parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment)
    )


def _parece_sqlite(data: bytes) -> bool:
    return bool(data) and data.startswith(b"SQLite format 3\x00")


def _cargar_sqlite_desde_bytes(data: bytes) -> pd.DataFrame:
    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp.write(data)
            temp_path = tmp.name
        return _cargar_desde_sqlite(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


def _cargar_xlsx_desde_bytes(data: bytes, sheet_name: str = "", header: int = 6) -> pd.DataFrame:
    buffer = io.BytesIO(data)

    # Estrategia 1: Usar sheet_name y header especificados
    try:
        df = pd.read_excel(
            buffer,
            sheet_name=sheet_name or 0,
            header=header,
        )
        # Validar que el dataframe tiene columnas reconocibles
        if len(df.columns) > 5:
            return df
    except Exception:
        pass

    # Estrategia 2: Si falla, intentar con header autodetección (primera hoja)
    buffer.seek(0)
    try:
        xls = pd.ExcelFile(buffer)
        preferred = []
        if sheet_name and sheet_name in xls.sheet_names:
            preferred.append(sheet_name)
        for candidate in xls.sheet_names:
            if candidate not in preferred:
                preferred.append(candidate)

        for sheet in preferred:
            try:
                df = pd.read_excel(xls, sheet_name=sheet, header=0)
                if len(df.columns) > 5:  # Validación básica
                    return df
            except Exception:
                pass
    except Exception:
        pass

    # Estrategia 3: Sin header, dejar que el usuario sepa que es un fallback
    buffer.seek(0)
    return pd.read_excel(buffer, sheet_name=sheet_name or 0, header=None)


def _cargar_xlsx_remoto(url: str, sheet_name: str = "", header: int = 6) -> pd.DataFrame:
    """Descarga un Excel remoto y lo carga en memoria.

    Esto evita problemas de bloqueo cuando el archivo esta abierto localmente.
    Reintenta con diferentes headers/hojas si la primera falla (para soportar variantes de estructura).
    """
    data = _descargar_bytes_con_reintentos(url, timeout=45)
    return _cargar_xlsx_desde_bytes(data, sheet_name=sheet_name, header=header)


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


def _cargar_desde_sqlite(path: str) -> pd.DataFrame:
    """Carga muestras desde la base SQLite local del laboratorio."""
    query = """
        SELECT
            id,
            codigoInterno,
            rotuloCliente,
            nombreCliente,
            descripcion,
            marca,
            referencia,
            estado,
            ubicacion,
            observacionAlmacenamiento,
            fechaRecepcion,
            numeroInforme,
            numeroCotizacion,
            remision
        FROM muestras
    """
    with sqlite3.connect(path) as con:
        return pd.read_sql_query(query, con)


def _cargar_desde_sqlite_url(url: str) -> pd.DataFrame:
    """Descarga una base SQLite desde URL y consulta la tabla de muestras."""
    data = _descargar_bytes_con_reintentos(_remote_xlsx_download_url(url), timeout=45)

    temp_path = ""
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as temp_file:
            temp_file.write(data)
            temp_path = temp_file.name
        return _cargar_desde_sqlite(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass


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


def _normalizar_dataframe_sqlite(df: pd.DataFrame) -> pd.DataFrame:
    """Normaliza la base SQLite local al esquema esperado por el bot."""
    rename_map = {
        "id": "ITEM",
        "fechaRecepcion": "FECHA_INGRESO",
        "nombreCliente": "CLIENTE",
        "descripcion": "DESCRIPCION",
        "marca": "MARCA",
        "referencia": "REFERENCIA_MODELO",
        "rotuloCliente": "REFERENCIA_EXTERNA",
        "codigoInterno": "REFERENCIA_INTERNA",
        "numeroInforme": "INFORME",
        "numeroCotizacion": "COTIZACION",
        "ubicacion": "UBICACION",
        "estado": "ESTADO",
        "observacionAlmacenamiento": "OBSERVACIONES",
        "remision": "NUMERO",
    }
    df = df.rename(columns=rename_map).copy()

    for col in [
        "ITEM",
        "FECHA_INGRESO",
        "CLIENTE",
        "DESCRIPCION",
        "MARCA",
        "REFERENCIA_MODELO",
        "REFERENCIA_EXTERNA",
        "REFERENCIA_INTERNA",
        "INFORME",
        "NUMERO",
        "COTIZACION",
        "UBICACION",
        "ESTADO",
        "OBSERVACIONES",
    ]:
        if col not in df.columns:
            df[col] = pd.NA

    df["ID"] = df["ITEM"]
    fechas = pd.to_datetime(df["FECHA_INGRESO"], errors="coerce")
    df["AÑO"] = fechas.dt.year.astype("Int64")
    df["MARCA"] = df["MARCA"].astype("string").str.strip().replace({"": pd.NA}).fillna("N/E")
    df["REFERENCIA"] = df["REFERENCIA_EXTERNA"]
    df["SERIE"] = df["REFERENCIA_INTERNA"]
    df["IDENTIFICACION_INTERNA"] = df["REFERENCIA_INTERNA"]
    df["TIPO_REGISTRO"] = "muestra"
    df["ESTADO"] = df["ESTADO"].astype("string").str.replace("_", " ", regex=False).str.title()

    return df


def cargar_datos():
    global LAST_DATA_SOURCE, LAST_MAIN_ERROR, LAST_EQUIPOS_ERROR
    LAST_MAIN_ERROR = ""
    LAST_EQUIPOS_ERROR = ""
    started_at = time.perf_counter()
    # URL remota principal para muestras en producción.
    remote_xlsx_url = _env_first("REMOTE_XLSX_URL", "ONEDRIVE_XLSX_URL", default=DEFAULT_REMOTE_XLSX_URL)

    df = None  # Inicializar para evitar NameError

    # Prioridad 1: Google Sheets remoto (fuente principal)
    if remote_xlsx_url:
        try:
            remote_download_url = _remote_xlsx_download_url(remote_xlsx_url)
            remote_data = _descargar_bytes_con_reintentos(remote_download_url, timeout=45)

            if _parece_sqlite(remote_data):
                df = _cargar_sqlite_desde_bytes(remote_data)
                LAST_DATA_SOURCE = "google_drive_sqlite"
                df = _normalizar_dataframe_sqlite(df)
                return _registrar_carga_exitosa(_post_procesar_datos(df), started_at)

            # Para Google Sheets: no forzar SHEET_NAME específico, dejar que autodetecte.
            # Si falla con la hoja esperada, el lector interno ya prueba alternativas.
            df = _cargar_xlsx_desde_bytes(remote_data, sheet_name=SHEET_NAME, header=6)
            LAST_DATA_SOURCE = "google_sheets"
            df = _normalizar_dataframe(df)
            return _registrar_carga_exitosa(_post_procesar_datos(df), started_at)
        except Exception as exc:
            LAST_MAIN_ERROR = f"remote_xlsx_main_error: {exc}"
    _emit_alert(
        code="all_sources_failed",
        message="Fallo la carga de datos desde la fuente principal",
        severity="error",
        extra={"error": LAST_MAIN_ERROR or "remote_xlsx_not_available"},
    )
    raise RuntimeError(LAST_MAIN_ERROR or "No se pudo cargar la fuente principal")


def _post_procesar_datos(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica procesamiento adicional (equipos) tras cargar datos principales."""
    global LAST_DATA_SOURCE, LAST_EQUIPOS_ERROR
    equipos_remoto_url = _env_first("EQUIPOS_REMOTE_XLSX_URL", "EQUIPOS_ONEDRIVE_XLSX_URL")

    # Carga opcional de un segundo Excel (control de equipos) y lo une al dataset principal.
    if equipos_remoto_url:
        try:
            equipos_sheet = os.getenv("EQUIPOS_SHEET_NAME", SHEET_NAME).strip()
            equipos_buffer = _cargar_xlsx_remoto(
                _remote_xlsx_download_url(equipos_remoto_url),
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
            LAST_DATA_SOURCE = f"{LAST_DATA_SOURCE}+equipos_remoto"
        except Exception as exc:
            LAST_EQUIPOS_ERROR = f"equipos_remoto_error: {exc}"
            LAST_DATA_SOURCE = f"{LAST_DATA_SOURCE}+equipos_remoto_error"

    return df


def obtener_fuente_datos() -> str:
    return LAST_DATA_SOURCE


def obtener_info_datos_locales() -> dict:
    """Información diagnóstica básica del archivo local de datos."""
    ruta = obtener_ruta_archivo_local()
    existe = os.path.exists(ruta)
    mtime = os.path.getmtime(ruta) if existe else None
    ruta_db = obtener_ruta_db_local()
    db_existe = os.path.exists(ruta_db) if ruta_db else False
    db_mtime = os.path.getmtime(ruta_db) if db_existe else None
    db_url = obtener_url_db()
    ruta_equipos = obtener_ruta_archivo_equipos()
    equipos_existe = os.path.exists(ruta_equipos) if ruta_equipos else False
    equipos_mtime = os.path.getmtime(ruta_equipos) if equipos_existe else None
    return {
        "ruta": ruta,
        "existe": existe,
        "mtime": mtime,
        "ruta_db": ruta_db,
        "db_existe": db_existe,
        "db_mtime": db_mtime,
        "db_url": db_url,
        "ruta_equipos": ruta_equipos,
        "equipos_existe": equipos_existe,
        "equipos_mtime": equipos_mtime,
        "main_error": LAST_MAIN_ERROR,
        "equipos_error": LAST_EQUIPOS_ERROR,
    }