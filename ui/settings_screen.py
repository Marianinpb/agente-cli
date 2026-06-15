"""
app_de_terminal/ui/settings_screen.py
=======================================
Pantalla de Configuración de iico-agent.

Permite ajustar todos los flags y parámetros del HarnessConfig
en tiempo real sin tocar el código:
  - Flags on/off (Switch): memoria pasiva, splay tree, embeddings, skills
  - Umbral de embeddings (Input numérico)
  - Máx. nodos Splay (Input numérico)
  - Máx. notas en contexto (Input numérico)

Cuando el usuario presiona "Aplicar", se emite el mensaje
`SettingsChanged` que el IicoApp captura y reconfigura el Harness.
"""

from __future__ import annotations

from dataclasses import dataclass

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Digits,
    Footer,
    Header,
    Input,
    Label,
    Rule,
    Static,
    Switch,
)


# ---------------------------------------------------------------------------
# Mensaje que la pantalla emite al IicoApp
# ---------------------------------------------------------------------------

@dataclass
class SettingsChanged(Message):
    """Emitido cuando el usuario confirma cambios en la pantalla de settings."""
    use_passive_memory: bool
    use_splay_tree: bool
    use_embedding_search: bool
    use_skills: bool
    use_react_loop: bool
    require_command_confirmation: bool
    embedding_threshold: float
    splay_cache_size: int
    max_context_notes: int
    splay_peek_top: int
    skill_timeout: float
    token_budget: int


# ---------------------------------------------------------------------------
# Pantalla modal de configuración
# ---------------------------------------------------------------------------

