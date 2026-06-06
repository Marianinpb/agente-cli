# iico-agent (app_de_terminal)

**iico-agent** es una Interfaz de Usuario de Terminal (TUI) de vanguardia para interactuar con modelos de lenguaje grandes (LLMs) locales y remotos.

## 🚀 Características Principales

- **Soporte de Proveedores**: Conéctate a **Ollama** y APIs compatibles con **OpenAI**.
- **Streaming en Vivo**: Las respuestas son generadas y mostradas en tiempo real a medida que el LLM genera los tokens.
- **Configuración en Caliente (Hot-Reload)**: Modifica parámetros del agente (como umbrales de búsqueda semántica o tamaños de caché del Splay Tree) en tiempo real mediante un panel interactivo (`Ctrl+S`).
- **Historial de Conversación**: Mantiene de manera inteligente el contexto de los mensajes a lo largo de tu sesión de chat, orquestado por el Arnés subyacente.

## 🧠 Arquitectura Basada en iico-core

La TUI está ahora **completamente desacoplada** de la lógica fundamental del agente. Toda la inteligencia técnica (clientes LLM, inyección de memoria pasiva y generación dinámica del system prompt) se delega a la librería externa **`iico-core`**.

La aplicación de terminal sirve únicamente como la "capa de presentación", capturando los inputs del usuario y suscribiéndose a los *Harness Events* (eventos de streaming, ejecución de herramientas o errores) emitidos por `iico-core`.

## 📦 Instalación

Para correr esta aplicación localmente, debes asegurarte de haber instalado primero (o de forma simultánea) el paquete núcleo `iico-core`.

1. Asegúrate de estar en el directorio de la TUI:
   ```bash
   cd app_de_terminal
   ```

2. Crea y activa un entorno virtual (recomendado):
   ```bash
   python -m venv venv2
   
   # En Windows:
   .\venv2\Scripts\activate
   
   # En Linux/macOS:
   source venv2/bin/activate
   ```

3. Instala el paquete de `iico-core` (en modo editable desde su directorio) y luego instala los requisitos de la interfaz:
   ```bash
   # Instala el core que está un nivel arriba
   pip install -e ../iico-core
   
   # Instala las dependencias de la TUI (como textual y httpx)
   pip install -r requirements.txt
   ```

## 💻 Uso

Para iniciar la interfaz gráfica de terminal, ejecuta:

```bash
python main.py
```

### ⌨️ Comandos de Chat y Atajos

Dentro del campo de texto principal, puedes ingresar estos comandos (`/`). Un menú flotante aparecerá sugiriendo autocompletado:

- `/model <nombre>`: Cambia el modelo en uso para la próxima solicitud.
- `/provider <ollama|openai> <endpoint>`: Agrega un nuevo proveedor dinámicamente y configura su URI.
- `/memory`: Lista las notas de la memoria pasiva que han sido cargadas exitosamente.
- `/memory-reload`: Fuerza una recarga de todas las notas locales del disco.
- `/skills`: Muestra las herramientas (Skills) cargadas en el `SkillRegistry` del agente.
- `/splay`: Visualiza las métricas y estado del *Splay Tree* (la caché de contexto).
- `/clear`: Limpia el historial visual y semántico de la conversación activa.

**Atajos de Teclado Útiles:**
- `Ctrl+C`: Salir de la aplicación rápidamente.
- `Ctrl+L`: Limpiar el buffer de la pantalla de chat.
- `Ctrl+S`: Abrir el panel de **Configuración Interactiva** para modificar parámetros del `Harness` en tiempo real.

---

> Construido con ❤️ usando Python, **iico-core**, y [Textual](https://github.com/Textualize/textual).
