# Brand_Bot WebView (Android)

Esta app abre tu chatbot web dentro de una WebView.

## Branding de inicio
- Titulo: Brand_Bot
- Subtitulo: Asistente virtual de Brandon

## Configurar URL del chatbot
Edita [app/build.gradle.kts](app/build.gradle.kts) y cambia `CHATBOT_URL` en debug/release por tu URL publica HTTPS.

Ejemplo:
- https://tu-chatbot.onrender.com

## Compilar localmente
Requisitos:
- Android Studio (recomendado) o Android SDK + JDK 17

Pasos:
1. Abre la carpeta `android-webview` en Android Studio.
2. Sincroniza Gradle.
3. Ejecuta Build > Build APK(s).
4. APK debug generado en `app/build/outputs/apk/debug/app-debug.apk`.

## Compilar en GitHub Actions
Se incluye el workflow [../.github/workflows/build-android-webview.yml](../.github/workflows/build-android-webview.yml).

1. Haz push de cambios.
2. En GitHub, abre Actions > Build Android WebView APK.
3. Descarga el artefacto `Brand_Bot-debug-apk`.
