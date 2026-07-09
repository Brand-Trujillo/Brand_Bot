import pandas as pd
import os
import sys
import io
import urllib.parse
import urllib.request

# Nombre del archivo de datos (se asume en la misma carpeta que el ejecutable/archivo)
ARCHIVO = "Control de muestras_2026.xlsx"
SHEET_NAME = "CONTROL_MUESTRAS_2026"


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


def _cargar_desde_onedrive(url: str) -> pd.DataFrame:
    """Descarga el Excel desde OneDrive y lo carga en memoria.

    Esto evita problemas de bloqueo cuando el archivo esta abierto localmente.
    """
    request = urllib.request.Request(url, method="GET")
    with urllib.request.urlopen(request, timeout=45) as response:
        data = response.read()

    buffer = io.BytesIO(data)
    df = pd.read_excel(
        buffer,
        sheet_name=SHEET_NAME,
        header=6,
    )
    return df


def cargar_datos():
    onedrive_url = os.getenv("ONEDRIVE_XLSX_URL", "").strip()

    if onedrive_url:
        try:
            df = _cargar_desde_onedrive(_onedrive_download_url(onedrive_url))
        except Exception:
            # Fallback seguro: continuar con archivo local si la URL falla.
            archivo_path = _resource_path(ARCHIVO)
            df = pd.read_excel(
                archivo_path,
                sheet_name=SHEET_NAME,
                header=6,
            )
    else:
        archivo_path = _resource_path(ARCHIVO)
        df = pd.read_excel(
            archivo_path,
            sheet_name=SHEET_NAME,
            header=6,
        )
    # Eliminar las dos filas que sobran
    df = df.iloc[2:]
    # Reiniciar el índice
    df = df.reset_index(drop=True)
    # Renombrar columnas
    df.columns = [
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
        "OBSERVACIONES"
    ]
    # limpiar los nombres de las columnas
    df.columns = df.columns.str.strip()
    # Normalizar MARCA: quitar espacios en blanco y usar N/E cuando no haya valor
    df["MARCA"] = df["MARCA"].astype("string").str.strip()
    df["MARCA"] = df["MARCA"].replace({"": pd.NA}).fillna("N/E")
    return df