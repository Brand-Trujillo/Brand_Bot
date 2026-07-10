def mostrar_resultados(resultado, intencion):
    total = len(resultado)
    max_items = 8
    print(f"\n🤖 Encontré {total} muestra(s).")
    if total > max_items:
        print(f"Mostrando solo las primeras {max_items}. Puedes afinar por cliente, estado, informe o cotización.\n")
    else:
        print("")

    for _, fila in resultado.head(max_items).iterrows():

        fecha = fila["FECHA_INGRESO"]
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")

        print(f"📦 Cliente: {fila['CLIENTE']}")
        print(f"🆔 Ref. interna: {fila.get('REFERENCIA_INTERNA', fila.get('ID', 'N/E'))}")
        print(f"📄 Informe: {fila.get('INFORME', 'N/E')}")
        print(f"💰 Cotización: {fila.get('COTIZACION', 'N/E')}")

        if intencion == "ubicacion":
            print(f"📍 Ubicación: {fila['UBICACION']}")

        elif intencion == "estado":
            print(f"📌 Estado: {fila['ESTADO']}")

        elif intencion == "fecha":
            print(f"📅 Fecha ingreso: {fecha}")

        elif intencion == "marca":
            print(f"🔖 Marca: {fila['MARCA']}")

        else:
            print(f"📍 Ubicación: {fila['UBICACION']}")
            print(f"📌 Estado: {fila['ESTADO']}")
            print(f"📅 Fecha ingreso: {fecha}")

        print("-" * 45)