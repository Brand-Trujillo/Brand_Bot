from intenciones import detectar_intencion
from datos import cargar_datos
from buscador import buscar
from respuestas import mostrar_resultados
from utilidades import extraer_busqueda
from evolution_api import obtener_respuesta_evolution

df = cargar_datos()

print("=" * 55)
print("🤖      NYCE ASSISTANT - CONTROL DE MUESTRAS")
print("=" * 55)
print("Hola, soy BrandBot auxiliar virtual de Brandon.")
print("Él me creo para ayudarte a buscar información sobre las muestras que se encuentran en el laboratorio.")
print("Puedes buscar por:")
print(" • Cliente")
print(" • Descripción")
print(" • Referencia")
print(" • Informe")
print(" • Cotización")
print(" • Ubicación")
print(" • Estado")
print(" • Fecha de ingreso")
print("\nEscribe 'salir' para cerrar el programa.")
print("=" * 55)

while True:

    consulta = input("\n👤 Tú: ")

    if consulta.lower() == "salir":
        print("\n🤖 Hasta luego. 👋")
        break

    if consulta.lower() == "ayuda":
        print("\n🤖 Puedo ayudarte con lo siguiente:")
        print("• Buscar por cliente")
        print("• Buscar por descripción")
        print("• Buscar por referencia")
        print("• Consultar ubicación")
        print("• Consultar estado")
        print("• Consultar marca")
        print("• Consultar fecha de ingreso")
        print("• Escribe 'salir' para cerrar el programa")
        print("-" * 55)
        continue

    busqueda = extraer_busqueda(consulta)
    resultado, meta = buscar(df, busqueda)

    if resultado.empty:
        respuesta_api = obtener_respuesta_evolution(
            consulta,
            system_prompt=(
                "Eres un asistente de soporte para un sistema de control de muestras de laboratorio. "
                "Cuando no encuentres una muestra local, responde de forma amable y clara."
            )
        )
        print(f"\n🤖 {respuesta_api}")
    else:
        intencion = detectar_intencion(consulta)
        mostrar_resultados(resultado, intencion)