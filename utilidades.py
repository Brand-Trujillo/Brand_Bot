import re

def extraer_busqueda(texto):
    numero = re.search(r"\d+", texto)

    if numero:
        return numero.group()

    return texto