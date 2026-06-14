"""
app_de_terminal/ui/app.py
=========================
TUI de iico-agent construida con Textual.

Esta capa SOLO se encarga de:
  1. Capturar input del usuario
  2. Pasarlo al Harness
  3. Renderizar los HarnessEvents que recibe

Toda la lógica de negocio (providers, memoria, system prompt, etc.)
vive en iico_core — esta UI no sabe nada de LLMs ni de Ollama.
"""

import sys
from pathlib import Path

# Asegurar que iico_core sea importable (funciona tanto con pip install -e .
# como corriendo directamente desde app_de_terminal/)
_root = Path(__file__).parent.parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from textual.app import App, ComposeResult
from textual.containers import Container, VerticalScroll, Horizontal
from textual.widgets import Header, Footer, Static, Input, OptionList, Label
from textual.widgets.option_list import Option
from textual.binding import Binding
from textual import events, on
from textual.reactive import reactive

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


# Iconos de estado para la barra de agente
_STATE_LABELS = {
    AgentState.IDLE:              ("[dim]⬤[/dim]",  "Listo"),
    AgentState.INTERVIEWING:      ("[yellow]⬤[/yellow]", "Entrevistando..."),
    AgentState.PLANNING:          ("[cyan]⬤[/cyan]",  "Planificando..."),
    AgentState.AWAITING_APPROVAL: ("[#ffaa00]⬤[/#ffaa00]", "Esperando aprobación"),
    AgentState.EXECUTING:         ("[green]⬤[/green]", "Ejecutando"),
    AgentState.VERIFYING:         ("[blue]⬤[/blue]",  "Verificando"),
}


class ChatMessage(Static):
    def __init__(self, role: str, content: str):
        super().__init__()
        self.role = role
        self.content = content

    def render(self) -> str:
        if self.role == "system":
            return f"[i #888888]{self.content}[/i #888888]"
        if self.role == "thinking":
            return f"[i #444488]🤔 {self.content}[/i #444488]"
        if self.role == "skill":
            return f"[dim]⚙ {self.content}[/dim]"
        prefix = "[b #004a98]iico[/b #004a98]" if self.role == "assistant" else "[b #e0e0e0]Tú[/b #e0e0e0]"
        return f"{prefix}: {self.content}"


