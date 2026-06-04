# iico-agent

**iico-agent** es una Interfaz de Usuario de Terminal (TUI) elegante y de alto rendimiento diseñada para interactuar con modelos de lenguaje grandes (LLMs) que se ejecutan localmente. Se inspira en proyectos como OpenCode, ofreciendo una experiencia fluida e integrada directamente en tu terminal.

## Características Principales

- **Conexión Local**: Soporte nativo para APIs compatibles con **Ollama** y **llama.cpp** (OpenAI format).
- **Streaming Asíncrono**: Respuestas generadas y mostradas en tiempo real sin bloquear la interfaz.
- **Comandos Dinámicos (Slash Commands)**: Configura tu proveedor, endpoint y modelo directamente desde la barra de chat, con un menú de autocompletado en pantalla.
- **Manejo Inteligente de Errores**: Identifica si tu servidor o contenedor Docker está apagado sin congelarse (timeout de 5 segundos) permitiéndote corregir la URL al instante.
- **Compatibilidad**: Funciona en cualquier terminal moderna de Windows, macOS o Linux, utilizando la robustez de `Textual`.

## Instalación

1. Clona este repositorio:
   ```bash
   git clone https://github.com/Marianinpb/agente-cli.git
   cd agente-cli
   ```

2. Crea un entorno virtual e inicialízalo:
   ```bash
   python -m venv venv2
   
   # En Windows:
   .\venv2\Scripts\activate
   # En Linux/macOS:
   source venv2/bin/activate
   ```

3. Instala las dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

Para iniciar el agente, asegúrate de tener tu servidor local (ej. `ollama serve` o tu contenedor de `llama.cpp`) encendido, y ejecuta:

```bash
python main.py
```

### Comandos de Chat

Puedes escribir estos comandos directamente en el input principal. Al presionar `/`, aparecerá un menú flotante autocompletable:

- `/model <nombre>`: Cambia el modelo en uso (ej. `/model llama3`).
- `/endpoint <url>`: Cambia la URL del servidor local (ej. `/endpoint http://localhost:11434`).
- `/provider <ollama|openai>`: Cambia el formato de la API. Usa `openai` si tu servidor local es **llama.cpp**.
- `/clear`: Limpia el historial de la conversación actual.

---

> Construido con Python y Textual.
