def mostrar_resultados(resultado, intencion):

    print(f"\n🤖 Encontré {len(resultado)} muestra(s).\n")

    for _, fila in resultado.iterrows():

        fecha = fila["FECHA_INGRESO"]
        if hasattr(fecha, "strftime"):
            fecha = fecha.strftime("%d/%m/%Y")

        print(f"📦 Cliente: {fila['CLIENTE']}")
        print(f"📝 Descripción: {fila['DESCRIPCION']}")
        print(f"🔖 Marca: {fila['MARCA']}")
        # Mostrar informe y cotizacion si existen
        informe = fila.get('INFORME', '')
        cotizacion = fila.get('COTIZACION', '')
        if informe:
            print(f"📄 Informe: {informe}")
        if cotizacion:
            print(f"💰 Cotización: {cotizacion}")

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