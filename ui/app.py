from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll
from textual.widgets import Header, Footer, Static, Input, OptionList
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual import events, on

from core.config_manager import config_manager
from api.ollama_provider import OllamaProvider
from api.openai_provider import OpenAIProvider
import asyncio
from typing import List, Dict

LOGO = r"""
 [b #004a98]
  _  _                                                   _   
 (_)(_)                                                 | |  
  _  _   ___   ___   ______   __ _   __ _   ___  _ __   | |_ 
 | || | / __| / _ \ |______| / _` | / _` | / _ \| '_ \  | __|
 | || || (__ | (_) |        | (_| || (_| ||  __/| | | | | |_ 
 |_||_| \___| \___/          \__,_| \__, | \___||_| |_|  \__|
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
        self.provider = None
        self.is_generating = False
        self.all_models = {}

    def on_mount(self) -> None:
        # Recuperar estado del modelo
        active_id = config_manager.get_active_model_id()
        if active_id:
            self.setup_provider_from_id(active_id)
        self.run_worker(self.fetch_all_models())

    async def fetch_all_models(self):
        providers = config_manager.get_providers()
        
        async def fetch_provider(p):
            p_type = p["type"]
            ep = p["endpoint"]
            group_name = f"{p_type} ({ep})"
            if p_type == "openai":
                models = await OpenAIProvider.fetch_models(ep)
            else:
                models = await OllamaProvider.fetch_models(ep)
            return group_name, {"type": p_type, "endpoint": ep, "models": models}
            
        results = await asyncio.gather(*(fetch_provider(p) for p in providers))
        
        new_all_models = {}
        for group_name, data in results:
            new_all_models[group_name] = data
            
        self.all_models = new_all_models

    def setup_provider_from_id(self, model_id: str):
        parts = model_id.split("|", 2)
        if len(parts) == 3:
            p_type, ep, model = parts
            if p_type == "openai":
                self.provider = OpenAIProvider(ep, model, 0.7)
            else:
                self.provider = OllamaProvider(ep, model, 0.7)
            config_manager.set_active_model_id(model_id)

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Container(id="main-container"):
            yield Static(LOGO, id="logo")
            with VerticalScroll(id="chat-area"):
                yield Static("[i]Bienvenido a iico-agent. Escribe un mensaje abajo y presiona Enter.[/i]", id="welcome-msg")
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
                    found_id = None
                    for grp, data in self.all_models.items():
                        if val in data["models"]:
                            found_id = f"{data['type']}|{data['endpoint']}|{val}"
                            break
                    if found_id:
                        self.setup_provider_from_id(found_id)
                        sys_msg = f"Modelo activo cambiado a '{val}'"
                    else:
                        sys_msg = f"Modelo '{val}' no encontrado."
                else:
                    sys_msg = f"Uso: /model <nombre>"
            elif cmd == "/provider":
                if val:
                    p_parts = val.split(" ", 1)
                    if len(p_parts) == 2 and p_parts[0] in ["ollama", "openai"]:
                        p_type = p_parts[0]
                        ep = p_parts[1]
                        config_manager.add_provider(p_type, p_type, ep)
                        self.run_worker(self.fetch_all_models())
                        sys_msg = f"Proveedor {p_type} agregado: {ep}. Actualizando lista de modelos..."
                    else:
                        sys_msg = "Uso: /provider <ollama|openai> <endpoint>"
                else:
                    sys_msg = "Uso: /provider <ollama|openai> <endpoint>"
            elif cmd == "/clear":
                self.action_clear_chat()
                return
            else:
                sys_msg = f"Comando desconocido '{cmd}'. Comandos: /model, /provider, /clear"
                
            if sys_msg:
                chat_area.mount(ChatMessage("system", sys_msg))
                chat_area.scroll_end(animate=False)
            return

        if not self.provider:
            chat_area.mount(ChatMessage("system", "Error: No hay ningún modelo o proveedor activo. Usa /model o /provider."))
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
        if event.option.id and "|" in event.option.id:
            # Selección de un modelo
            self.setup_provider_from_id(event.option.id)
            input_widget.value = ""
            chat_area = self.query_one("#chat-area")
            model_name = event.option.id.split("|")[2]
            chat_area.mount(ChatMessage("system", f"Modelo activo cambiado a '{model_name}'"))
            chat_area.scroll_end(animate=False)
        else:
            input_widget.value = str(event.option.prompt).strip()
            if not input_widget.value.endswith(" "):
                input_widget.value += " "
        input_widget.focus()
        input_widget.action_end()
        self.query_one("#cmd-options").display = False

    async def on_input_changed(self, event: Input.Changed) -> None:
        val = event.value
        option_list = self.query_one("#cmd-options", OptionList)
        
        if val.startswith("/") and not val.startswith("/model "):
            commands = ["/model ", "/provider ", "/clear"]
            if " " not in val:
                matches = [cmd for cmd in commands if cmd.startswith(val.lower())]
                if matches:
                    option_list.clear_options()
                    option_list.add_options(matches)
                    option_list.display = True
                    return
        elif val.startswith("/model "):
            search = val[7:].strip().lower()
            option_list.clear_options()
            has_options = False
            for grp, data in self.all_models.items():
                filtered = [m for m in data["models"] if search in m.lower()]
                if filtered:
                    option_list.add_option(Option(f"=== {grp} ===", disabled=True))
                    for m in filtered:
                        m_id = f"{data['type']}|{data['endpoint']}|{m}"
                        option_list.add_option(Option(f"  {m}", id=m_id))
                    has_options = True
            if has_options:
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