class SettingsScreen(ModalScreen):
    """
    Pantalla modal de configuración. Se abre con Ctrl+S.
    Muestra todos los knobs del HarnessConfig como controles interactivos.
    """

    CSS = """
    SettingsScreen {
        align: center middle;
    }

    #settings-dialog {
        width: 70;
        height: auto;
        max-height: 85vh;
        background: $surface;
        border: thick #004a98;
        padding: 1 2;
    }

    #settings-title {
        text-align: center;
        color: #66a3ff;
        text-style: bold;
        margin-bottom: 1;
    }

    .section-label {
        color: #004a98;
        text-style: bold;
        margin-top: 1;
        margin-bottom: 0;
    }

    .setting-row {
        height: 3;
        margin-bottom: 0;
        align: left middle;
    }

    .setting-label {
        width: 36;
        color: $text;
        content-align: left middle;
        height: 3;
    }

    .setting-desc {
        color: $text-muted;
        text-style: italic;
        margin-left: 2;
        margin-bottom: 1;
    }

    Switch {
        height: 3;
    }

    .num-input {
        width: 8;
        border: round #004a98;
    }

    .num-input:focus {
        border: round #66a3ff;
    }

    #btn-row {
        margin-top: 2;
        align: right middle;
        height: 3;
    }

    #btn-apply {
        background: #004a98;
        color: white;
        margin-right: 1;
    }

    #btn-apply:hover {
        background: #66a3ff;
    }

    #btn-cancel {
        background: $boost;
        color: $text-muted;
    }

    #btn-cancel:hover {
        color: $text;
    }

    #threshold-hint {
        color: $text-muted;
        text-style: italic;
        margin-left: 2;
        margin-bottom: 1;
    }
    """

    BINDINGS = [
        Binding("escape", "dismiss", "Cerrar"),
    ]

    def __init__(self, current_config):
        super().__init__()
        self._cfg = current_config

    def compose(self) -> ComposeResult:
        cfg = self._cfg
        with Container(id="settings-dialog"):
            yield Static("⚙  Configuración de iico-agent", id="settings-title")
            yield Rule()

            with VerticalScroll():
                # ── Características (Flags) ──────────────────────────────
                yield Static("CARACTERÍSTICAS", classes="section-label")
                yield Rule()

                # Memoria Pasiva
                with Horizontal(classes="setting-row"):
                    yield Label("Memoria Pasiva (notas .md)", classes="setting-label")
                    yield Switch(
                        value=cfg.use_passive_memory,
                        id="sw-passive-memory",
                    )
                yield Static(
                    "Carga notas de memory_store/ y las inyecta al prompt",
                    classes="setting-desc",
                )

                # Splay Tree
                with Horizontal(classes="setting-row"):
                    yield Label("Caché Splay Tree (Nivel 2)", classes="setting-label")
                    yield Switch(
                        value=cfg.use_splay_tree,
                        id="sw-splay-tree",
                    )
                yield Static(
                    "Caché rápida de localidad temporal sobre las notas recientes",
                    classes="setting-desc",
                )

                # Embeddings
                with Horizontal(classes="setting-row"):
                    yield Label("Búsqueda Semántica (Nivel 1)", classes="setting-label")
                    yield Switch(
                        value=cfg.use_embedding_search,
                        id="sw-embeddings",
                    )
                yield Static(
                    "Requiere iico-core[embeddings]. Usa ONNX + MiniLM-L6-v2",
                    classes="setting-desc",
                )

                # Skills
                with Horizontal(classes="setting-row"):
                    yield Label("Skills / Herramientas", classes="setting-label")
                    yield Switch(
                        value=cfg.use_skills,
                        id="sw-skills",
                    )
                yield Static(
                    "Activa SkillRegistry + ShellBridge para ejecutar tools externas",
                    classes="setting-desc",
                )

                # ReAct Loop
                with Horizontal(classes="setting-row"):
                    yield Label("ReAct Loop (Agente Autónomo)", classes="setting-label")
                    yield Switch(
                        value=cfg.use_react_loop,
                        id="sw-react-loop",
                    )
                yield Static(
                    "Activa el bucle de razonamiento ReAct para ejecutar tareas automáticamente",
                    classes="setting-desc",
                )

                # Confirmación antes de correr comandos de terminal
                with Horizontal(classes="setting-row"):
                    yield Label("Confirmar comandos de terminal", classes="setting-label")
                    yield Switch(
                        value=cfg.require_command_confirmation,
                        id="sw-cmd-confirm",
                    )
                yield Static(
                    "Preguntar al usuario antes de ejecutar run_command en la terminal",
                    classes="setting-desc",
                )

                # ── Parámetros numéricos ─────────────────────────────────
                yield Static("PARÁMETROS", classes="section-label")
                yield Rule()

                # Umbral de embeddings
                with Horizontal(classes="setting-row"):
                    yield Label("Umbral de similitud (0.0 – 1.0)", classes="setting-label")
                    yield Input(
                        value=str(cfg.embedding_threshold),
                        id="inp-threshold",
                        classes="num-input",
                    )
                yield Static(
                    f"Actual: {cfg.embedding_threshold:.2f}  |  MiniLM en español: 0.40–0.65 recomendado",
                    id="threshold-hint",
                )

                # Máx. nodos Splay
                with Horizontal(classes="setting-row"):
                    yield Label("Máx. nodos en Splay Tree", classes="setting-label")
                    yield Input(
                        value=str(cfg.splay_cache_size),
                        id="inp-splay-size",
                        classes="num-input",
                    )
                yield Static(
                    "Cuántas notas puede guardar la caché rápida antes de evictar",
                    classes="setting-desc",
                )

                # Máx. notas en contexto
                with Horizontal(classes="setting-row"):
                    yield Label("Máx. notas en contexto (prompt)", classes="setting-label")
                    yield Input(
                        value=str(cfg.max_context_notes),
                        id="inp-max-notes",
                        classes="num-input",
                    )
                yield Static(
                    "Cuántas notas se inyectan al system prompt por turno",
                    classes="setting-desc",
                )

                # Splay peek top
                with Horizontal(classes="setting-row"):
                    yield Label("Nodos Splay a revisar (peek)", classes="setting-label")
                    yield Input(
                        value=str(cfg.splay_peek_top),
                        id="inp-splay-peek",
                        classes="num-input",
                    )
                yield Static(
                    "Cuántos nodos del tope del árbol se inspeccionan antes de vectorizar",
                    classes="setting-desc",
                )

                # Timeout de skills
                with Horizontal(classes="setting-row"):
                    yield Label("Timeout de Skills (seg)", classes="setting-label")
                    yield Input(
                        value=str(cfg.skill_timeout),
                        id="inp-skill-timeout",
                        classes="num-input",
                    )
                yield Static(
                    "Tiempo máximo (en segundos) para ejecutar una herramienta",
                    classes="setting-desc",
                )

                # Presupuesto de tokens
                with Horizontal(classes="setting-row"):
                    yield Label("Presupuesto de tokens", classes="setting-label")
                    yield Input(
                        value=str(cfg.token_budget),
                        id="inp-token-budget",
                        classes="num-input",
                    )
                yield Static(
                    "Límite aproximado de tokens para el system prompt",
                    classes="setting-desc",
                )

                # ── Botones ──────────────────────────────────────────────
                with Horizontal(id="btn-row"):
                    yield Button("Aplicar", id="btn-apply", variant="primary")
                    yield Button("Cancelar", id="btn-cancel")

    # ------------------------------------------------------------------
    # Eventos
    # ------------------------------------------------------------------

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-cancel":
            self.dismiss()
            return

        if event.button.id == "btn-apply":
            self._apply()

    def _apply(self) -> None:
        """Valida y emite SettingsChanged con los valores actuales de los controles."""
        errors: list[str] = []

        # Leer switches
        use_passive = self.query_one("#sw-passive-memory", Switch).value
        use_splay   = self.query_one("#sw-splay-tree", Switch).value
        use_emb     = self.query_one("#sw-embeddings", Switch).value
        use_skills  = self.query_one("#sw-skills", Switch).value
        use_react   = self.query_one("#sw-react-loop", Switch).value
        cmd_confirm = self.query_one("#sw-cmd-confirm", Switch).value

        # Leer y validar inputs numéricos
        try:
            threshold = float(self.query_one("#inp-threshold", Input).value)
            if not (0.0 <= threshold <= 1.0):
                raise ValueError("Debe estar entre 0.0 y 1.0")
        except ValueError:
            errors.append("Umbral: debe ser un número entre 0.0 y 1.0")
            threshold = self._cfg.embedding_threshold

        try:
            splay_size = int(self.query_one("#inp-splay-size", Input).value)
            if splay_size < 1:
                raise ValueError()
        except ValueError:
            errors.append("Máx. nodos Splay: debe ser un entero positivo")
            splay_size = self._cfg.splay_cache_size

        try:
            max_notes = int(self.query_one("#inp-max-notes", Input).value)
            if max_notes < 1:
                raise ValueError()
        except ValueError:
            errors.append("Máx. notas: debe ser un entero positivo")
            max_notes = self._cfg.max_context_notes

        try:
            peek_top = int(self.query_one("#inp-splay-peek", Input).value)
            if peek_top < 1:
                raise ValueError()
        except ValueError:
            errors.append("Peek top: debe ser un entero positivo")
            peek_top = self._cfg.splay_peek_top

        try:
            skill_tout = float(self.query_one("#inp-skill-timeout", Input).value)
            if skill_tout <= 0:
                raise ValueError()
        except ValueError:
            errors.append("Timeout Skills: debe ser mayor a 0")
            skill_tout = self._cfg.skill_timeout

        try:
            tok_budget = int(self.query_one("#inp-token-budget", Input).value)
            if tok_budget < 100:
                raise ValueError()
        except ValueError:
            errors.append("Token budget: debe ser mínimo 100")
            tok_budget = self._cfg.token_budget

        if errors:
            # Mostrar errores en consola (en una UI real podría ser un toast)
            self.app.notify(
                "\n".join(errors),
                title="Error de validación",
                severity="error",
            )
            return

        # Emitir mensaje al IicoApp
        self.dismiss(
            SettingsChanged(
                use_passive_memory=use_passive,
                use_splay_tree=use_splay,
                use_embedding_search=use_emb,
                use_skills=use_skills,
                use_react_loop=use_react,
                require_command_confirmation=cmd_confirm,
                embedding_threshold=threshold,
                splay_cache_size=splay_size,
                max_context_notes=max_notes,
                splay_peek_top=peek_top,
                skill_timeout=skill_tout,
                token_budget=tok_budget,
            )
        )