class IicoApp(App):
    TITLE = "iico-agent"
    CSS_PATH = "styles.tcss"
    BINDINGS = [
        Binding("ctrl+c", "quit", "Salir", priority=True),
        Binding("ctrl+l", "clear_chat", "Limpiar", priority=True),
        Binding("ctrl+s", "open_settings", "Settings", priority=True),
    ]

    def __init__(self):
        super().__init__()
        self.harness: Harness | None = None
        self.is_generating = False
        self.all_models: dict = {}

    # ------------------------------------------------------------------
    # Ciclo de vida
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        active_id = config_manager.get_active_model_id()
        if active_id:
            self._setup_harness_from_id(active_id)
        self.run_worker(self._fetch_all_models())

    async def _fetch_all_models(self):
        providers = config_manager.get_providers()

        async def fetch_one(p):
            p_type = p["type"]
            ep = p["endpoint"]
            group_name = f"{p_type} ({ep})"
            if p_type == "openai":
                client = OpenAIClient(ep, "")
            else:
                from iico_core.llm_client import OllamaClient
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
        # Actualizar barra de estado
        try:
            self._refresh_state_bar()
        except Exception:
            pass  # La UI puede no estar montada aún

    # ------------------------------------------------------------------
    # Composición de la UI
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        # Barra de estado del agente (Fase 3)
        with Horizontal(id="agent-status-bar"):
            yield Label("[dim]⬤[/dim]", id="state-icon")
            yield Label("Listo", id="state-label")
            yield Label("", id="state-task")
        with Container(id="main-container"):
            yield Static(LOGO, id="logo")
            with VerticalScroll(id="chat-area"):
                yield Static(
                    "[i]Bienvenido a iico-agent. Escribe un mensaje abajo y presiona Enter.[/i]",
                    id="welcome-msg",
                )
            yield OptionList(id="cmd-options")
            yield Input(placeholder="Escribe tu mensaje aquí...", id="chat-input")
        yield Footer()

    # ------------------------------------------------------------------
    # Manejo de input
    # ------------------------------------------------------------------

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if self.is_generating or not event.value.strip():
            return

        user_text = event.value.strip()
        event.input.value = ""
        chat_area = self.query_one("#chat-area")

        # ── Comandos de UI (modelo/provider) que el Harness no conoce ──
        if user_text.startswith("/model") or user_text.startswith("/provider"):
            await self._handle_ui_command(user_text, chat_area)
            return

        # ── Sin Harness configurado ──
        if not self.harness:
            chat_area.mount(ChatMessage(
                "system",
                "Error: No hay ningún modelo activo. Usa /model <nombre> o /provider <tipo> <endpoint>."
            ))
            chat_area.scroll_end(animate=False)
            return

        # ── Mensaje normal o comando del Harness (/clear, /memory, etc.) ──
        chat_area.mount(ChatMessage("user", user_text))
        chat_area.scroll_end(animate=False)

        assistant_widget = ChatMessage("assistant", "")
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
                    # Mostrar el estado de razonamiento en la barra
                    self._set_state_task(str(event.payload))
                    # También mostrar brevemente en el chat si está pensando mucho
                    if thinking_widget is None:
                        thinking_widget = ChatMessage("thinking", str(event.payload))
                        chat_area.mount(thinking_widget)
                    else:
                        thinking_widget.content = str(event.payload)
                        thinking_widget.refresh()
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.SKILL_START:
                    skill_name = str(event.payload)
                    self._set_state_task(f"⚙ Ejecutando: {skill_name}")
                    chat_area.mount(ChatMessage("skill", f"Ejecutando skill: {skill_name}..."))
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.SKILL_DONE:
                    payload = event.payload
                    if isinstance(payload, dict):
                        skill = payload.get("skill", "")
                        ok = payload.get("success", True)
                        icon = "✅" if ok else "❌"
                        chat_area.mount(ChatMessage("skill", f"{icon} {skill}"))
                    self._set_state_task("")
                    chat_area.scroll_end(animate=False)

                elif event.type == HarnessEventType.STATE_CHANGED:
                    # Actualizar barra de agente + mensaje en chat
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
                    # Mensaje especial para preguntas de la entrevista SDD
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
                    # Limpiar el widget de thinking si existe
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
                    sys_msg = f"Modelo '{val}' no encontrado. Usa /model <nombre> con un modelo disponible."
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

    def action_clear_chat(self) -> None:
        if not self.is_generating:
            if self.harness:
                self.harness.clear_history()
            chat_area = self.query_one("#chat-area")
            for child in chat_area.children:
                if child.id != "welcome-msg":
                    child.remove()

    def action_open_settings(self) -> None:
        """Abre la pantalla modal de configuración."""
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

    def _on_settings_closed(self, result) -> None:
        """
        Callback que recibe el SettingsChanged cuando el usuario presiona Aplicar.
        Aplica los cambios al Harness en caliente sin reiniciarlo por completo.
        """
        if result is None or not isinstance(result, SettingsChanged):
            return  # El usuario canceló

        if self.harness is None:
            return

        cfg = self.harness.config

        # Actualizar flags
        cfg.use_passive_memory    = result.use_passive_memory
        cfg.use_splay_tree        = result.use_splay_tree
        cfg.use_skills            = result.use_skills
        cfg.splay_cache_size      = result.splay_cache_size
        cfg.max_context_notes     = result.max_context_notes
        cfg.splay_peek_top        = result.splay_peek_top

        # Umbral de embeddings: no requiere reinicio
        cfg.embedding_threshold   = result.embedding_threshold
        if self.harness._embedding_index is not None:
            # Actualizar el índice directamente si ya estaba cargado
            pass  # El threshold se lee en cada llamada a search(), no hay que reiniciar

        # Embeddings: si se activa y no estaba inicializado, construir el índice
        if result.use_embedding_search and not cfg.use_embedding_search:
            cfg.use_embedding_search = True
            self.harness._init_embedding_index()
        elif not result.use_embedding_search:
            cfg.use_embedding_search = False
            self.harness._embedding_index = None

        # Skills: si se activa y no había registry, cargarlo
        if result.use_skills and self.harness._skill_registry is None:
            from iico_core.memory.active import SkillRegistry
            from iico_core.bridge.shell import ShellBridge
            self.harness._skill_registry = SkillRegistry(cfg.skills_path)
            self.harness._bridge = ShellBridge(default_timeout=cfg.skill_timeout)
        elif not result.use_skills:
            self.harness._skill_registry = None
            self.harness._bridge = None

        chat_area = self.query_one("#chat-area")
        flags_summary = (
            f"[bold #66a3ff]Configuración aplicada:[/bold #66a3ff] "
            f"Memoria={'ON' if cfg.use_passive_memory else 'OFF'} | "
            f"Splay={'ON' if cfg.use_splay_tree else 'OFF'} | "
            f"Embeddings={'ON' if cfg.use_embedding_search else 'OFF'} (umbral={cfg.embedding_threshold:.2f}) | "
            f"Skills={'ON' if cfg.use_skills else 'OFF'} | "
            f"Nodos Splay={cfg.splay_cache_size} | "
            f"Notas={cfg.max_context_notes}"
        )
        chat_area.mount(ChatMessage("system", flags_summary))
        chat_area.scroll_end(animate=False)


    # ------------------------------------------------------------------
    # Helpers de barra de estado del agente (Fase 3)
    # ------------------------------------------------------------------

    def _refresh_state_bar(self) -> None:
        """Actualiza el ícono y texto de la barra de estado según el estado del Harness."""
        try:
            icon_widget = self.query_one("#state-icon", Label)
            label_widget = self.query_one("#state-label", Label)
        except Exception:
            return

        state = AgentState.IDLE
        if self.harness and hasattr(self.harness, "_state"):
            state = self.harness._state

        icon, text = _STATE_LABELS.get(state, ("[dim]⬤[/dim]", "Listo"))
        icon_widget.update(icon)
        label_widget.update(text)

    def _set_state_task(self, task_text: str) -> None:
        """Actualiza el texto de la tarea actual en la barra de estado."""
        try:
            task_widget = self.query_one("#state-task", Label)
            task_widget.update(f" — {task_text}" if task_text else "")
        except Exception:
            pass


if __name__ == "__main__":
    app = IicoApp()
    app.run()
