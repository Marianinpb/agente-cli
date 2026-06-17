"""
app_de_terminal/ui/app.py
=========================
TUI de iico-agent construida con Textual.

Layout (Fase 3):
    ┌─────────────────────────────────────────────────────┐
    │  Header (reloj)                                     │
    ├──────────────────────────────────────────────────── │
    │  ● Listo — <tarea actual>          [barra de estado]│
    ├─────────────┬───────────────────────────────────────┤
    │ 📁 Proyecto │  Logo / Chat                          │
    │  (árbol)   │  [minimizable con Ctrl+B]              │
    │            │  > input                               │
    └─────────────┴───────────────────────────────────────┘
    │  Footer                                             │

Esta capa SOLO se encarga de:
  1. Capturar input del usuario
  2. Pasarlo al Harness
  3. Renderizar los HarnessEvents que recibe

Toda la lógica de negocio vive en iico_core.
"""

import sys
from pathlib import Path

_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Header, Footer, Static, Input, OptionList, Label,
    DirectoryTree, Button, Switch, Rule,
)
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual import events, on

from core.config_manager import config_manager

from iico_core import Harness, HarnessConfig, HarnessEventType, ProviderConfig
from iico_core.types import AgentState
from iico_core.llm_client import OllamaClient, OpenAIClient
from .settings_screen import SettingsScreen, SettingsChanged

import asyncio


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

# Iconos de estado para la barra del agente
_STATE_LABELS = {
    AgentState.IDLE:              ("⬤",  "Listo",               "dim"),
    AgentState.INTERVIEWING:      ("⬤",  "Entrevistando...",    "yellow"),
    AgentState.PLANNING:          ("⬤",  "Planificando...",     "cyan"),
    AgentState.AWAITING_APPROVAL: ("⬤",  "Esperando aprobación","bright_yellow"),
    AgentState.EXECUTING:         ("⬤",  "Ejecutando",          "green"),
    AgentState.VERIFYING:         ("⬤",  "Verificando",         "blue"),
}


# ---------------------------------------------------------------------------
# Modal de confirmación de comandos de terminal
# ---------------------------------------------------------------------------

