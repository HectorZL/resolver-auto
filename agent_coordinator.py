"""
Coordinador para sistema multi-agente.

Gestiona el estado compartido de actividades, sistema de bloqueo exclusivo,
tracking de aprobaciones (4 por actividad) y timeout de 2 minutos.
"""

import json
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional

# Usar filelock para mejor compatibilidad multi-proceso
try:
    from filelock import FileLock
except ImportError:
    print("[WARNING] filelock no instalado. Instalar con: pip install filelock")
    FileLock = None

class AgentCoordinator:
    """Coordina múltiples agentes trabajando en paralelo."""
    
    def __init__(self, state_file: str = "agents_state.md", timeout_seconds: int = 120):
        """
        Inicializa el coordinador.
        
        Args:
            state_file: Ruta al archivo MD de estado compartido
            timeout_seconds: Segundos antes de liberar actividad inactiva (default: 120 = 2 min)
        """
        self.state_file = state_file
        self.timeout_seconds = timeout_seconds
        self.state_json = state_file.replace(".md", ".json")  # JSON interno para datos estructurados
        self.lock_file = self.state_json + ".lock"  # Archivo para el lock
        
        if FileLock:
            self.file_lock = FileLock(self.lock_file, timeout=10)
        else:
            self.file_lock = None
            print("[WARNING] Sistema de locks deshabilitado (pip install filelock)")
        
        # Inicializar archivos si no existen
        if not os.path.exists(self.state_json):
            self._save_state({})
        
        self._update_markdown()
    
    def _load_state(self) -> Dict:
        """Carga el estado desde el archivo JSON con lock."""
        if self.file_lock:
            with self.file_lock:
                return self._load_state_unsafe()
        else:
            return self._load_state_unsafe()
    
    def _load_state_unsafe(self) -> Dict:
        """Carga estado sin lock (uso interno)."""
        try:
            if not os.path.exists(self.state_json):
                return {}
            with open(self.state_json, 'r', encoding='utf-8') as f:
                content = f.read()
                if not content.strip():
                    return {}
                return json.loads(content)
        except json.JSONDecodeError:
            print("[WARNING] Estado corrupto, reiniciando...")
            return {}
        except Exception as e:
            print(f"[WARNING] Error cargando estado: {e}")
            return {}
    
    def _save_state(self, state: Dict):
        """Guarda el estado en el archivo JSON con lock."""
        if self.file_lock:
            with self.file_lock:
                self._save_state_unsafe(state)
        else:
            self._save_state_unsafe(state)
    
    def _save_state_unsafe(self, state: Dict):
        """Guarda estado sin lock (uso interno)."""
        try:
            with open(self.state_json, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[WARNING] Error guardando estado: {e}")
    
    def _update_markdown(self):
        """Actualiza el archivo MD con formato legible desde el estado JSON."""
        state = self._load_state()
        
        lines = [
            "# Estado de Actividades Multi-Agente (Modo Cooperativo)",
            f"*Última actualización: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*",
            "",
            "---",
            ""
        ]
        
        if not state:
            lines.append("*No hay actividades registradas aún*")
        else:
            for activity_key, data in sorted(state.items()):
                lines.append(f"## Actividad: {activity_key}")
                lines.append(f"- **Estado:** {data.get('status', 'Desconocido')}")
                
                # Manejar lista de agentes
                agents = data.get('agents', [])
                if isinstance(agents, list):
                    agents_str = ", ".join(agents) if agents else "-"
                else:
                    # Backward compatibility
                    agents_str = str(data.get('agent_id', '-'))
                
                lines.append(f"- **Agentes:** {agents_str}")
                lines.append(f"- **Progreso:** {data.get('approvals', 0)}/4 aprobaciones")
                
                if data.get('questions_done') and data.get('questions_total'):
                    lines.append(f"- **Preguntas Actuales:** {data['questions_done']}/{data['questions_total']}")
                
                lines.append(f"- **Última Actualización:** {data.get('last_update', '-')}")
                
                if data.get('event'):
                    lines.append(f"- **Evento:** {data['event']}")
                
                lines.append("")
        
        with open(self.state_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
    
    def claim_activity(self, agent_id: str, activity_key: str) -> bool:
        """
        Intenta reclamar una actividad para un agente.
        Soporta hasta 2 agentes simultáneos por actividad.
        """
        state = self._load_state()
        
        # Verificar si ya existe
        if activity_key in state:
            activity = state[activity_key]
            
            # Si ya tiene 4/4 aprobaciones, está completa
            if activity.get('approvals', 0) >= 4:
                return False
            
            # Obtener lista de agentes actuales
            current_agents = activity.get('agents', [])
            if not isinstance(current_agents, list):
                # Migrar formato antiguo
                old_agent = activity.get('agent_id')
                current_agents = [old_agent] if old_agent and old_agent != '-' else []

            # Si ya estoy en la lista, retornar True (re-claim)
            if agent_id in current_agents:
                return True

            # Si la actividad está llena (1 agente), verificar timeouts
            MAX_AGENTS = 1
            if len(current_agents) >= MAX_AGENTS:
                # Verificar timeout global de la actividad para simplificar
                # (Idealmente verificaríamos heartbeat por agente, pero global funciona por ahora)
                last_update = datetime.fromisoformat(activity.get('last_update', '1970-01-01T00:00:00'))
                if datetime.now() - last_update < timedelta(seconds=self.timeout_seconds):
                    return False  # Todavía activo y lleno
                
                # Timeout alcanzado, liberar a todos y permitir entrar
                print(f"[INFO] Timeout detectado para {activity_key}, reiniciando lista de agentes...")
                state[activity_key]['agents'] = []
                current_agents = []
        
        # Reclamar actividad (añadirse a la lista)
        if activity_key not in state:
            state[activity_key] = {
                'approvals': 0,
                'questions_done': 0,
                'questions_total': 0,
                'agents': []
            }
            current_agents = []
        
        # Migración al vuelo si es necesario
        if 'agents' not in state[activity_key]:
             state[activity_key]['agents'] = []
             if state[activity_key].get('agent_id') and state[activity_key]['agent_id'] != '-':
                 state[activity_key]['agents'].append(state[activity_key]['agent_id'])
             current_agents = state[activity_key]['agents']

        # Añadir agente a la lista
        if agent_id not in current_agents:
            current_agents.append(agent_id)
        
        state[activity_key]['agents'] = current_agents
        state[activity_key].update({
            'status': 'En Progreso',
            'last_update': datetime.now().isoformat(),
            'event': f'{agent_id} se unió a la actividad ({len(current_agents)}/1 agentes)'
        })
        
        # Limpiar campo antiguo
        if 'agent_id' in state[activity_key]:
            del state[activity_key]['agent_id']
        
        self._save_state(state)
        self._update_markdown()
        
        print(f"[COORDINATOR] {agent_id} reclamó {activity_key} (Total: {len(current_agents)})")
        return True
    
    def update_heartbeat(self, agent_id: str, activity_key: str, 
                        questions_done: int, questions_total: int):
        """Actualiza el timestamp de una actividad."""
        state = self._load_state()
        
        if activity_key not in state:
            return
        
        # Verificar si el agente está en la lista de la actividad
        agents = state[activity_key].get('agents', [])
        # Compatibilidad hacia atrás
        if not isinstance(agents, list):
            agents = [state[activity_key].get('agent_id')] if state[activity_key].get('agent_id') else []

        if agent_id not in agents:
            # Si no está en la lista, intentar re-unirse silenciosamente si hay espacio
            if len(agents) < 1:
                 self.claim_activity(agent_id, activity_key)
            else:
                 print(f"[WARNING] {agent_id} intentó actualizar actividad donde no está registrado: {activity_key}")
                 return
        
        state[activity_key].update({
            'questions_done': questions_done,
            'questions_total': questions_total,
            'last_update': datetime.now().isoformat()
        })
        
        self._save_state(state)
        self._update_markdown()
    
    def complete_approval(self, agent_id: str, activity_key: str):
        """Registra una aprobación completa."""
        state = self._load_state()
        
        if activity_key not in state:
            return
        
        # Incrementar contador de aprobaciones
        current_approvals = state[activity_key].get('approvals', 0)
        new_approvals = current_approvals + 1
        
        state[activity_key].update({
            'approvals': new_approvals,
            'questions_done': 0,  
            'last_update': datetime.now().isoformat(),
            'event': f'{agent_id} completó aprobación {new_approvals}/4'
        })
        
        # Si llegó a 4/4, marcar como completada y limpiar agentes
        if new_approvals >= 4:
            state[activity_key]['status'] = 'Completada 100%'
            state[activity_key]['event'] = f'{agent_id} completó la actividad al 100% (4/4 aprobaciones)'
            state[activity_key]['agents'] = [] # Liberar a todos
        
        self._save_state(state)
        self._update_markdown()
        
        print(f"[COORDINATOR] {agent_id} completó aprobación {new_approvals}/4 de {activity_key}")
    
    def release_activity(self, agent_id: str, activity_key: str, reason: str = "Liberada"):
        """Libera una actividad (se sale de la lista de agentes)."""
        state = self._load_state()
        
        if activity_key not in state:
            return
        
        agents = state[activity_key].get('agents', [])
        if not isinstance(agents, list):
             agents = [state[activity_key].get('agent_id')] if state[activity_key].get('agent_id') else []
        
        # Remover al agente de la lista
        if agent_id in agents:
            agents.remove(agent_id)
            state[activity_key]['agents'] = agents
            
            # Solo marcar como "Disponible" si no queda nadie
            if not agents:
                if state[activity_key].get('approvals', 0) >= 4:
                    state[activity_key]['status'] = 'Completada 100%'
                else:
                    state[activity_key]['status'] = 'Disponible'
                state[activity_key]['event'] = f'{agent_id} liberó: {reason} (Vacía)'
            else:
                state[activity_key]['event'] = f'{agent_id} salió: {reason} (Quedan: {", ".join(agents)})'
            
            state[activity_key]['last_update'] = datetime.now().isoformat()
            
            self._save_state(state)
            self._update_markdown()
            print(f"[COORDINATOR] {agent_id} dejó {activity_key}: {reason}")

    def check_timeouts(self):
        """Verifica timeouts y limpia agentes atascados."""
        state = self._load_state()
        changed = False
        
        for activity_key, data in state.items():
            if data.get('status') == 'En Progreso':
                last_update = datetime.fromisoformat(data.get('last_update', '1970-01-01T00:00:00'))
                if datetime.now() - last_update > timedelta(seconds=self.timeout_seconds):
                    agents = data.get('agents', [])
                    print(f"[COORDINATOR] TIMEOUT: {activity_key} (agentes: {agents})")
                    
                    state[activity_key].update({
                        'status': 'Disponible (Timeout)',
                        'agents': [], # Limpiar todos los agentes
                        'event': f"TIMEOUT - Sin respuesta por {self.timeout_seconds}+ segundos"
                    })
                    changed = True
        
        if changed:
            self._save_state(state)
            self._update_markdown()

    
    def get_available_activities(self) -> List[str]:
        """
        Obtiene lista de actividades disponibles para trabajar.
        Retorna actividades 'Disponible' Y actividades 'En Progreso' con espacio (<2 agentes).
        Prioriza las que ya tienen 1 agente para cooperar.
        """
        state = self._load_state()
        available = []
        
        # Primero buscar actividades para cooperar (En Progreso con 1 agente)
        for activity_key, data in state.items():
            if data.get('approvals', 0) >= 4:
                continue
            
            if data.get('status') == 'En Progreso':
                # Verificar agentes
                agents = data.get('agents', [])
                if not isinstance(agents, list):
                    agents = [data.get('agent_id')] if data.get('agent_id') else []
                
                # Si hay espacio (menos de 2 agentes) y está activa
                if len(agents) < 2:
                    last_update = datetime.fromisoformat(data.get('last_update', '1970-01-01T00:00:00'))
                    if datetime.now() - last_update < timedelta(seconds=self.timeout_seconds):
                        available.append(activity_key)

        # Luego añadir actividades totalmente vacías
        for activity_key, data in state.items():
            if data.get('approvals', 0) >= 4:
                continue
            
            if data.get('status') in ['Disponible', 'Disponible (Timeout)']:
                if activity_key not in available:
                     available.append(activity_key)
        
        return available
    
    def get_activity_progress(self, activity_key: str) -> int:
        """
        Obtiene el número de aprobaciones de una actividad.
        
        Returns:
            Número de aprobaciones (0-4)
        """
        state = self._load_state()
        if activity_key not in state:
            return 0
        return state[activity_key].get('approvals', 0)
    
    def get_timedout_activity_names(self) -> List[str]:
        """
        Obtiene los nombres de actividades que hicieron timeout.
        Útil para que los agentes limpien sus listas de skip locales.
        
        Returns:
            Lista de activity_key con estado 'Disponible (Timeout)'
        """
        state = self._load_state()
        timedout = []
        for activity_key, data in state.items():
            if data.get('status') == 'Disponible (Timeout)':
                timedout.append(activity_key)
        return timedout

    

    
    def register_activity(self, activity_key: str):
        """
        Registra una nueva actividad en el sistema.
        
        Args:
            activity_key: Identificador único de la actividad
        """
        state = self._load_state()
        
        if activity_key not in state:
            state[activity_key] = {
                'status': 'Disponible',
                'agent_id': '-',
                'approvals': 0,
                'questions_done': 0,
                'questions_total': 0,
                'last_update': datetime.now().isoformat(),
                'event': 'Actividad descubierta'
            }
            
            self._save_state(state)
            self._update_markdown()
            print(f"[COORDINATOR] Nueva actividad registrada: {activity_key}")

    def force_reset_status(self, activity_key: str, reason: str = "Sincronización con plataforma"):
        """
        Fuerza el reseteo del estado de una actividad si la plataforma indica que está incompleta.
        """
        state = self._load_state()
        if activity_key in state:
            print(f"[COORDINATOR] ⚠️ FORCING RESET: {activity_key} ({reason})")
            state[activity_key].update({
                'status': 'Disponible',
                'agents': [],
                'approvals': 0, # Resetear aprobaciones para permitir trabajo
                'last_update': datetime.now().isoformat(),
                'event': f'RESET FORZADO: {reason}'
            })
            self._save_state(state)
            self._update_markdown()
