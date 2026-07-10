import re


def _ordenar_por_relevancia(df, tokens, campos_prioritarios=None):
    """Ordena resultados por score de relevancia.

    Prioriza coincidencias exactas y luego parciales, dando más peso
    a los campos que el usuario menciona explícitamente en la consulta.
    """
    if df is None or df.empty:
        return df

    tokens = [str(t).strip().lower() for t in (tokens or []) if str(t).strip()]
    if not tokens:
        return df

    campos_prioritarios = [c for c in (campos_prioritarios or []) if c in df.columns]
    columnas = [c for c in df.columns if c not in ["ITEM", "ID", "AÑO"]]

    def _score_fila(fila):
        score = 0
        for t in tokens:
            for c in columnas:
                valor = str(fila.get(c, "")).strip().lower()
                if not valor:
                    continue

                peso_base = 6 if c in campos_prioritarios else 3
                if valor == t:
                    score += peso_base + 6
                elif t in valor:
                    score += peso_base + 2
        return score

    ordenado = df.copy()
    ordenado["_score_busqueda"] = ordenado.apply(_score_fila, axis=1)
    ordenado = ordenado.sort_values(by=["_score_busqueda"], ascending=[False], na_position="last")
    return ordenado.drop(columns=["_score_busqueda"])

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

    # Si no quedaron tokens útiles, evitamos devolver todo el dataset por defecto.
    if not numeric_tokens and not text_tokens and not estado_tokens:
        return df.iloc[0:0], {
            'tokens': tokens,
            'match': 'no_tokens',
            'rapidfuzz': False,
        }

    # Evitar tokens de un solo carácter (ej. 'c') que generan muchos falsos positivos
    # Conservamos tokens con dígitos (p. ej. 'c502')
    text_tokens = [t for t in text_tokens if len(t) > 1 or any(ch.isdigit() for ch in t)]

    # Si la consulta es un único token textual y coincide exactamente con CLIENTE,
    # devolvemos solo ese cliente para evitar ruido por fuzzy (ej. VTEK vs VETEK).
    if (
        len(text_tokens) == 1
        and not numeric_tokens
        and not estado_tokens
        and 'CLIENTE' in df.columns
    ):
        t = text_tokens[0].strip().lower()
        mask_cliente = df['CLIENTE'].astype(str).str.strip().str.lower() == t
        if mask_cliente.any():
            return df[mask_cliente], {
                'tokens': tokens,
                'match_field': 'CLIENTE',
                'match': 'exact_client',
                'rapidfuzz': False,
            }

    # Detectar patrón tipo 'C 502' o 'c502' y priorizar búsqueda en COTIZACION
    m_c_pref = re.search(r'(?i)\b[cC]\s*0*(\d+)\b', texto_original)
    if m_c_pref and 'COTIZACION' in df.columns:
        numero_busqueda = m_c_pref.group(1).lstrip('0') or '0'
        import pandas as _pd
        cot_digits = df['COTIZACION'].astype(str).fillna('').str.extract(r'(\d+)', expand=False).fillna('')
        mask_cot = cot_digits.str.lstrip('0') == numero_busqueda
        if mask_cot.any():
            resultados = _ordenar_por_relevancia(df[mask_cot], tokens, ['COTIZACION'])
            return resultados, {'tokens': tokens, 'match_field': 'COTIZACION', 'match': 'exact_prefix_c', 'rapidfuzz': False}

    # Detectar patrón tipo 'I 406' o 'i406' y priorizar búsqueda en INFORME
    m_i_pref = re.search(r'(?i)\b[iI]\s*0*(\d+)\b', texto_original)
    if m_i_pref and 'INFORME' in df.columns:
        numero_busqueda = m_i_pref.group(1).lstrip('0') or '0'
        import pandas as _pd
        informe_digits = df['INFORME'].astype(str).fillna('').str.extract(r'(\d+)', expand=False).fillna('')
        mask_info = informe_digits.str.lstrip('0') == numero_busqueda
        if mask_info.any():
            resultados = _ordenar_por_relevancia(df[mask_info], tokens, ['INFORME'])
            return resultados, {'tokens': tokens, 'match_field': 'INFORME', 'match': 'exact_prefix_i', 'rapidfuzz': False}

    # Detectar intención de campo para hacer matching numérico más preciso.
    # Ej: "informe 406" debe priorizar INFORME, no todos los identificadores.
    target_numeric_cols = []
    if any(k in texto_original for k in ["informe", "reporte", "report"]):
        target_numeric_cols.append("INFORME")
    if any(k in texto_original for k in ["cotizacion", "cotización", "presupuesto"]):
        target_numeric_cols.append("COTIZACION")
    if "referencia externa" in texto_original:
        target_numeric_cols.append("REFERENCIA_EXTERNA")
    if any(k in texto_original for k in ["referencia interna", "id interna", "identificacion interna", "identificación interna"]):
        target_numeric_cols.append("REFERENCIA_INTERNA")
    if "referencia" in texto_original and "referencia interna" not in texto_original and "referencia externa" not in texto_original:
        target_numeric_cols.append("REFERENCIA")
    if "serie" in texto_original:
        target_numeric_cols.append("SERIE")
    if "numero" in texto_original or "nro" in texto_original or "número" in texto_original:
        target_numeric_cols.append("NUMERO")

    # Si hay tokens numéricos, priorizar búsqueda exacta en columnas de identificadores
    if numeric_tokens:
        # Incluir todos los identificadores relevantes por defecto.
        default_cols_exact = [
            "NUMERO", "SERIE", "REFERENCIA",
            "INFORME", "COTIZACION", "IDENTIFICACION_INTERNA",
            "REFERENCIA_INTERNA", "REFERENCIA_EXTERNA", "REFERENCIA_MODELO"
        ]
        # Si hay intención explícita de campo, restringimos para ganar precisión.
        cols_exact = target_numeric_cols[:] if target_numeric_cols else default_cols_exact
        cols_exact = [c for c in cols_exact if c in df.columns]
        import pandas as _pd
        mask_numeric = _pd.Series(True, index=df.index)

        def _normalize_digits(v: str) -> str:
            digits = re.findall(r"\d+", v)
            if not digits:
                return ""
            return "".join(digits).lstrip("0") or "0"

        for nt in numeric_tokens:
            # para cada token numérico, construir máscara que sea True si alguna columna tiene igualdad exacta
            mask_anycol = _pd.Series(False, index=df.index)
            for c in cols_exact:
                if c in df.columns:
                    serie = df[c].astype(str).fillna("").str.strip().str.lower()
                    # Igualdad textual directa
                    mask_text = serie == nt.lower()
                    # Igualdad por dígitos normalizados (admite prefijos como I20819 o C-20819)
                    norm = serie.apply(_normalize_digits)
                    target = (nt.lstrip("0") or "0")
                    mask_digits = norm == target
                    mask_anycol = mask_anycol | mask_text | mask_digits
            mask_numeric = mask_numeric & mask_anycol

        # si encontramos coincidencias exactas en columnas numéricas, devolverlas directamente
        if mask_numeric.any():
            resultados = _ordenar_por_relevancia(df[mask_numeric], tokens, cols_exact)
            return resultados, {
                'tokens': tokens,
                'estado_tokens': estado_tokens,
                'otros_tokens': otros_tokens,
                'numeric_tokens': numeric_tokens,
                'match': 'exact',
                'match_field': ','.join(cols_exact),
                'rapidfuzz': False,
            }

        # Si no hay coincidencias exactas, intentar coincidencia parcial controlada.
        # Usamos fronteras numéricas para no confundir 20819 con 1208199.
        mask_partial = _pd.Series(False, index=df.index)
        for nt in numeric_tokens:
            mask_anycol = _pd.Series(False, index=df.index)
            for c in cols_exact:
                if c in df.columns:
                    serie = df[c].astype(str).fillna("")
                    patron = rf"(?<!\d){re.escape(nt)}(?!\d)"
                    mask_col = serie.str.contains(patron, na=False, regex=True)
                    mask_anycol = mask_anycol | mask_col
            mask_partial = mask_partial | mask_anycol

        if mask_partial.any():
            resultados = _ordenar_por_relevancia(df[mask_partial], tokens, cols_exact)
            return resultados, {
                'tokens': tokens,
                'estado_tokens': estado_tokens,
                'otros_tokens': otros_tokens,
                'numeric_tokens': numeric_tokens,
                'match': 'partial_controlled',
                'match_field': ','.join(cols_exact),
                'rapidfuzz': False,
            }

        # Si el usuario hizo una búsqueda numérica y no hubo coincidencias,
        # no caemos al fuzzy global para evitar falsos positivos masivos.
        return df.iloc[0:0], {
            'tokens': tokens,
            'estado_tokens': estado_tokens,
            'otros_tokens': otros_tokens,
            'numeric_tokens': numeric_tokens,
            'match': 'numeric_no_match',
            'match_field': ','.join(cols_exact),
            'rapidfuzz': False,
        }

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
    if 'referencia externa' in texto_bajo or 'externa' in texto_bajo or 'externa' in tokens:
        campos_objetivo.append('REFERENCIA_EXTERNA')
    if 'interna' in texto_bajo or 'identificacion interna' in texto_bajo or 'identificación interna' in texto_bajo or 'id interna' in texto_bajo:
        campos_objetivo.append('REFERENCIA_INTERNA')
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
    if 'externa' in texto_bajo or 'externa' in tokens:
        campos_objetivo.append('REFERENCIA_EXTERNA')
    if 'interna' in texto_bajo or 'interna' in tokens:
        campos_objetivo.append('REFERENCIA_INTERNA')
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
                        if campo in ['COTIZACION', 'INFORME', 'IDENTIFICACION_INTERNA', 'REFERENCIA_INTERNA'] and f.isdigit():
                            digits = serie_raw.str.extract(r'(\d+)', expand=False).fillna('')
                            # comparar sin ceros a la izquierda
                            mask_num = digits.str.lstrip('0') == f.lstrip('0')
                            # también admitir presencia del número como substring (por si hay prefijos)
                            mask_contains = serie.str.contains(re.escape(f), na=False)
                            mask_exact = mask_exact | (mask_num | mask_contains)
                        else:
                            mask_exact = mask_exact | (serie.str.strip() == f)
                    if mask_exact.any():
                        resultados = _ordenar_por_relevancia(df[mask_exact], tokens, [campo])
                        return resultados, {'tokens': tokens, 'match_field': campo, 'match': 'exact', 'rapidfuzz': False}

                # 2) Búsqueda por substring (vectorizada)
                if filtros:
                    # Si todos los filtros son numéricos y el campo es COTIZACION, buscar por presencia de números
                    if campo in ['COTIZACION', 'IDENTIFICACION_INTERNA', 'REFERENCIA_INTERNA'] and all(f.isdigit() for f in filtros):
                        mask_sub = _pd.Series(False, index=df.index)
                        for f in filtros:
                            mask_sub = mask_sub | serie.str.contains(re.escape(f), na=False)
                    else:
                        pattern = '|'.join([re.escape(f) for f in filtros])
                        mask_sub = serie.str.contains(pattern, na=False)

                    if mask_sub.any():
                        resultados = _ordenar_por_relevancia(df[mask_sub], tokens, [campo])
                        return resultados, {'tokens': tokens, 'match_field': campo, 'match': 'partial', 'rapidfuzz': False}

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
    df_busqueda = df.drop(columns=[c for c in ["ITEM", "ID", "AÑO"] if c in df.columns])
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

        mask_token = df_busqueda.astype(str).apply(lambda fila: fila_coincide(fila.str.lower()), axis=1)
        mask = mask & mask_token

    resultados = df[mask]
    resultados = _ordenar_por_relevancia(resultados, tokens, campos_objetivo)
    # Devolver también los tokens usados para resaltado
    return resultados, {'tokens': tokens, 'estado_tokens': estado_tokens, 'otros_tokens': otros_tokens, 'rapidfuzz': rapidfuzz_available}