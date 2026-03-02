"""
Script principal para ejecutar múltiples agentes en paralelo.

Coordina 4 agentes que resuelven exámenes simultáneamente,
compartiendo estado mediante archivo MD con sistema de bloqueo exclusivo.
"""

import json
import multiprocessing
import threading  # Para el thread de monitoreo de timeouts
import time
import sys
import os
from datetime import datetime
import traceback

# Patch asyncio para Playwright + Gemini
# import nest_asyncio
# nest_asyncio.apply()

def run_agent_process(agent_id: str, config_path: str, state_file: str, timeout_seconds: int):
    """
    Ejecuta un agente en un proceso separado.
    
    Args:
        agent_id: ID único del agente
        config_path: Ruta al config.json
        state_file: Ruta al archivo MD de estado compartido
        timeout_seconds: Timeout para liberar actividades
    """
    
    while True: # Bucle de auto-reinicio
        try:
            # Importar dentro del proceso para evitar conflictos
            from exam_agent import ExamAgent
            from agent_coordinator import AgentCoordinator
            
            # Crear coordinador (compartido mediante el archivo)
            coordinator = AgentCoordinator(state_file=state_file, timeout_seconds=timeout_seconds)
            
            # Crear agente con ID único
            agent = ExamAgent(config_path=config_path, agent_id=agent_id, coordinator=coordinator)
            
            # Ejecutar agente
            print(f"\n{'='*60}")
            print(f"   {agent_id} - INICIANDO")
            print(f"{'='*60}\n")
            
            agent.run()
            
            # Si termina limpiamente, verificar si debemos reiniciar o salir
            # Por ahora asumimos que si termina run() es un fin normal y no reiniciamos,
            # salvo que run() lance excepción.
            print(f"[{agent_id}] Finalizado correctamente.")
            break
            
        except KeyboardInterrupt:
            print(f"\n[{agent_id}] Detenido por el usuario")
            break
        except Exception as e:
            print(f"\n[{agent_id}] CRASH DETECTADO: {e}")
            traceback.print_exc()
            print(f"[{agent_id}] 🔄 Reiniciando en 5 segundos...")
            
            # Intentar liberar recursos/actividades si el agente murió
            try:
                if 'agent' in locals() and hasattr(agent, 'current_activity_key') and agent.current_activity_key:
                    print(f"[{agent_id}] ⚠️ Liberando actividad '{agent.current_activity_key}' por cierre inesperado...")
                    if 'coordinator' in locals():
                         coordinator.release_activity(agent_id, agent.current_activity_key, reason="Crash/Exit del Agente")
            except Exception as cleanup_error:
                print(f"[{agent_id}] Error cleaning up: {cleanup_error}")
            
            time.sleep(5) # Esperar antes de reiniciar


def monitor_state(state_file: str, interval: int = 5):
    """
    Monitorea y muestra el estado del archivo MD periódicamente.
    
    Args:
        state_file: Ruta al archivo MD
        interval: Intervalo de actualización en segundos
    """
    while True:
        try:
            if os.path.exists(state_file):
                # os.system('cls' if os.name == 'nt' else 'clear') # Desactivado para ver debug
                print(f"\n{'='*70}")
                print(f"   ESTADO MULTI-AGENTE - {datetime.now().strftime('%H:%M:%S')}")
                print(f"{'='*70}\n")
                
                with open(state_file, 'r', encoding='utf-8') as f:
                    print(f.read())
                
                print(f"\n{'='*70}")
                print(f"   Actualización automática cada {interval}s | Ctrl+C para salir")
                print(f"{'='*70}\n")
            
            time.sleep(interval)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[MONITOR] Error: {e}")
            time.sleep(interval)


def timeout_monitor(state_file: str, timeout_seconds: int, check_interval: int = 30):
    """
    Monitorea y libera actividades que excedieron el timeout.
    Se ejecuta en un thread separado.
    
    Args:
        state_file: Ruta al archivo MD de estado
        timeout_seconds: Timeout configurado
        check_interval: Intervalo entre checks (segundos)
    """
    from agent_coordinator import AgentCoordinator
    coordinator = AgentCoordinator(state_file=state_file, timeout_seconds=timeout_seconds)
    
    print(f"[TIMEOUT-MONITOR] Iniciado - verificará timeouts cada {check_interval}s")
    
    while True:
        try:
            time.sleep(check_interval)
            coordinator.check_timeouts()
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[TIMEOUT-MONITOR] Error: {e}")


