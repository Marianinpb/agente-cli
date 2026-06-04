# iico-agent

**iico-agent** es una Interfaz de Usuario de Terminal (TUI) para interactuar con modelos de lenguaje grandes (LLMs) locales y remotos.

## 🚀 Características Principales

- **Soporte de Proveedores**: Conéctate a **Ollama** y APIs compatibles con **OpenAI**.
- **Streaming**: Respuestas generadas y mostradas en tiempo real.
- **Comandos Dinámicos**: Configura tu proveedor y modelo directamente desde el chat.
- **Historial de Conversación**: Mantiene el contexto de los mensajes a lo largo de tu sesión de chat.

## 📦 Instalación

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

## 💻 Uso

Para iniciar el agente, ejecuta:

```bash
python main.py
```

### ⌨️ Comandos de Chat y Atajos

Puedes escribir estos comandos directamente en la barra de texto principal. Al presionar `/`, aparecerá un menú flotante autocompletable:

- `/model <nombre>`: Cambia el modelo en uso.
- `/provider <ollama|openai> <endpoint>`: Agrega un proveedor y su endpoint (ej. `/provider ollama http://localhost:11434`).
- `/clear`: Limpia el historial de la conversación actual.

**Atajos de Teclado:**
- `Ctrl+C`: Salir de la aplicación.
- `Ctrl+L`: Limpiar el chat.

---

> Construido con ❤️ usando Python y [Textual](https://github.com/Textualize/textual).
