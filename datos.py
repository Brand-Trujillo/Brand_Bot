import pandas as pd
import os
import sys

# Nombre del archivo de datos (se asume en la misma carpeta que el ejecutable/archivo)
ARCHIVO = "Control de muestras_2026.xlsx"


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


def cargar_datos():
    archivo_path = _resource_path(ARCHIVO)
    df = pd.read_excel(
        archivo_path,
        sheet_name="CONTROL_MUESTRAS_2026",
        header=6
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