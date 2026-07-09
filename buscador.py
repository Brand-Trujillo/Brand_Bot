import re

def limpiar_texto(texto):
    texto = texto.lower()

    palabras_ignorar = [
        "donde", "dime", "cuando", "llego", "está", "esta", "la", "el", "los", "las",
        "de", "del", "una", "un", "muestra", "muestras",
        "buscar", "muéstrame", "mostrar", "ya", "llegó",
        "llego", "por", "favor", "quiero", "ver", "en", "y", "o"
    ]

    palabras = re.findall(r"\w+", texto)

    palabras = [
        p for p in palabras
        if p not in palabras_ignorar and (len(p) > 1 or p.isdigit())
    ]

    return " ".join(palabras)


def buscar(df, texto):
    """
    Busca en el dataframe con soporte para doble filtro.
    Ejemplo: "certecnica en custodia" o "cidet enviado"
    """
    
    texto_original = texto.lower()
    texto_limpio = limpiar_texto(texto)

    # Estados conocidos
    estados = ["custodia", "almacenado", "proceso", "enviado", "entregado", "terminado", "finalizado"]

    # Tokens a partir del texto limpio
    tokens = [t for t in re.findall(r"\w+", texto_limpio) if t]

    # Detectar tokens que coinciden con estados (o sus variantes)
    estado_tokens = []
    otros_tokens = []
    for t in tokens:
        matched = None
        for estado in estados:
            if t == estado or t in estado or estado in t:
                matched = estado
                break
        if matched:
            estado_tokens.append(matched)
        else:
            otros_tokens.append(t)

    # Separar tokens numéricos (números de muestra) de los tokens textuales
    numeric_tokens = [t for t in otros_tokens if t.isdigit()]
    text_tokens = [t for t in otros_tokens if not t.isdigit()]

    # Evitar tokens de un solo carácter (ej. 'c') que generan muchos falsos positivos
    # Conservamos tokens con dígitos (p. ej. 'c502')
    text_tokens = [t for t in text_tokens if len(t) > 1 or any(ch.isdigit() for ch in t)]

    # Detectar patrón tipo 'C 502' o 'c502' y priorizar búsqueda en COTIZACION
    m_c_pref = re.search(r'(?i)\b[cC]\s*0*(\d+)\b', texto_original)
    if m_c_pref and 'COTIZACION' in df.columns:
        numero_busqueda = m_c_pref.group(1).lstrip('0') or '0'
        import pandas as _pd
        cot_digits = df['COTIZACION'].astype(str).fillna('').str.extract(r'(\d+)', expand=False).fillna('')
        mask_cot = cot_digits.str.lstrip('0') == numero_busqueda
        if mask_cot.any():
            return df[mask_cot], {'tokens': tokens, 'match_field': 'COTIZACION', 'match': 'exact_prefix_c', 'rapidfuzz': False}

    # Detectar patrón tipo 'I 406' o 'i406' y priorizar búsqueda en INFORME
    m_i_pref = re.search(r'(?i)\b[iI]\s*0*(\d+)\b', texto_original)
    if m_i_pref and 'INFORME' in df.columns:
        numero_busqueda = m_i_pref.group(1).lstrip('0') or '0'
        import pandas as _pd
        informe_digits = df['INFORME'].astype(str).fillna('').str.extract(r'(\d+)', expand=False).fillna('')
        mask_info = informe_digits.str.lstrip('0') == numero_busqueda
        if mask_info.any():
            return df[mask_info], {'tokens': tokens, 'match_field': 'INFORME', 'match': 'exact_prefix_i', 'rapidfuzz': False}

    # Si hay tokens numéricos, priorizar búsqueda exacta en columnas numéricas/ID
    if numeric_tokens:
        # Columnas donde normalmente buscamos identificadores numéricos.
        # Excluir `ITEM` para evitar matches erróneos (solicitado por el usuario).
        cols_exact = ["NUMERO", "ID", "SERIE", "ITEM", "REFERENCIA"]
        cols_exact = [c for c in cols_exact if c in df.columns and c.upper() != 'ITEM']
        import pandas as _pd
        mask_numeric = _pd.Series(True, index=df.index)
        for nt in numeric_tokens:
            # para cada token numérico, construir máscara que sea True si alguna columna tiene igualdad exacta
            mask_anycol = _pd.Series(False, index=df.index)
            for c in cols_exact:
                if c in df.columns:
                    mask_col = df[c].astype(str).str.strip().str.lower() == nt.lower()
                    mask_anycol = mask_anycol | mask_col
            mask_numeric = mask_numeric & mask_anycol

        # si encontramos coincidencias exactas en columnas numéricas, devolverlas directamente
        if mask_numeric.any():
            resultados = df[mask_numeric]
            return resultados, {'tokens': tokens, 'estado_tokens': estado_tokens, 'otros_tokens': otros_tokens, 'numeric_tokens': numeric_tokens, 'match': 'exact', 'rapidfuzz': False}

        # Si no hay coincidencias exactas, intentar coincidencia parcial (substring) en las mismas columnas
        mask_partial = _pd.Series(False, index=df.index)
        for nt in numeric_tokens:
            mask_anycol = _pd.Series(False, index=df.index)
            for c in cols_exact:
                if c in df.columns:
                    mask_col = df[c].astype(str).str.contains(nt, na=False)
                    mask_anycol = mask_anycol | mask_col
            mask_partial = mask_partial | mask_anycol

        if mask_partial.any():
            resultados = df[mask_partial]
            return resultados, {'tokens': tokens, 'estado_tokens': estado_tokens, 'otros_tokens': otros_tokens, 'numeric_tokens': numeric_tokens, 'match': 'partial', 'rapidfuzz': False}

    # Priorizar búsqueda dirigida si el usuario menciona 'informe' o 'cotizacion'
    texto_bajo = texto_original
    campos_objetivo = []
    if 'informe' in texto_bajo or 'reporte' in texto_bajo or 'reporte tecnico' in texto_bajo or 'report' in texto_bajo or 'informe' in tokens:
        campos_objetivo.append('INFORME')
    if 'cotizacion' in texto_bajo or 'cotización' in texto_bajo or 'presupuesto' in texto_bajo or 'valor' in texto_bajo or 'cotizar' in texto_bajo or 'cotizacion' in tokens:
        campos_objetivo.append('COTIZACION')
    if 'cliente' in texto_bajo or 'nombre' in texto_bajo or 'cliente' in tokens:
        campos_objetivo.append('CLIENTE')
    if 'descripcion' in texto_bajo or 'detalle' in texto_bajo or 'producto' in texto_bajo or 'articulo' in texto_bajo or 'descripcion' in tokens:
        campos_objetivo.append('DESCRIPCION')
    if 'referencia' in texto_bajo or 'ref' in texto_bajo or 'codigo' in texto_bajo or 'codigo' in tokens:
        campos_objetivo.append('REFERENCIA')
    if 'modelo' in texto_bajo or 'referencia modelo' in texto_bajo or 'referencia/modelo' in texto_bajo:
        campos_objetivo.append('REFERENCIA_MODELO')
    if 'interna' in texto_bajo or 'identificacion interna' in texto_bajo or 'identificación interna' in texto_bajo or 'id interna' in texto_bajo:
        campos_objetivo.append('IDENTIFICACION_INTERNA')
    if 'marca' in texto_bajo or 'etiqueta' in texto_bajo or 'brand' in texto_bajo or 'marca' in tokens:
        campos_objetivo.append('MARCA')
    if 'ubicacion' in texto_bajo or 'direccion' in texto_bajo or 'localizacion' in texto_bajo or 'ubicado' in texto_bajo or 'ubicada' in texto_bajo or 'donde' in texto_bajo or 'ubicacion' in tokens:
        campos_objetivo.append('UBICACION')
    if 'cliente' in texto_bajo or 'cliente' in tokens:
        campos_objetivo.append('CLIENTE')
    if 'descripcion' in texto_bajo or 'descripcion' in tokens or 'detalle' in texto_bajo:
        campos_objetivo.append('DESCRIPCION')
    if 'referencia' in texto_bajo or 'referencia' in tokens or 'ref' in texto_bajo:
        campos_objetivo.append('REFERENCIA')
    if 'modelo' in texto_bajo or 'modelo' in tokens:
        campos_objetivo.append('REFERENCIA_MODELO')
    if 'interna' in texto_bajo or 'interna' in tokens:
        campos_objetivo.append('IDENTIFICACION_INTERNA')
    if 'marca' in texto_bajo or 'marca' in tokens:
        campos_objetivo.append('MARCA')
    if 'ubicacion' in texto_bajo or 'ubicacion' in tokens:
        campos_objetivo.append('UBICACION')

    # Si se mencionan campos objetivo, realizar búsquedas vectorizadas y solo recurrir a fuzzy en ese campo
    if campos_objetivo:
        import pandas as _pd
        # tokens de búsqueda relevantes (sin el nombre del campo)
        filtros = [t for t in tokens if t not in ['informe', 'cotizacion', 'cotización']]

        for campo in campos_objetivo:
            if campo in df.columns:
                serie_raw = df[campo].astype(str).fillna('')
                serie = serie_raw.str.lower()

                # 1) Búsqueda exacta sobre el campo (trimmed)
                if filtros:
                    mask_exact = _pd.Series(False, index=df.index)
                    for f in filtros:
                        # Si el filtro es numérico y el campo es COTIZACION, extraer dígitos para comparar
                        if campo in ['COTIZACION', 'INFORME', 'IDENTIFICACION_INTERNA'] and f.isdigit():
                            digits = serie_raw.str.extract(r'(\d+)', expand=False).fillna('')
                            # comparar sin ceros a la izquierda
                            mask_num = digits.str.lstrip('0') == f.lstrip('0')
                            # también admitir presencia del número como substring (por si hay prefijos)
                            mask_contains = serie.str.contains(re.escape(f), na=False)
                            mask_exact = mask_exact | (mask_num | mask_contains)
                        else:
                            mask_exact = mask_exact | (serie.str.strip() == f)
                    if mask_exact.any():
                        return df[mask_exact], {'tokens': tokens, 'match_field': campo, 'match': 'exact', 'rapidfuzz': False}

                # 2) Búsqueda por substring (vectorizada)
                if filtros:
                    # Si todos los filtros son numéricos y el campo es COTIZACION, buscar por presencia de números
                    if campo in ['COTIZACION', 'IDENTIFICACION_INTERNA'] and all(f.isdigit() for f in filtros):
                        mask_sub = _pd.Series(False, index=df.index)
                        for f in filtros:
                            mask_sub = mask_sub | serie.str.contains(re.escape(f), na=False)
                    else:
                        pattern = '|'.join([re.escape(f) for f in filtros])
                        mask_sub = serie.str.contains(pattern, na=False)

                    if mask_sub.any():
                        return df[mask_sub], {'tokens': tokens, 'match_field': campo, 'match': 'partial', 'rapidfuzz': False}

                # 3) Si no hay tokens pero se pidió el campo, devolver filas con valor no vacío
                if not filtros:
                    mask_nonempty = serie.str.strip() != ''
                    if mask_nonempty.any():
                        return df[mask_nonempty], {'tokens': tokens, 'match_field': campo, 'match': 'nonempty', 'rapidfuzz': False}

                # 4) Fallback: permitimos seguir al flujo general para aplicar fuzzy sobre todo el registro

    # Intentar usar rapidfuzz para fuzzy matching, si no está disponible usar difflib
    try:
        from rapidfuzz import fuzz  # type: ignore[import]
        def fuzzy_match_score(a, b):
            try:
                return fuzz.token_set_ratio(a, b)
            except Exception:
                return 0
        rapidfuzz_available = True
    except Exception:
        import difflib
        def fuzzy_match_score(a, b):
            return int(difflib.SequenceMatcher(None, a, b).ratio() * 100)
        rapidfuzz_available = False

    # Umbral de similaridad (0-100)
    UMBRAL = 78

    import pandas as _pd
    mask = _pd.Series(True, index=df.index)

    # Aplicar filtros de estado (coincidencia exacta o fuzzy sobre la columna ESTADO)
    for est in estado_tokens:
        mask = mask & df["ESTADO"].astype(str).str.lower().str.contains(est, regex=False, na=False)

    # Para cada token textual restante, comprobar fuzzy match en todas las columnas
    for t in text_tokens:
        def fila_coincide(fila):
            for val in fila:
                s = str(val).lower()
                # chequeo rápido por substring primero
                if t in s:
                    return True
                # fuzzy check
                score = fuzzy_match_score(t, s)
                if score >= UMBRAL:
                    return True
            return False

        mask_token = df.astype(str).apply(lambda fila: fila_coincide(fila.str.lower()), axis=1)
        mask = mask & mask_token

    resultados = df[mask]
    # Devolver también los tokens usados para resaltado
    return resultados, {'tokens': tokens, 'estado_tokens': estado_tokens, 'otros_tokens': otros_tokens, 'rapidfuzz': rapidfuzz_available}