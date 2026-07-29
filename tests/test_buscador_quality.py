import unittest

import pandas as pd

from buscador import buscar
from chatbot_service import _ordenar_primera_muestra, _texto_confirmacion


class TestBuscadorQuality(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.df = pd.DataFrame(
            [
                {
                    "ITEM": 1,
                    "FECHA_INGRESO": "2026-07-06",
                    "CLIENTE": "Klensam",
                    "DESCRIPCION": "Bandeja plastica",
                    "MARCA": "Klensam",
                    "REFERENCIA_MODELO": "N/E",
                    "REFERENCIA_EXTERNA": "21961",
                    "REFERENCIA_INTERNA": "2026-07-06-04",
                    "IDENTIFICACION_INTERNA": "2026-07-06-04",
                    "INFORME": "I 0704",
                    "NUMERO": "1",
                    "COTIZACION": "C 0704",
                    "UBICACION": "A1",
                    "ESTADO": "En custodia",
                    "REFERENCIA": "21961",
                    "SERIE": "2026-07-06-04",
                },
                {
                    "ITEM": 2,
                    "FECHA_INGRESO": "2026-07-10",
                    "CLIENTE": "Klensam",
                    "DESCRIPCION": "Bandeja plastica premium",
                    "MARCA": "Klensam",
                    "REFERENCIA_MODELO": "N/E",
                    "REFERENCIA_EXTERNA": "21962",
                    "REFERENCIA_INTERNA": "2026-07-10-08",
                    "IDENTIFICACION_INTERNA": "2026-07-10-08",
                    "INFORME": "I 0704",
                    "NUMERO": "1",
                    "COTIZACION": "C 0704",
                    "UBICACION": "A2",
                    "ESTADO": "Almacenado",
                    "REFERENCIA": "21962",
                    "SERIE": "2026-07-10-08",
                },
                {
                    "ITEM": 3,
                    "FECHA_INGRESO": "2026-06-30",
                    "CLIENTE": "CIDET",
                    "DESCRIPCION": "Multitoma blanca",
                    "MARCA": "VTEK",
                    "REFERENCIA_MODELO": "PC-26-120-004",
                    "REFERENCIA_EXTERNA": "PC-26-120-004",
                    "REFERENCIA_INTERNA": "2026-06-30-01",
                    "IDENTIFICACION_INTERNA": "2026-06-30-01",
                    "INFORME": "I 0690",
                    "NUMERO": "2",
                    "COTIZACION": "C 0688",
                    "UBICACION": "B1",
                    "ESTADO": "Enviado",
                    "REFERENCIA": "PC-26-120-004",
                    "SERIE": "2026-06-30-01",
                },
                {
                    "ITEM": 4,
                    "FECHA_INGRESO": "2026-07-15",
                    "CLIENTE": "CIDET",
                    "DESCRIPCION": "Tomacorriente",
                    "MARCA": "VTEK",
                    "REFERENCIA_MODELO": "PC-26-120-009",
                    "REFERENCIA_EXTERNA": "PC-26-120-009",
                    "REFERENCIA_INTERNA": "2026-07-15-02",
                    "IDENTIFICACION_INTERNA": "2026-07-15-02",
                    "INFORME": "I 0720",
                    "NUMERO": "2",
                    "COTIZACION": "C 0722",
                    "UBICACION": "B2",
                    "ESTADO": "En custodia",
                    "REFERENCIA": "PC-26-120-009",
                    "SERIE": "2026-07-15-02",
                },
                {
                    "ITEM": 5,
                    "FECHA_INGRESO": "2026-07-20",
                    "CLIENTE": "Intertek",
                    "DESCRIPCION": "Base de lampara",
                    "MARCA": "TEZZIO",
                    "REFERENCIA_MODELO": "20099",
                    "REFERENCIA_EXTERNA": "20099",
                    "REFERENCIA_INTERNA": "2026-07-20-10",
                    "IDENTIFICACION_INTERNA": "2026-07-20-10",
                    "INFORME": "I 0800",
                    "NUMERO": "1",
                    "COTIZACION": "C 0801",
                    "UBICACION": "C1",
                    "ESTADO": "Almacenado",
                    "REFERENCIA": "20099",
                    "SERIE": "2026-07-20-10",
                },
                {
                    "ITEM": 6,
                    "FECHA_INGRESO": "2026-07-25",
                    "CLIENTE": "Intertek",
                    "DESCRIPCION": "Interruptor",
                    "MARCA": "SIELU",
                    "REFERENCIA_MODELO": "20101",
                    "REFERENCIA_EXTERNA": "20101",
                    "REFERENCIA_INTERNA": "2026-07-25-11",
                    "IDENTIFICACION_INTERNA": "2026-07-25-11",
                    "INFORME": "I 0802",
                    "NUMERO": "1",
                    "COTIZACION": "C 0802",
                    "UBICACION": "C2",
                    "ESTADO": "En proceso",
                    "REFERENCIA": "20101",
                    "SERIE": "2026-07-25-11",
                },
            ]
        )

    def test_busca_informe_prefijo(self):
        resultado, meta = buscar(self.df, "I 0704")
        self.assertEqual(len(resultado), 2)
        self.assertEqual(meta.get("match"), "exact_prefix_i")

    def test_busca_cotizacion_prefijo(self):
        resultado, meta = buscar(self.df, "C 0704")
        self.assertEqual(len(resultado), 2)
        self.assertEqual(meta.get("match"), "exact_prefix_c")

    def test_busca_referencia_numerica(self):
        resultado, meta = buscar(self.df, "21961")
        self.assertEqual(len(resultado), 1)
        self.assertIn(meta.get("match"), {"exact", "partial_controlled"})

    def test_codigo_exacto_con_guiones(self):
        resultado, meta = buscar(self.df, "PC-26-120-004")
        self.assertGreaterEqual(len(resultado), 1)
        self.assertEqual(meta.get("match"), "exact_code")

    def test_codigo_por_prefijo(self):
        resultado, meta = buscar(self.df, "PC-26-120")
        self.assertGreaterEqual(len(resultado), 2)
        self.assertEqual(meta.get("match"), "prefix_code")

    def test_cliente_exacto(self):
        resultado, meta = buscar(self.df, "Klensam")
        self.assertEqual(len(resultado), 2)
        self.assertEqual(meta.get("match"), "exact_client")

    def test_estado_y_cliente(self):
        resultado, _ = buscar(self.df, "cidet custodia")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 4)

    def test_no_tokens(self):
        resultado, meta = buscar(self.df, "de la y en")
        self.assertEqual(len(resultado), 0)
        self.assertEqual(meta.get("match"), "no_tokens")

    def test_referencia_interna(self):
        resultado, _ = buscar(self.df, "2026-07-06-04")
        self.assertGreaterEqual(len(resultado), 1)
        self.assertIn(1, set(resultado["ITEM"].astype(int).tolist()))

    def test_referencia_externa(self):
        resultado, _ = buscar(self.df, "referencia externa 20099")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 5)

    def test_modelo(self):
        resultado, _ = buscar(self.df, "modelo 20101")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 6)

    def test_numeric_no_match(self):
        resultado, meta = buscar(self.df, "999999")
        self.assertEqual(len(resultado), 0)
        self.assertEqual(meta.get("match"), "numeric_no_match")

    def test_sinonimo_multitoma(self):
        resultado, _ = buscar(self.df, "extencion blanca")
        self.assertGreaterEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 3)

    def test_orden_visible_informe(self):
        resultado, _ = buscar(self.df, "I 0704")
        ordenado = _ordenar_primera_muestra(resultado)
        self.assertEqual(int(ordenado.iloc[0]["ITEM"]), 1)
        self.assertEqual(int(ordenado.iloc[1]["ITEM"]), 2)

    def test_campo_informe_numerico(self):
        resultado, _ = buscar(self.df, "informe 802")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 6)

    def test_campo_informe_con_o_en_vez_de_cero(self):
        resultado, _ = buscar(self.df, "O802")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 6)

    def test_campo_cotizacion_numerico(self):
        resultado, _ = buscar(self.df, "cotizacion 801")
        self.assertEqual(len(resultado), 1)
        self.assertEqual(int(resultado.iloc[0]["ITEM"]), 5)

    def test_confirmacion_sencilla(self):
        self.assertEqual(_texto_confirmacion("21961", "referencia", "neutral"), "Voy a buscar por referencia: 21961.")


if __name__ == "__main__":
    unittest.main()
