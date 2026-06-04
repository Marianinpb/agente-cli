from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, OptionList
from textual.binding import Binding
from textual import events, on

from core.config_manager import config_manager
from api.ollama_provider import OllamaProvider
from api.openai_provider import OpenAIProvider
import asyncio

LOGO = r"""
 [b #004a98]
  _  _                                       _   
 (_)(_)                                     | |  
  _  _   ___   ___  ______   __ _   __ _  __| |  
 | || | / __| / _ \|______| / _` | / _` |/ _` |  
 | || || (__ | (_) |       | (_| || (_| | (_| |  
 |_||_| \___| \___/         \__,_| \__, |\__,_|  
                                    __/ |        
                                   |___/         
[/b #004a98]
"""

class ChatMessage(Static):
    def __init__(self, role: str, content: str):
        super().__init__()
        self.role = role
        self.content = content

    def render(self) -> str:
        if self.role == "system":
            return f"[i #888888]{self.content}[/i #888888]"
        prefix = "[b #004a98]iico[/b #004a98]" if self.role == "assistant" else "[b #e0e0e0]Tú[/b #e0e0e0]"
        return f"{prefix}: {self.content}"

class IicoApp(App):
    TITLE = "iico-agent"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir", priority=True),
        Binding("ctrl+l", "clear_chat", "Limpiar", priority=True)
    ]

    def __init__(self):
        super().__init__()
        self.messages_history = []
        self.setup_provider()
        self.is_generating = False

    def setup_provider(self):
        endpoint = config_manager.get("llm", "endpoint")
        model = config_manager.get("llm", "model")
        temperature = config_manager.get("llm", "temperature")
        provider_type = config_manager.get("llm", "provider")
        
        if provider_type == "openai":
            self.provider = OpenAIProvider(endpoint, model, temperature)
        else:
            self.provider = OllamaProvider(endpoint, model, temperature)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield Static(LOGO, id="logo")
            with VerticalScroll(id="chat-area"):
                yield Static("[i]Bienvenido a iico. Escribe un mensaje abajo y presiona Enter.[/i]", id="welcome-msg")
            yield OptionList(id="cmd-options")
            yield Input(placeholder="Escribe tu mensaje aquí...", id="chat-input")
        yield Footer()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.is_generating or not event.value.strip():
            return

        user_text = event.value.strip()
        event.input.value = ""
        
        chat_area = self.query_one("#chat-area")
        
        # Parseo de comandos /
        if user_text.startswith("/"):
            parts = user_text.split(" ", 1)
            cmd = parts[0].lower()
            val = parts[1].strip() if len(parts) > 1 else ""
            
            sys_msg = ""
            if cmd == "/model":
                if val:
                    config_manager.set("llm", "model", val)
                    self.setup_provider()
                    sys_msg = f"Modelo cambiado a '{val}'"
                else:
                    sys_msg = f"Uso: /model <nombre_del_modelo>"
            elif cmd == "/endpoint":
                if val:
                    config_manager.set("llm", "endpoint", val)
                    self.setup_provider()
                    sys_msg = f"Endpoint cambiado a '{val}'"
                else:
                    sys_msg = f"Uso: /endpoint <url>"
            elif cmd == "/provider":
                if val in ["ollama", "openai"]:
                    config_manager.set("llm", "provider", val)
                    self.setup_provider()
                    sys_msg = f"Proveedor cambiado a '{val}'"
                else:
                    sys_msg = f"Uso: /provider <ollama|openai>"
            elif cmd == "/clear":
                self.action_clear_chat()
                return
            else:
                sys_msg = f"Comando desconocido '{cmd}'. Comandos: /model, /endpoint, /provider, /clear"
                
            if sys_msg:
                chat_area.mount(ChatMessage("system", sys_msg))
                chat_area.scroll_end(animate=False)
            return
            
        # Add user message
        self.messages_history.append({"role": "user", "content": user_text})
        chat_area.mount(ChatMessage("user", user_text))
        chat_area.scroll_end(animate=False)
        
        # Add placeholder for assistant message
        assistant_msg = ChatMessage("assistant", "")
        chat_area.mount(assistant_msg)
        chat_area.scroll_end(animate=False)
        
        self.is_generating = True
        self.run_worker(self.generate_response(assistant_msg))

    async def generate_response(self, assistant_msg_widget: ChatMessage) -> None:
        full_response = ""
        try:
            async for chunk in self.provider.chat_stream(self.messages_history):
                full_response += chunk
                assistant_msg_widget.content = full_response
                assistant_msg_widget.refresh()
                self.query_one("#chat-area").scroll_end(animate=False)
        except Exception as e:
            full_response += f"\nError: {str(e)}"
            assistant_msg_widget.content = full_response
            assistant_msg_widget.refresh()
            
        self.messages_history.append({"role": "assistant", "content": full_response})
        self.is_generating = False

    @on(OptionList.OptionSelected, "#cmd-options")
    def on_cmd_selected(self, event: OptionList.OptionSelected) -> None:
        input_widget = self.query_one("#chat-input", Input)
        input_widget.value = str(event.option.prompt) + " "
        input_widget.focus()
        input_widget.action_end() # Mueve el cursor al final
        self.query_one("#cmd-options").display = False

    async def on_input_changed(self, event: Input.Changed) -> None:
        val = event.value
        option_list = self.query_one("#cmd-options", OptionList)
        
        if val.startswith("/") and " " not in val:
            commands = ["/model", "/endpoint", "/provider", "/clear"]
            matches = [cmd for cmd in commands if cmd.startswith(val.lower())]
            if matches:
                option_list.clear_options()
                option_list.add_options(matches)
                option_list.display = True
                return
        
        option_list.display = False

    def on_key(self, event: events.Key) -> None:
        option_list = self.query_one("#cmd-options", OptionList)
        if option_list.display and event.key in ["down", "up", "tab"]:
            option_list.focus()

    def action_clear_chat(self) -> None:
        if not self.is_generating:
            self.messages_history.clear()
            chat_area = self.query_one("#chat-area")
            for child in chat_area.children:
                if child.id != "welcome-msg":
                    child.remove()

if __name__ == "__main__":
    app = IicoApp()
    app.run()
