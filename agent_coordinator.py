"""
Coordinador para sistema multi-agente.

Gestiona el estado compartido de actividades usando SQLite (WAL mode),
tracking de aprobaciones (4 por actividad) y timeout de 2 minutos.

Reemplaza el antiguo sistema JSON + FileLock por db_manager.
"""

import os
import time
from datetime import datetime, timedelta
from typing import Dict, List

import db_manager


class AgentCoordinator:
    """Coordina múltiples agentes trabajando en paralelo."""

    MAX_AGENTS = 1

    def __init__(self, state_file: str = "agents_state.md", timeout_seconds: int = 120):
        """
        Args:
            state_file: Ruta al archivo MD de estado compartido.
            timeout_seconds: Segundos antes de liberar actividad inactiva.
        """
        self.state_file = state_file
        self.timeout_seconds = timeout_seconds

        # Inicializar BD y migrar datos legacy si existen
        db_manager.init_db()
        db_manager.migrate_from_json()

        self._last_md_write: float = 0.0
        self._update_markdown()

    # ── Transacción atómica ────────────────────────────────────────────────

    def _atomic_update(self, callback) -> bool:
        """
        Ejecuta load-modify-save dentro de una sola transacción SQLite.
        El bloqueo lo gestiona la BD (WAL + busy_timeout), sin locks externos.

        Args:
            callback: Función que recibe el state dict y lo modifica in-place.
                      Debe retornar True si hubo cambios, False en otro caso.

        Returns:
            True si el callback reportó cambios, False en otro caso.
        """
        conn = db_manager._get_connection()
        conn.execute("BEGIN")
        try:
            state = db_manager.load_agents_state(conn)
            changed = callback(state)
            if changed:
                db_manager.save_agents_state(state, conn)
            conn.commit()
            return changed
        except Exception:
            conn.rollback()
            raise

    def _read_state(self) -> Dict:
        """Lectura rápida del estado completo (sin transacción)."""
        return db_manager.load_agents_state()

    # ── Markdown (solo lectura) ────────────────────────────────────────────

    def _update_markdown(self):
        """Actualiza el archivo MD legible (throttled a 5 s)."""
        now = time.time()
        if now - self._last_md_write < 5.0:
            return
        self._last_md_write = now

        state = self._read_state()

        lines = [
            "# Estado de Actividades Multi-Agente (Modo Cooperativo)",
            f"*Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            "",
        ]

        if not state:
            lines.append("*No hay actividades registradas aún*")
        else:
            for activity_key, data in sorted(state.items()):
                lines.append(f"## Actividad: {activity_key}")
                lines.append(f"- **Estado:** {data.get('status', 'Desconocido')}")

                agents = data.get("agents", [])
                if isinstance(agents, list):
                    agents_str = ", ".join(agents) if agents else "-"
                else:
                    agents_str = str(data.get("agent_id", "-"))

                lines.append(f"- **Agentes:** {agents_str}")
                lines.append(f"- **Progreso:** {data.get('approvals', 0)}/4 aprobaciones")

                if data.get("questions_done") and data.get("questions_total"):
                    lines.append(
                        f"- **Preguntas Actuales:** {data['questions_done']}/{data['questions_total']}"
                    )

                lines.append(f"- **Última Actualización:** {data.get('last_update', '-')}")

                if data.get("event"):
                    lines.append(f"- **Evento:** {data['event']}")

                lines.append("")

        with open(self.state_file, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))

    # ── Métodos públicos (API idéntica a la anterior) ──────────────────────

    def claim_activity(self, agent_id: str, activity_key: str) -> bool:
        """Intenta reclamar una actividad para un agente. Atómico."""
        result = [False]

        def _do_claim(state):
            # --- Early exit: ya completada ---
            if activity_key in state and state[activity_key].get("approvals", 0) >= 4:
                result[0] = False
                return False

            # --- Early exit: agente ya en la lista ---
            if activity_key in state:
                current_agents = state[activity_key].get("agents", [])
                if not isinstance(current_agents, list):
                    old_agent = state[activity_key].get("agent_id")
                    current_agents = [old_agent] if old_agent and old_agent != "-" else []
                    state[activity_key]["agents"] = current_agents

                if agent_id in current_agents:
                    result[0] = True
                    return False

            # --- Verificar cupo y timeout ---
            if activity_key in state:
                current_agents = state[activity_key].get("agents", [])
                if not isinstance(current_agents, list):
                    old_agent = state[activity_key].get("agent_id")
                    current_agents = [old_agent] if old_agent and old_agent != "-" else []
                    state[activity_key]["agents"] = current_agents

                if len(current_agents) >= self.MAX_AGENTS:
                    last_update = datetime.fromisoformat(
                        state[activity_key].get("last_update", "1970-01-01T00:00:00")
                    )
                    if datetime.now() - last_update < timedelta(seconds=self.timeout_seconds):
                        result[0] = False
                        return False

                    print(f"[INFO] Timeout detectado para {activity_key}, "
                          f"reiniciando lista de agentes...")
                    state[activity_key]["agents"] = []
                    current_agents = []

            # --- Crear si es nueva ---
            if activity_key not in state:
                state[activity_key] = {
                    "approvals": 0,
                    "questions_done": 0,
                    "questions_total": 0,
                    "agents": [],
                }

            # Migrar legacy
            if "agents" not in state[activity_key]:
                state[activity_key]["agents"] = []
                old = state[activity_key].get("agent_id")
                if old and old != "-":
                    state[activity_key]["agents"].append(old)

            current_agents = state[activity_key]["agents"]
            if agent_id not in current_agents:
                current_agents.append(agent_id)

            state[activity_key]["agents"] = current_agents
            state[activity_key].update({
                "status": "En Progreso",
                "last_update": datetime.now().isoformat(),
                "event": f"{agent_id} se uni\u00f3 a la actividad "
                         f"({len(current_agents)}/{self.MAX_AGENTS} agentes)",
            })
            state[activity_key].pop("agent_id", None)

            result[0] = True
            return True

        changed = self._atomic_update(_do_claim)
        self._update_markdown()

        if result[0]:
            agents_count = len(
                self._read_state().get(activity_key, {}).get("agents", [])
            )
            print(f"[COORDINATOR] {agent_id} reclam\u00f3 {activity_key} "
                  f"(Total: {agents_count})")

        return result[0]

    def update_heartbeat(self, agent_id: str, activity_key: str,
                         questions_done: int, questions_total: int):
        """Actualiza el timestamp de una actividad. Atómico."""

        def _do_heartbeat(state):
            if activity_key not in state:
                return False

            agents = state[activity_key].get("agents", [])
            if not isinstance(agents, list):
                agents = [state[activity_key].get("agent_id")] \
                    if state[activity_key].get("agent_id") else []

            if agent_id not in agents:
                if len(agents) < self.MAX_AGENTS:
                    agents.append(agent_id)
                    state[activity_key]["agents"] = agents
                    state[activity_key]["status"] = "En Progreso"
                else:
                    print(f"[WARNING] {agent_id} intent\u00f3 actualizar "
                          f"actividad donde no est\u00e1 registrado: {activity_key}")
                    return False

            state[activity_key].update({
                "questions_done": questions_done,
                "questions_total": questions_total,
                "last_update": datetime.now().isoformat(),
            })
            return True

        self._atomic_update(_do_heartbeat)
        self._update_markdown()

    def complete_approval(self, agent_id: str, activity_key: str):
        """Registra una aprobaci\u00f3n. Atómico."""

        def _do_approval(state):
            if activity_key not in state:
                return False

            current = state[activity_key].get("approvals", 0)
            new_approvals = current + 1

            state[activity_key].update({
                "approvals": new_approvals,
                "questions_done": 0,
                "last_update": datetime.now().isoformat(),
                "event": f"{agent_id} complet\u00f3 aprobaci\u00f3n {new_approvals}/4",
            })

            if new_approvals >= 4:
                state[activity_key]["status"] = "Completada 100%"
                state[activity_key]["event"] = \
                    f"{agent_id} complet\u00f3 la actividad al 100% (4/4 aprobaciones)"
                state[activity_key]["agents"] = []

            return True

        changed = self._atomic_update(_do_approval)
        self._update_markdown()

        if changed:
            new_val = self._read_state().get(activity_key, {}).get("approvals", 0)
            print(f"[COORDINATOR] {agent_id} complet\u00f3 aprobaci\u00f3n "
                  f"{new_val}/4 de {activity_key}")

    def release_activity(self, agent_id: str, activity_key: str,
                         reason: str = "Liberada"):
        """Libera una actividad. Atómico."""

        def _do_release(state):
            if activity_key not in state:
                return False

            agents = state[activity_key].get("agents", [])
            if not isinstance(agents, list):
                agents = [state[activity_key].get("agent_id")] \
                    if state[activity_key].get("agent_id") else []

            if agent_id not in agents:
                return False

            agents.remove(agent_id)
            state[activity_key]["agents"] = agents

            if not agents:
                if state[activity_key].get("approvals", 0) >= 4:
                    state[activity_key]["status"] = "Completada 100%"
                else:
                    state[activity_key]["status"] = "Disponible"
                state[activity_key]["event"] = \
                    f"{agent_id} liber\u00f3: {reason} (Vac\u00eda)"
            else:
                state[activity_key]["event"] = \
                    f"{agent_id} sali\u00f3: {reason} " \
                    f"(Quedan: {', '.join(agents)})"

            state[activity_key]["last_update"] = datetime.now().isoformat()
            return True

        changed = self._atomic_update(_do_release)
        self._update_markdown()

        if changed:
            print(f"[COORDINATOR] {agent_id} dej\u00f3 {activity_key}: {reason}")

    def check_timeouts(self) -> bool:
        """Marca actividades inactivas como timeout. Atómico.

        Returns:
            True si al menos una actividad fue marcada como timeout.
        """

        def _do_timeouts(state):
            changed = False
            for activity_key, data in state.items():
                if data.get("status") == "En Progreso":
                    last_update = datetime.fromisoformat(
                        data.get("last_update", "1970-01-01T00:00:00")
                    )
                    if datetime.now() - last_update > timedelta(seconds=self.timeout_seconds):
                        agents = data.get("agents", [])
                        print(f"[COORDINATOR] TIMEOUT: {activity_key} "
                              f"(agentes: {agents})")
                        state[activity_key].update({
                            "status": "Disponible (Timeout)",
                            "agents": [],
                            "event": f"TIMEOUT - Sin respuesta por "
                                     f"{self.timeout_seconds}+ segundos",
                        })
                        changed = True
            return changed

        changed = self._atomic_update(_do_timeouts)
        self._update_markdown()
        return changed

    def get_available_activities(self) -> List[str]:
        """Actividades disponibles ordenadas por número de preguntas (menor a mayor).

        Las actividades con questions_total conocido (> 0) aparecen primero,
        ordenadas de menor a mayor. Las actividades con questions_total = 0
        (desconocido) aparecen al final. Esto permite a los agentes priorizar
        actividades rápidas para maximizar la velocidad de finalización.
        """
        state = self._read_state()
        available = []

        # Primero actividades cooperativas (En Progreso con < 2 agentes)
        for activity_key, data in state.items():
            if data.get("approvals", 0) >= 4:
                continue
            if data.get("status") == "En Progreso":
                agents = data.get("agents", [])
                if not isinstance(agents, list):
                    agents = [data.get("agent_id")] if data.get("agent_id") else []
                if len(agents) < 2:
                    last_update = datetime.fromisoformat(
                        data.get("last_update", "1970-01-01T00:00:00")
                    )
                    if datetime.now() - last_update < timedelta(seconds=self.timeout_seconds):
                        available.append(activity_key)

        # Luego actividades vacías
        for activity_key, data in state.items():
            if data.get("approvals", 0) >= 4:
                continue
            if data.get("status") in ("Disponible", "Disponible (Timeout)"):
                if activity_key not in available:
                    available.append(activity_key)

        # Ordenar por número de preguntas (menor a mayor).
        #   - Actividades con questions_total > 0 van primero, ordenadas asc.
        #   - Actividades con questions_total == 0 (desconocido) van al final.
        available.sort(key=lambda key: (
            0 if state.get(key, {}).get("questions_total", 0) > 0 else 1,
            state.get(key, {}).get("questions_total", 0)
        ))

        return available

    def get_activity_progress(self, activity_key: str) -> int:
        """Número de aprobaciones (0-4)."""
        state = self._read_state()
        return state.get(activity_key, {}).get("approvals", 0)

    def get_timedout_activity_names(self) -> List[str]:
        """Actividades en estado 'Disponible (Timeout)'."""
        state = self._read_state()
        return [
            k for k, v in state.items()
            if v.get("status") == "Disponible (Timeout)"
        ]

    def register_activity(self, activity_key: str):
        """Registra una nueva actividad. Atómico."""

        def _do_register(state):
            if activity_key in state:
                return False

            parts = activity_key.rsplit("_", 1)
            activity_name = parts[-1] if len(parts) > 1 else activity_key

            state[activity_key] = {
                "status": "Disponible",
                "agent_id": "-",
                "activity_name": activity_name,
                "approvals": 0,
                "questions_done": 0,
                "questions_total": 0,
                "last_update": datetime.now().isoformat(),
                "event": "Actividad descubierta",
            }
            return True

        changed = self._atomic_update(_do_register)
        self._update_markdown()
        if changed:
            print(f"[COORDINATOR] Nueva actividad registrada: {activity_key}")

    def force_reset_status(self, activity_key: str,
                           reason: str = "Sincronización con plataforma"):
        """Resetea una actividad a 'Disponible'. Atómico."""

        def _do_reset(state):
            if activity_key not in state:
                return False

            print(f"[COORDINATOR] FORCING RESET: {activity_key} ({reason})")
            state[activity_key].update({
                "status": "Disponible",
                "agents": [],
                "approvals": 0,
                "last_update": datetime.now().isoformat(),
                "event": f"RESET FORZADO: {reason}",
            })
            return True

        changed = self._atomic_update(_do_reset)
        self._update_markdown()