def main():
    """Punto de entrada principal para el sistema multi-agente."""
    print("""
    ╔═══════════════════════════════════════════════════════════════════╗
    ║     SISTEMA MULTI-AGENTE - RESOLUTOR DE EXÁMENES UTM (x4)          ║
    ║                                                                   ║
    ║  4 agentes trabajarán simultáneamente en diferentes actividades   ║
    ║  Coordinación mediante archivo MD compartido con bloqueo          ║
    ╚═══════════════════════════════════════════════════════════════════╝
    """)
    
    # Cargar configuración
    config_path = "config.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print("[ERROR] No se encontró config.json")
        sys.exit(1)
    
    # Verificar API key
    if config.get("gemini_api_key") == "TU_API_KEY_AQUI":
        print("[ERROR] ¡Debes configurar tu API key de Gemini en config.json!")
        print("        Obtén tu API key en: https://aistudio.google.com/app/apikey")
        sys.exit(1)
    
    # Configuración multi-agente
    multi_config = config.get("multi_agent", {})
    num_agents = multi_config.get("num_agents", 4)
    state_file = multi_config.get("state_file", "agents_state.md")
    timeout_seconds = multi_config.get("activity_timeout_seconds", 120)
    
    print(f"\n[INFO] Configuración:")
    print(f"  - Agentes: {num_agents}")
    print(f"  - Archivo de estado: {state_file}")
    print(f"  - Timeout: {timeout_seconds} segundos\n")
    
    # Preguntar si desea monitor
    print("[PREGUNTA] ¿Deseas abrir un monitor en tiempo real del estado? (s/n): ", end="")
    monitor_choice = input().strip().lower()
    
    # Inicializar coordinador
    from agent_coordinator import AgentCoordinator
    coordinator = AgentCoordinator(state_file=state_file, timeout_seconds=timeout_seconds)
    print(f"[INFO] Coordinador inicializado con archivo: {state_file}\n")
    
    # Crear procesos de agentes
    processes = []
    for i in range(1, num_agents + 1):
        agent_id = f"Agent-{i}"
        p = multiprocessing.Process(
            target=run_agent_process,
            args=(agent_id, config_path, state_file, timeout_seconds),
            name=agent_id
        )
        processes.append(p)
    
    # Iniciar agentes
    print(f"[INFO] Iniciando {num_agents} agentes...\n")
    import random
    for p in processes:
        p.start()
        delay = 2 + random.uniform(0, 4)
        print(f"[INFO] Esperando {delay:.1f}s antes de lanzar el siguiente agente...")
        time.sleep(delay)  # Delay aleatorio para evitar colisiones en login y navegación
    
    # Iniciar thread de monitoreo de timeouts
    timeout_thread = threading.Thread(
        target=timeout_monitor,
        args=(state_file, timeout_seconds, 30),  # Verificar cada 30 segundos
        daemon=True  # Se cierra automáticamente cuando termina el programa
    )
    timeout_thread.start()
    
    print(f"\n[SUCCESS] ✅ {num_agents} agentes ejecutándose en paralelo!")
    print(f"[INFO] Estado disponible en: {state_file}")
    print(f"[INFO] Monitor de timeouts activo (verifica cada 30s)")
    print(f"[INFO] Presiona Ctrl+C para detener todos los agentes\n")
    
    try:
        # Si eligió monitor, ejecutarlo
        if monitor_choice == 's':
            print("[INFO] Iniciando monitor en tiempo real...\n")
            time.sleep(3)
            monitor_state(state_file, interval=5)
        else:
            # Esperar a que terminen los procesos
            for p in processes:
                p.join()
    except KeyboardInterrupt:
        print("\n\n[INFO] Señal de interrupción recibida, deteniendo agentes...")
        
        # Terminar todos los procesos
        for p in processes:
            if p.is_alive():
                p.terminate()
        
        # Esperar a que terminen
        for p in processes:
            p.join(timeout=5)
        
        print("[INFO] Todos los agentes detenidos")
    
    print(f"\n[INFO] Sistema multi-agente finalizado")
    print(f"[INFO] Revisa el estado final en: {state_file}\n")


if __name__ == "__main__":
    main()