class ConfirmCommandScreen(ModalScreen):
    """
    Diálogo modal que pregunta al usuario si el agente puede ejecutar
    un comando en la terminal. Devuelve True (ejecutar) o False (cancelar).
    """

    DEFAULT_CSS = """
    ConfirmCommandScreen {
        align: center middle;
    }
    #confirm-dialog {
        width: 72;
        height: auto;
        max-height: 20;
        border: thick $warning;
        background: $surface;
        padding: 1 2;
    }
    #confirm-title {
        text-style: bold;
        color: $warning;
        margin-bottom: 1;
    }
    #confirm-cmd {
        background: $panel;
        padding: 0 1;
        margin-bottom: 1;
    }
    #confirm-buttons {
        align: center middle;
        height: 3;
        margin-top: 1;
    }
    #btn-confirm-yes {
        margin-right: 2;
    }
    """

    def __init__(self, command: str):
        super().__init__()
        self._command = command

    def compose(self) -> ComposeResult:
        with Container(id="confirm-dialog"):
            yield Label("⚠️  El agente quiere ejecutar en terminal:", id="confirm-title")
            yield Static(f"[b]$ {self._command}[/b]", id="confirm-cmd")
            yield Static("¿Permites que el agente ejecute este comando?")
            with Horizontal(id="confirm-buttons"):
                yield Button("✅ Ejecutar", id="btn-confirm-yes", variant="success")
                yield Button("❌ Cancelar", id="btn-confirm-no", variant="error")

    @on(Button.Pressed, "#btn-confirm-yes")
    def on_yes(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#btn-confirm-no")
    def on_no(self) -> None:
        self.dismiss(False)


# ---------------------------------------------------------------------------
# Widget de mensaje de chat
# ---------------------------------------------------------------------------

class ChatMessage(Static):
    def __init__(self, role: str, content: str):
        super().__init__()
        self.role = role
        self.content = content

    def render(self) -> str:
        if self.role == "system":
            return f"[i #888888]{self.content}[/i #888888]"
        if self.role == "thinking":
            return f"[i #5555aa]🤔 {self.content}[/i #5555aa]"
        if self.role == "skill":
            return f"[dim]⚙ {self.content}[/dim]"
        prefix = (
            "[b #004a98]iico[/b #004a98]"
            if self.role == "assistant"
            else "[b #e0e0e0]Tú[/b #e0e0e0]"
        )
        return f"{prefix}: {self.content}"


# ---------------------------------------------------------------------------
# Panel lateral: explorador de archivos
# ---------------------------------------------------------------------------

class FileExplorer(Vertical):
    """
    Panel lateral con DirectoryTree.
    - Doble clic en una carpeta → la establece como raíz del proyecto.
    - El botón "Establecer raíz" hace lo mismo con la carpeta seleccionada.
    - Ctrl+B minimiza/maximiza el panel desde la app principal.
    """

    DEFAULT_CSS = ""

    def __init__(self, initial_path: Path):
        super().__init__(id="file-explorer")
        self._current_path = initial_path
        self._selected_dir: Path | None = None

    def compose(self) -> ComposeResult:
        yield Label("📁 Explorador", id="explorer-title")
        yield Label(
            f"[dim]{self._current_path}[/dim]",
            id="explorer-root-label",
        )
        with Horizontal(id="explorer-buttons"):
            yield Button("⬆️ Subir", id="btn-up-dir", variant="default")
            yield Button("Establecer raíz", id="btn-set-root", variant="primary")
        yield DirectoryTree(str(self._current_path), id="dir-tree")

    def update_root(self, path: Path) -> None:
        """Cambia la raíz del árbol de directorios."""
        self._current_path = path
        try:
            label = self.query_one("#explorer-root-label", Label)
            label.update(f"[dim]{path}[/dim]")
            tree = self.query_one("#dir-tree", DirectoryTree)
            tree.path = str(path)
        except Exception:
            pass


# Iconos y colores para la barra de estado del agente
_STATE_LABELS: dict = {
    "IDLE":              ("⬤", "Listo",                "#888888"),
    "INTERVIEWING":      ("⬤", "Entrevistando...",     "#f0c040"),
    "PLANNING":          ("⬤", "Planificando...",      "#40d0f0"),
    "AWAITING_APPROVAL": ("⬤", "Esperando aprobación", "#f09010"),
    "EXECUTING":         ("⬤", "Ejecutando",           "#40dd60"),
    "VERIFYING":         ("⬤", "Verificando",          "#4080f0"),
}


# ---------------------------------------------------------------------------
# Aplicación principal
# ---------------------------------------------------------------------------

class IicoApp(App):
    TITLE = "iico-agent"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+q", "quit",          "Salir",      priority=True),
        Binding("ctrl+c", "ignore_ctrl_c", "Copiar",     show=False, priority=True),
        Binding("ctrl+l", "clear_chat",    "Limpiar",    priority=True),
        Binding("ctrl+s", "open_settings", "Settings",   priority=True),
        Binding("ctrl+b", "toggle_explorer","Explorador", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.harness: Harness | None = None
        self.is_generating = False
        self.all_models: dict = {}
        self._explorer_visible = True
        self._project_root: Path | None = None

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        active_id = config_manager.get_active_model_id()
        if active_id:
            self._setup_harness_from_id(active_id)
        self.run_worker(self._fetch_all_models())
        # Mostrar barra de estado inicial
        self._refresh_state_bar()

    async def _fetch_all_models(self):
        providers = config_manager.get_providers()

        async def fetch_one(p):
            p_type = p["type"]
            ep = p["endpoint"]
            group_name = f"{p_type} ({ep})"
            if p_type == "openai":
                client = OpenAIClient(ep, "")
            else:
                client = OllamaClient(ep, "")
            models = await client.fetch_models()
            return group_name, {"type": p_type, "endpoint": ep, "models": models}

        results = await asyncio.gather(*(fetch_one(p) for p in providers))
        self.all_models = {name: data for name, data in results}

    def _setup_harness_from_id(self, model_id: str) -> None:
        """Crea o reconfigura el Harness con el modelo seleccionado."""
        parts = model_id.split("|", 2)
        if len(parts) != 3:
            return
        p_type, ep, model = parts

        provider_cfg = ProviderConfig(
            type=p_type,
            endpoint=ep,
            model=model,
            temperature=0.7,
        )
        harness_cfg = HarnessConfig(
            provider=provider_cfg,
            memory_path=_root / "memory_store",
            skills_path=_root / "skills",
            use_skills=True,
            use_embedding_search=True,
            use_react_loop=True,
        )
        self.harness = Harness(harness_cfg)
        config_manager.set_active_model_id(model_id)
        self._refresh_state_bar()

    # ------------------------------------------------------------------
    # Composición del layout
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # Barra de estado del agente (siempre visible)
        with Horizontal(id="agent-status-bar"):
            yield Label("⬤", id="state-icon")
            yield Label("Listo", id="state-label")
            yield Label("", id="state-task")

        # Layout principal: explorador | chat
        with Horizontal(id="workspace"):
            # Panel izquierdo: explorador de archivos
            yield FileExplorer(initial_path=_root)

            # Panel derecho: chat
            with Vertical(id="chat-panel"):
                yield Static(LOGO, id="logo")
                with VerticalScroll(id="chat-area"):
                    yield Static(
                        "[i]Bienvenido a iico-agent.[/i]\n"
                        "[dim]Ctrl+B → explorador | Ctrl+S → ajustes | /sdd → flujo de diseño[/dim]",
                        id="welcome-msg",
                    )
                yield OptionList(id="cmd-options")
                yield Input(placeholder="Escribe tu mensaje aquí...", id="chat-input")

        yield Footer()

    # ------------------------------------------------------------------
    # Explorador: interacciones
    # ------------------------------------------------------------------

    @on(DirectoryTree.DirectorySelected, "#dir-tree")
    def on_dir_selected(self, event: DirectoryTree.DirectorySelected) -> None:
        """Guardar la carpeta seleccionada en el árbol."""
        self._selected_dir = Path(str(event.path))

    @on(DirectoryTree.FileSelected, "#dir-tree")
    def on_file_selected(self, event: DirectoryTree.FileSelected) -> None:
        """Si se selecciona un archivo, guardar su carpeta padre."""
        self._selected_dir = Path(str(event.path)).parent

    @on(Button.Pressed, "#btn-up-dir")
    def on_up_dir_pressed(self, event: Button.Pressed) -> None:
        """Sube un nivel en la jerarquía del explorador."""
        try:
            explorer = self.query_one(FileExplorer)
            parent = explorer._current_path.parent
            explorer.update_root(parent)
        except Exception:
            pass

    @on(Button.Pressed, "#btn-set-root")
    def on_set_root_pressed(self, event: Button.Pressed) -> None:
        """Establece la carpeta seleccionada como raíz del proyecto."""
        target = self._selected_dir or self._project_root
        if target and target.is_dir():
            self._set_project_root(target)
        else:
            self._notify_status("Selecciona primero una carpeta en el árbol.")

    def _set_project_root(self, path: Path) -> None:
        """Establece la raíz del proyecto en el Harness y actualiza la UI."""
        self._project_root = path

        # Actualizar el árbol visual
        try:
            explorer = self.query_one(FileExplorer)
            explorer.update_root(path)
        except Exception:
            pass

        # Notificar al Harness vía el comando slash interno
        if self.harness:
            import asyncio
            asyncio.ensure_future(self._apply_project_root_to_harness(path))

        # Mostrar en el chat
        chat_area = self.query_one("#chat-area")
        chat_area.mount(
            ChatMessage("system", f"📁 Raíz del proyecto: {path}")
        )
        chat_area.scroll_end(animate=False)

    async def _apply_project_root_to_harness(self, path: Path) -> None:
        """Aplica la raíz del proyecto al Harness directamente."""
        if not self.harness:
            return
        self.harness._project_root = path
        if self.harness._sdd_manager:
            self.harness._sdd_manager.set_project_root(path)
        if self.harness._task_manager:
            self.harness._task_manager.set_project_root(path)
        # Propagar al ShellBridge para que las skills corran en el directorio correcto
        if self.harness._bridge:
            self.harness._bridge.project_root = path

    def action_toggle_explorer(self) -> None:
        """Ctrl+B — muestra/oculta el panel del explorador."""
        try:
            explorer = self.query_one(FileExplorer)
            self._explorer_visible = not self._explorer_visible
            explorer.display = self._explorer_visible
        except Exception:
            pass

    def _notify_status(self, msg: str) -> None:
        try:
            chat_area = self.query_one("#chat-area")
            chat_area.mount(ChatMessage("system", msg))
            chat_area.scroll_end(animate=False)
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Manejo de input del chat
    # ------------------------------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.is_generating or not event.value.strip():
            return

        user_text = event.value.strip()
        event.input.value = ""
        chat_area = self.query_one("#chat-area")

        # ── Comandos de UI que el Harness no conoce ──
        if user_text.startswith("/model") or user_text.startswith("/provider"):
            await self._handle_ui_command(user_text, chat_area)
            return

        # ── /project desde chat → también actualiza el árbol ──
        if user_text.startswith("/project "):
            path_str = user_text[9:].strip()
            p = Path(path_str).expanduser().resolve()
            if p.exists() and p.is_dir():
                self._set_project_root(p)
            # También dejamos que el Harness procese el comando
            # (caerá al flujo normal de abajo)

        # ── Sin Harness configurado ──
        if not self.harness:
            chat_area.mount(ChatMessage(
                "system",
                "Error: No hay ningún modelo activo. Usa /model <nombre> o /provider <tipo> <endpoint>."
            ))
            chat_area.scroll_end(animate=False)
            return

        # ── Mensaje normal o comando del Harness ──
        chat_area.mount(ChatMessage("user", user_text))
        chat_area.scroll_end(animate=False)

        assistant_widget = ChatMessage("assistant", "▌")  # cursor inicial
        chat_area.mount(assistant_widget)
        chat_area.scroll_end(animate=False)

        self.is_generating = True
        self.run_worker(self._stream_response(user_text, assistant_widget))

    async def _stream_response(self, user_text: str, widget: ChatMessage) -> None:
        """Consume el stream de HarnessEvents y actualiza el widget del UI."""
        full_text = ""
        thinking_widget: ChatMessage | None = None
        chat_area = self.query_one("#chat-area")

        try:
            async for event in self.harness.process_input(user_text):

                if event.type == HarnessEventType.TOKEN:
                    full_text += event.payload
                    widget.content = full_text
                    widget.refresh()
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.THINKING:
                    self._set_state_task(str(event.payload))
                    # Mostrar "Ejecutando" en la barra mientras el agente razona
                    try:
                        self.query_one("#state-icon", Label).update("[#40dd60]⬤[/#40dd60]")
                        self.query_one("#state-label", Label).update("[#40dd60]Ejecutando[/#40dd60]")
                    except Exception:
                        pass
                    if thinking_widget is None:
                        thinking_widget = ChatMessage("thinking", str(event.payload))
                        chat_area.mount(thinking_widget)
                    else:
                        thinking_widget.content = str(event.payload)
                        thinking_widget.refresh()
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.SKILL_START:
                    payload = event.payload
                    if isinstance(payload, dict):
                        skill_name = payload.get("name", "")
                        args = payload.get("args", {})
                        self._set_state_task(f"⚙ {skill_name}")
                        if skill_name == "run_command" and "command" in args:
                            # Mostrar el comando real que va a ejecutar
                            chat_area.mount(ChatMessage("skill", f"🖥 $ {args['command']}"))
                        else:
                            chat_area.mount(ChatMessage("skill", f"Ejecutando: {skill_name}..."))
                    else:
                        skill_name = str(payload)
                        self._set_state_task(f"⚙ {skill_name}")
                        chat_area.mount(ChatMessage("skill", f"Ejecutando: {skill_name}..."))
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.SKILL_DONE:
                    payload = event.payload
                    if isinstance(payload, dict):
                        skill = payload.get("skill", "")
                        ok = payload.get("success", True)
                        cancelled = payload.get("cancelled", False)
                        if cancelled:
                            icon = "🚫"
                            chat_area.mount(ChatMessage("skill", f"{icon} {skill}: cancelado por el usuario"))
                        else:
                            icon = "✅" if ok else "❌"
                            chat_area.mount(ChatMessage("skill", f"{icon} {skill}"))
                    self._set_state_task("")
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.COMMAND_APPROVAL_REQUIRED:
                    command = str(event.payload)
                    # El modal bloquea hasta que el usuario decida;
                    # el Future ya existe en harness (fue creado antes del yield)
                    approved = await self.push_screen_wait(
                        ConfirmCommandScreen(command)
                    )
                    if approved:
                        self.harness.approve()
                    else:
                        self.harness.reject()

                elif event.type == HarnessEventType.STATE_CHANGED:
                    msg = str(event.payload)
                    self._refresh_state_bar()
                    chat_area.mount(ChatMessage("system", msg))
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.PLAN_PROPOSED:
                    self._refresh_state_bar()

                elif event.type in (
                    HarnessEventType.TASK_STARTED,
                    HarnessEventType.TASK_COMPLETED,
                    HarnessEventType.TASK_FAILED,
                ):
                    payload = event.payload or {}
                    if isinstance(payload, dict):
                        task_id = payload.get("id", "?")
                        if event.type == HarnessEventType.TASK_STARTED:
                            msg = f"▶ Tarea {task_id}: iniciada"
                        elif event.type == HarnessEventType.TASK_COMPLETED:
                            summary = payload.get("summary", "")[:80]
                            msg = f"✅ Tarea {task_id}: completada — {summary}"
                        else:
                            error = payload.get("error", "") or str(payload.get("failed_goals", ""))
                            msg = f"❌ Tarea {task_id}: falló — {error[:80]}"
                        chat_area.mount(ChatMessage("system", msg))
                    self._refresh_state_bar()
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.GOAL_VERIFIED:
                    payload = event.payload or {}
                    if isinstance(payload, dict):
                        goal = payload.get("goal", "")[:60]
                        met = payload.get("met", False)
                        icon = "✅" if met else "⚠️"
                        chat_area.mount(ChatMessage("skill", f"{icon} Meta: {goal}"))
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.SDD_QUESTION:
                    widget.content = str(event.payload)
                    widget.refresh()
                    self._refresh_state_bar()
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.SDD_STARTED:
                    self._refresh_state_bar()

                elif event.type == HarnessEventType.SYSTEM:
                    widget.role = "system"
                    widget.content = str(event.payload)
                    widget.refresh()
                    self._refresh_state_bar()

                elif event.type == HarnessEventType.ERROR:
                    widget.role = "system"
                    widget.content = f"[red][Error][/red] {event.payload}"
                    widget.refresh()

                elif event.type == HarnessEventType.DONE:
                    if thinking_widget:
                        thinking_widget.remove()
                        thinking_widget = None
                    self._refresh_state_bar()
                    self._set_state_task("")

        except Exception as e:
            widget.role = "system"
            widget.content = f"[Error inesperado en la UI] {e}"
            widget.refresh()
        finally:
            self.is_generating = False
            self._set_state_task("")

    # ------------------------------------------------------------------
    # Comandos de UI (modelo / provider)
    # ------------------------------------------------------------------

    async def _handle_ui_command(self, text: str, chat_area) -> None:
        parts = text.split(" ", 1)
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
                    self._setup_harness_from_id(found_id)
                    sys_msg = f"Modelo activo cambiado a '{val}'"
                else:
                    sys_msg = f"Modelo '{val}' no encontrado. Usa /model <nombre>."
            else:
                current = self.harness.model_name if self.harness else "ninguno"
                sys_msg = f"Modelo actual: {current}. Uso: /model <nombre>"

        elif cmd == "/provider":
            if val:
                p_parts = val.split(" ", 1)
                if len(p_parts) == 2 and p_parts[0] in ["ollama", "openai"]:
                    p_type, ep = p_parts
                    config_manager.add_provider(p_type, p_type, ep)
                    self.run_worker(self._fetch_all_models())
                    sys_msg = f"Proveedor {p_type} ({ep}) agregado. Actualizando lista..."
                else:
                    sys_msg = "Uso: /provider <ollama|openai> <endpoint>"
            else:
                sys_msg = "Uso: /provider <ollama|openai> <endpoint>"

        if sys_msg:
            chat_area.mount(ChatMessage("system", sys_msg))
            chat_area.scroll_end(animate=False)

    # ------------------------------------------------------------------
    # Autocompletado de comandos
    # ------------------------------------------------------------------

    @on(OptionList.OptionSelected, "#cmd-options")
    def on_cmd_selected(self, event: OptionList.OptionSelected) -> None:
        input_widget = self.query_one("#chat-input", Input)
        if event.option.id and "|" in event.option.id:
            self._setup_harness_from_id(event.option.id)
            input_widget.value = ""
            model_name = event.option.id.split("|")[2]
            self.query_one("#chat-area").mount(
                ChatMessage("system", f"Modelo activo cambiado a '{model_name}'")
            )
            self.query_one("#chat-area").scroll_end(animate=False)
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
            commands = [
                "/model ", "/provider ", "/clear", "/memory", "/memory-reload",
                "/skills", "/splay",
                # Fase 3
                "/sdd ", "/plan", "/tasks", "/project ", "/abort",
            ]
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
        option_list = self.query_one("#cmd-options")
        if option_list.display and event.key in ["down", "up", "tab"]:
            option_list.focus()

    # ------------------------------------------------------------------
    # Acciones de bindings
    # ------------------------------------------------------------------

    def action_ignore_ctrl_c(self) -> None:
        """
        No hacer nada. Evita que la app se cierre al intentar copiar texto.
        El usuario debe usar la copia nativa de su terminal.
        """
        pass

    def action_clear_chat(self) -> None:
        if not self.is_generating:
            if self.harness:
                self.harness.clear_history()
            chat_area = self.query_one("#chat-area")
            for child in list(chat_area.children):
                if child.id != "welcome-msg":
                    child.remove()

    def action_open_settings(self) -> None:
        if self.harness is None:
            self.notify(
                "Primero selecciona un modelo con /model <nombre>",
                title="Sin modelo activo",
                severity="warning",
            )
            return
        self.push_screen(
            SettingsScreen(self.harness.config),
            self._on_settings_closed,
        )

    def action_toggle_explorer(self) -> None:
        """Ctrl+B — muestra/oculta el explorador de archivos."""
        try:
            explorer = self.query_one(FileExplorer)
            self._explorer_visible = not self._explorer_visible
            explorer.display = self._explorer_visible
        except Exception:
            pass

    def _on_settings_closed(self, result) -> None:
        if result is None or not isinstance(result, SettingsChanged):
            return

        if self.harness is None:
            return

        cfg = self.harness.config
        cfg.use_passive_memory           = result.use_passive_memory
        cfg.use_splay_tree               = result.use_splay_tree
        cfg.use_skills                   = result.use_skills
        cfg.use_react_loop               = result.use_react_loop
        cfg.require_command_confirmation = result.require_command_confirmation
        cfg.splay_cache_size             = result.splay_cache_size
        cfg.max_context_notes            = result.max_context_notes
        cfg.splay_peek_top               = result.splay_peek_top
        cfg.embedding_threshold          = result.embedding_threshold
        cfg.skill_timeout                = result.skill_timeout
        cfg.token_budget                 = result.token_budget

        if result.use_embedding_search and not cfg.use_embedding_search:
            cfg.use_embedding_search = True
            self.harness._init_embedding_index()
        elif not result.use_embedding_search:
            cfg.use_embedding_search = False
            self.harness._embedding_index = None

        if result.use_skills and self.harness._skill_registry is None:
            from iico_core.memory.active import SkillRegistry
            from iico_core.bridge.shell import ShellBridge
            self.harness._skill_registry = SkillRegistry(cfg.skills_path)
            self.harness._bridge = ShellBridge(default_timeout=cfg.skill_timeout)
        elif not result.use_skills:
            self.harness._skill_registry = None
            self.harness._bridge = None
        else:
            if self.harness._bridge:
                self.harness._bridge.default_timeout = cfg.skill_timeout

        chat_area = self.query_one("#chat-area")
        flags_summary = (
            f"[bold #66a3ff]Configuración aplicada:[/bold #66a3ff] "
            f"Memoria={'ON' if cfg.use_passive_memory else 'OFF'} | "
            f"Splay={'ON' if cfg.use_splay_tree else 'OFF'} | "
            f"Embeddings={'ON' if cfg.use_embedding_search else 'OFF'} (umbral={cfg.embedding_threshold:.2f}) | "
            f"Skills={'ON' if cfg.use_skills else 'OFF'} (timeout={cfg.skill_timeout}s) | "
            f"ReAct={'ON' if cfg.use_react_loop else 'OFF'} | "
            f"Confirmar cmds={'ON' if cfg.require_command_confirmation else 'OFF'} | "
            f"Tokens={cfg.token_budget} | "
            f"Nodos Splay={cfg.splay_cache_size} | "
            f"Notas={cfg.max_context_notes}"
        )
        chat_area.mount(ChatMessage("system", flags_summary))
        chat_area.scroll_end(animate=False)

    # ------------------------------------------------------------------
    # Helpers: barra de estado del agente
    # ------------------------------------------------------------------

    def _refresh_state_bar(self) -> None:
        """Actualiza ícono y texto de la barra de estado."""
        try:
            icon_w = self.query_one("#state-icon", Label)
            label_w = self.query_one("#state-label", Label)
        except Exception:
            return

        state_key = "IDLE"
        if self.harness and hasattr(self.harness, "_state"):
            state_key = self.harness._state.name  # e.g. 'EXECUTING'

        icon, text, color = _STATE_LABELS.get(
            state_key, ("⬤", "Listo", "#888888")
        )
        icon_w.update(f"[{color}]{icon}[/{color}]")
        label_w.update(f"[{color}]{text}[/{color}]")

    def _set_state_task(self, task_text: str) -> None:
        """Actualiza el subtexto de la tarea actual en la barra."""
        try:
            task_w = self.query_one("#state-task", Label)
            task_w.update(f" — {task_text}" if task_text else "")
        except Exception:
            pass


if __name__ == "__main__":
    app = IicoApp()
    app.run()
