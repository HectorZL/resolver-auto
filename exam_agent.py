
"""
Agente principal para resolver exámenes automáticamente.
Versión modularizada.
"""

import json
import time
from pathlib import Path
import re # Needed for run loop regex if any? Actually run loop mostly delegates, but verification logic used regex. Let's see.

from browser_controller import BrowserController
from gemini_solver import GeminiSolver

# Nuevos módulos
from module_navigator import ModuleNavigator
from question_detector import QuestionDetector
from question_solvers import QuestionSolvers

class ExamAgent:
    """Agente de IA para resolver exámenes automáticamente."""
    
    def __init__(self, config_path: str = "config.json", agent_id: str = None, coordinator = None):
        """Inicializa el agente con la configuración."""
        # Cargar configuración
        self.config_path = config_path
        self.config = self._load_config(config_path)
        
        # Multi-agente
        self.agent_id = agent_id or f"Agent-Solo"
        self.coordinator = coordinator
        self.multi_agent_mode = coordinator is not None
        
        # Inicializar componentes base (pasar agent_id al navegador)
        self.browser = BrowserController(headless=False, agent_id=self.agent_id)
        self.solver = GeminiSolver(api_key=self.config["gemini_api_key"])
        
        # Inicializar módulos de lógica
        self.navigator = ModuleNavigator(self.browser, self.config)
        self.detector = QuestionDetector(self.browser)
        self.solvers = QuestionSolvers(self.browser, self.solver, self.config, delay=2)
        
        # Estado
        self.activity_attempts = {}
        self.questions_answered = 0
        self.last_question_hash = None
        self.consecutive_repeats = 0
        self.current_activity_key = None
        
        print(f"[INFO] {self.agent_id} inicializado (Multi-Agente: {self.multi_agent_mode})")

    def _load_config(self, path: str) -> dict:
        """Carga la configuración desde un archivo JSON."""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[ERROR] No se pudo cargar config: {e}")
            return {}

    def _get_max_attempts(self, attempts_done: int) -> int:
        """Calcula los intentos máximos permitidos para una actividad."""
        return 5  # Permitir hasta 5 intentos

    def solve_current_question(self) -> bool:
        """Resuelve la pregunta actual en pantalla detectando el tipo de pregunta."""
        print("[INFO] Analizando pregunta...")
        
        try:
            # 1. Extraer pregunta
            question_text = self.detector.get_question_text()
            
            # Detectar preguntas repetidas y cambiar modelo
            question_hash = hash(question_text[:100] if question_text else "")
            
            if question_hash == self.last_question_hash:
                self.consecutive_repeats += 1
            else:
                self.consecutive_repeats = 0
                if self.solver.using_advanced:
                    self.solver.reset_to_normal_model()
            
            self.last_question_hash = question_hash
            
            if self.consecutive_repeats >= 3 and not self.solver.using_advanced:
                print(f"[WARNING] Pregunta repetida {self.consecutive_repeats} veces consecuitivas → Modelo AVANZADO")
                self.solver.switch_to_advanced_model()
            
            print(f"[INFO] Pregunta: {question_text[:100]}..." if question_text else "[INFO] No se encontró pregunta")
            
            # 2. Detectar tipo
            question_type = self.detector.detect_question_type()
            print(f"[INFO] Tipo de pregunta: {question_type}")
            
            # 3. Resolver
            success = False
            
            if question_type == "multiple_choice":
                success = self.solvers.solve_multiple_choice(question_text)
            elif question_type == "fill_blanks":
                success = self.solvers.solve_fill_blanks(question_text)
            elif question_type == "matching_buttons":
                success = self.solvers.solve_matching_buttons(question_text)
            elif question_type == "image_drag_match":
                success = self.solvers.solve_image_drag_match(question_text)
            elif question_type == "text_match":
                success = self.solvers.solve_text_match(question_text)
            elif question_type == "inline_choice":
                success = self.solvers.solve_inline_choice(question_text)
            elif question_type == "image_with_options":
                success = self.solvers.solve_image_with_options(question_text)
            elif question_type == "matching_requirements":
                success = self.solvers.solve_matching_requirements(question_text)
            elif question_type == "sentence_completion":
                success = self.solvers.solve_sentence_completion(question_text)
            elif question_type == "sentence_ordering":
                success = self.solvers.solve_sentence_ordering(question_text)
            elif question_type == "sentence_join":
                # DRAW A LINE TO JOIN - similar a text_match pero puede estar completado
                success = self.solvers.solve_sentence_join(question_text)
            else:
                success = self.solvers.solve_with_screenshot(question_text)
            
            # NOTA: No reseteamos consecutive_repeats aquí, porque si la pregunta aparece de nuevo
            # significa que fallamos (aunque el click haya sido exitoso).
            # Se reseteará solo cuando el hash de la pregunta cambie.
            
            return success
            
        except Exception as e:
            print(f"[ERROR] Error resolviendo pregunta: {e}")
            return False

    def run(self):
        """Ejecuta el agente principal."""
        print("\n" + "="*60)
        print("   AGENTE DE EXÁMENES UTM - INICIANDO (MODULAR)")
        print("="*60 + "\n")
        
        try:
            # 1. Login
            if not self.navigator.login():
                print("[FATAL] No se pudo iniciar sesión")
                return
            
            # 2. Buscar y resolver módulos incompletos
            processed_modules = set()  # Evita loops infinitos
            skipped_activities_per_module = {}  # Track actividades saltadas por módulo
            
            while True:
                # Asegurarse de estar en el dashboard
                if "dashboard" not in self.browser.page.url and "autoaprendizaje" in self.browser.page.url:
                    pass # Ya manejado por find_incomplete_module parcialmente o el flujo
                
                # NUEVO: Limpiar skip lists de actividades que hicieron timeout
                if self.multi_agent_mode and self.coordinator:
                    try:
                        timedout_activities = self.coordinator.get_timedout_activity_names()
                        if timedout_activities:
                            for m_key in skipped_activities_per_module:
                                # Para cada actividad con timeout, extraer el nombre de actividad
                                # activity_key format: "MODULE X | UNIT Y (Z)_activityname"
                                for timeout_key in timedout_activities:
                                    # Extraer nombre de actividad (última parte después de _)
                                    parts = timeout_key.rsplit('_', 1)
                                    if len(parts) == 2 and parts[0] == m_key:
                                        activity_name = parts[1]
                                        if activity_name in skipped_activities_per_module[m_key]:
                                            print(f"[{self.agent_id}] 🔓 Limpiando skip para '{activity_name}' (timeout detectado)")
                                            skipped_activities_per_module[m_key].discard(activity_name)
                    except Exception as e:
                        print(f"[WARNING] Error limpiando skip lists: {e}")
                
                # Buscar módulos incompletos
                incomplete_modules = self.navigator.find_incomplete_module(exclude_modules=processed_modules)

                
                if not incomplete_modules:
                     current_url = self.browser.page.url.lower()
                     
                     # Check connection lost / login page / homepage redirect
                     if "signin" in current_url or "login" in current_url or current_url.rstrip("/").endswith(":8443"):
                         print("[WARNING] Redirección detectada (Login/Homepage). Intentando recuperar sesión...")
                         
                         # Cerrar modal de "Bienvenidos" si existe
                         try:
                             cerrar_btn = self.browser.page.query_selector("button:has-text('Cerrar')")
                             if cerrar_btn and cerrar_btn.is_visible():
                                 cerrar_btn.click()
                                 self.browser.sleep(0.5)
                                 print("[INFO] Modal 'Bienvenidos' cerrado")
                         except:
                             pass
                         
                         if self.navigator.login():
                             continue
                         else:
                             print("[FATAL] No se pudo recuperar la sesión tras redirección.")
                             break
                     
                     # Check if we are stuck on error page or something else
                     if "dashboard" not in current_url and "autoaprendizaje" not in current_url:
                          print(f"[WARNING] No se encontraron módulos y la URL es sospechosa ({current_url}).")
                          print("[INFO] REGLA DE RECUPERACIÓN: Intentando ir al DASHBOARD...")
                          
                          try:
                              dashboard_url = self.config.get("dashboard_url", "https://aulaslenguas.utm.edu.ec:8443/dashboard")
                              if "/signin" in dashboard_url:
                                   dashboard_url = dashboard_url.replace("/signin", "/dashboard")

                              self.browser.page.goto(dashboard_url)
                              self.browser.sleep(5)
                              processed_modules.clear()
                              continue 
                          except:
                              pass

                     print(f"[{self.agent_id}] 💤 No se encontraron módulos incompletos. Esperando 30s...")
                     processed_modules.clear()
                     skipped_activities_per_module.clear()
                     self.browser.sleep(30)
                     continue

                # Seleccionar un módulo y actividad válida
                selected_module = None
                selected_activity = None

                for mod in incomplete_modules:
                    m_key = mod['title']
                    if m_key not in skipped_activities_per_module:
                        skipped_activities_per_module[m_key] = set()
                    
                    # Buscar actividad
                    act = self.navigator.find_incomplete_activity(
                        mod["element"],
                        skip_activities=skipped_activities_per_module[m_key]
                    )
                    
                    if not act:
                        print(f"[INFO] Módulo {mod['title']} ya no tiene actividades. Marcando procesado.")
                        processed_modules.add(mod['title'])
                        continue
                    
                    if act.get("status") == "busy":
                        print(f"[{self.agent_id}] Módulo {mod['title']} ocupado. Probando siguiente...")
                        processed_modules.add(mod['title'])
                        continue
                    
                    # Encontramos trabajo!
                    selected_module = mod
                    selected_activity = act
                    break
                
                if not selected_activity:
                    print(f"[{self.agent_id}] 💤 Todos los módulos incompletos están ocupados por otros agentes. Esperando 15s...")
                    self.browser.sleep(15)
                    continue

                # Proceder con la actividad encontrada
                module = selected_module
                module_key = module['title']
                activity = selected_activity
                self.current_activity = activity
                activity_key = f"{module_key}_{activity['name']}"
                
                # MULTI-AGENTE: Intentar reclamar actividad
                if self.multi_agent_mode:
                    # Registrar si es nueva
                    self.coordinator.register_activity(activity_key)
                    
                    # Intentar reclamar
                    if not self.coordinator.claim_activity(self.agent_id, activity_key):
                        # Verificar si fue rechazado por "Completada" (approvals >= 4)
                        # PERO la plataforma dice que está incompleta (< 100%)
                        progress = activity.get('progress', 0)
                        if progress < 100:
                            coordinator_approvals = self.coordinator.get_activity_progress(activity_key)
                            if coordinator_approvals >= 4:
                                print(f"[{self.agent_id}] ⚠️ DISCUSIÓN: Plataforma dice {progress}% pero Coordinador dice {coordinator_approvals}/4 completados.")
                                print(f"[{self.agent_id}] 🔄 FORZANDO RESET en Coordinador para sincronizar con realidad...")
                                self.coordinator.force_reset_status(activity_key, f"Plataforma {progress}% vs Coordinador {coordinator_approvals}/4")
                                
                                # Reintentar claim
                                if self.coordinator.claim_activity(self.agent_id, activity_key):
                                    print(f"[{self.agent_id}] ✅ Reclamada tras reset: {activity_key}")
                                    self.current_activity_key = activity_key
                                else:
                                     print(f"[{self.agent_id}] ❌ Aún no disponible tras reset (quizás ocupada por otro)")
                                     skipped_activities_per_module[module_key].add(activity['name'])
                                     continue
                            else:
                                print(f"[{self.agent_id}] Actividad {activity_key} no disponible (ocupada por otros)")
                                skipped_activities_per_module[module_key].add(activity['name'])
                                continue
                        else:
                            print(f"[{self.agent_id}] Actividad {activity_key} no disponible (completa)")
                            skipped_activities_per_module[module_key].add(activity['name'])
                            continue
                    
                    self.current_activity_key = activity_key
                    print(f"[{self.agent_id}] ✅ Reclamada: {activity_key}")
                
                if activity_key not in self.activity_attempts:
                    self.activity_attempts[activity_key] = {"attempts": 0, "completed": False}
                
                if self.activity_attempts[activity_key]["completed"]:
                    print(f"[INFO] Actividad '{activity['name']}' ya completada anteriormente. Saltando...")
                    if self.multi_agent_mode and self.current_activity_key:
                        self.coordinator.release_activity(self.agent_id, self.current_activity_key, "Ya completada localmente")
                    skipped_activities_per_module[module_key].add(activity['name'])
                    continue
                
                attempts_done = self.activity_attempts[activity_key]["attempts"]
                max_attempts = self._get_max_attempts(attempts_done)
                
                if attempts_done >= max_attempts:
                    print(f"[WARNING] Actividad '{activity['name']}' alcanzó {attempts_done} intentos sin completarse. Saltando...")
                    if self.multi_agent_mode and self.current_activity_key:
                        self.coordinator.release_activity(self.agent_id, self.current_activity_key, f"Max intentos ({attempts_done})")
                    skipped_activities_per_module[module_key].add(activity['name'])
                    continue
                
                self.activity_attempts[activity_key]["attempts"] += 1
                print(f"[INFO] Intento {self.activity_attempts[activity_key]['attempts']} de {max_attempts} para '{activity['name']}'")
                
                # Iniciar actividad
                if not self.navigator.click_activity_and_start(activity):
                    print("[ERROR] No se pudo iniciar la actividad")
                    if self.multi_agent_mode and self.current_activity_key:
                        self.coordinator.release_activity(self.agent_id, self.current_activity_key, "Error al iniciar UI")
                    continue
                
                # Esperar carga
                self.browser.sleep(2)
                
                # Resolver preguntas
                questions_in_activity = 0
                stuck_counter = 0
                while not self.navigator.is_activity_complete():
                    if not self.solve_current_question():
                        print("[WARNING] Problema resolviendo pregunta, intentando continuar...")
                        stuck_counter += 1
                        self.browser.sleep(2)
                        
                        # FALLBACK: Return to Dashboard if stuck
                        if stuck_counter >= 3:
                            print("[ERROR] Atascado en la misma pregunta 3 veces. Ejecutando FALLBACK a DASHBOARD...")
                            
                            # MULTI-AGENTE: Liberar actividad antes de salir
                            if self.multi_agent_mode and self.current_activity_key:
                                self.coordinator.release_activity(self.agent_id, self.current_activity_key, "Atascado - fallback")
                            
                            try:
                                # Start fresh
                                if "dashboard_url" in self.config:
                                    self.browser.page.goto(self.config["dashboard_url"])
                                else:
                                    # Default dashboard URL from finding_incomplete logic usually starts at root/dashboard
                                    # Let's try to infer or use standard URL helper if available, or just go to root.
                                    # Assuming standard dashboard URL based on config login_url
                                    base_url = self.config["login_url"].replace("/signin", "/dashboard")
                                    self.browser.page.goto(base_url)
                                
                                self.browser.sleep(5)
                                stuck_counter = 0
                                # Exit inner loop to re-scan modules
                                break 
                            except Exception as e:
                                print(f"[CRITICAL] Fallback dashboard failed: {e}")
                    else:
                        stuck_counter = 0
                        questions_in_activity += 1
                        self.questions_answered += 1
                        
                        # MULTI-AGENTE: Heartbeat para evitar timeout
                        if self.multi_agent_mode and self.current_activity_key:
                            current, total = self.navigator.get_question_progress()
                            self.coordinator.update_heartbeat(self.agent_id, self.current_activity_key, 
                                                             current or questions_in_activity, total or 10)
                    
                    if not self.navigator.has_next_question():
                        break
                    
                    self.browser.sleep(1)
                
                # MULTI-AGENTE: Solo registrar aprobación si REALMENTE se completó
                is_success = self.navigator.is_activity_complete()
                
                if self.multi_agent_mode and self.current_activity_key and questions_in_activity > 0:
                    if is_success:
                        self.coordinator.complete_approval(self.agent_id, self.current_activity_key)
                        print(f"[{self.agent_id}] ✅ Aprobación confirmada y registrada en coordinador.")
                    else:
                        print(f"[{self.agent_id}] ⚠️ Actividad interrumpida o incompleta. NO se registra aprobación.")
                    
                    # Verificar si ya tiene 4/4
                    approvals = self.coordinator.get_activity_progress(self.current_activity_key)
                    if approvals >= 4:
                        print(f"[{self.agent_id}] 🎉 Actividad {activity_key} COMPLETADA 100% (4/4)")
                        self.coordinator.release_activity(self.agent_id, self.current_activity_key, "Completada 100%")
                        self.activity_attempts[activity_key]["completed"] = True
                    else:
                        print(f"[{self.agent_id}] Aprobación registrada: {approvals}/4 para {activity_key}")
                
                # Volver al dashboard y verificar
                self.browser.sleep(2)
                try:
                    # Verificar si estamos en pantalla de finalización (CONGRATULATIONS)
                    if self.navigator.handle_completion_screen():
                        print("[INFO] Retorno al dashboard manejado por botón CONTINUE")
                    else:
                        print("[INFO] Usando navegación atrás del navegador...")
                        self.browser.page.go_back()
                    
                    self.browser.sleep(1)
                    self.browser.page.reload()
                    self.browser.sleep(2)
                    print("[INFO] Página recargada para actualizar progreso")
                    
                    # Verificar progreso
                    module_updated = self.navigator.find_incomplete_module(exclude_modules=set())
                    if module_updated and module_updated['title'] == module['title']:
                        activity_updated = self.navigator.find_incomplete_activity(module_updated["element"])
                        
                        if not activity_updated or activity_updated['name'] != activity['name']:
                            self.activity_attempts[activity_key]["completed"] = True
                            print(f"[SUCCESS] Actividad '{activity['name']}' COMPLETADA AL 100%! ({questions_in_activity} preguntas)")
                        else:
                            current_progress = activity_updated.get('progress', 0)
                            print(f"[INFO] Actividad '{activity['name']}' aún incompleta: {current_progress}%")
                            print(f"[INFO] Se reintentará en el próximo ciclo...")
                    else:
                        print(f"[WARNING] No se pudo verificar el progreso de '{activity['name']}'")
                        
                except Exception as verify_err:
                    print(f"[WARNING] Error verificando progreso: {verify_err}")
                    print("[ERROR] Navegación falló. Forzando retorno al Dashboard para evitar bloqueo...")
                    # Force redirect to dashboard to reset state
                    dashboard_url = self.config.get("dashboard_url", "https://aulaslenguas.utm.edu.ec:8443/dashboard")
                    if "/signin" in dashboard_url: # Handle incorrect default fallback if key missing
                         dashboard_url = dashboard_url.replace("/signin", "/dashboard")
                    
                    try:
                        self.browser.page.goto(dashboard_url)
                        self.browser.sleep(5)
                        print("[INFO] Redirección forzada al Dashboard completada.")
                    except:
                        print("[CRITICAL] No se pudo forzar el retorno al dashboard.")
            
            print("\n" + "="*60)
            print(f"   AGENTE FINALIZADO - Preguntas respondidas: {self.questions_answered}")
            print("="*60 + "\n")
            
        except KeyboardInterrupt:
            print("\n[INFO] Agente detenido por el usuario")
        except Exception as e:
            print(f"[ERROR] Error en el agente: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print("[INFO] El navegador permanecerá abierto")
            # input("Presiona Enter para cerrar el navegador...") # REMOVED to prevent EOFError in subprocess
            # self.browser.close() # Optional: decide if we want to close or keep open. User prefers open usually but for multi-agent maybe close?
            # For now just keep open and do nothing, but don't block.
            pass


if __name__ == "__main__":
    agent = ExamAgent()
    agent.run()
