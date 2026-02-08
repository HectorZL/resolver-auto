
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
    
    def __init__(self, config_path: str = "config.json"):
        """Inicializa el agente con la configuración."""
        # Cargar configuración
        self.config_path = config_path
        self.config = self._load_config(config_path)
        
        # Inicializar componentes base
        self.browser = BrowserController(headless=False)
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
        
        print("[INFO] Agente inicializado (Modular)")

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
                
                # Buscar módulo incompleto
                module = self.navigator.find_incomplete_module(exclude_modules=processed_modules)
                
                if not module:
                     current_url = self.browser.page.url.lower()
                     
                     # Check connection lost / login page
                     if "signin" in current_url or "login" in current_url:
                         print("[WARNING] Redirección detectada a LOGIN. Intentando recuperar sesión...")
                         if self.navigator.login():
                             continue
                         else:
                             print("[FATAL] No se pudo recuperar la sesión tras redirección.")
                             break
                     
                     # Check if we are stuck on error page or something else
                     if "dashboard" not in current_url and "autoaprendizaje" not in current_url:
                          print(f"[WARNING] No se encontraron módulos y la URL es sospechosa ({current_url}).")
                          print("[INFO] REGLA DE RECUPERACIÓN: Forzando reinicio total en LOGIN...")
                          
                          try:
                              # Forzar navegación al LOGIN para reiniciar todo el proceso
                              login_url = self.config.get("login_url", "https://aulaslenguas.utm.edu.ec:8443/signin")
                              self.browser.page.goto(login_url)
                              self.browser.sleep(5)
                              
                              # Limpiar estado para que re-escanee todo desde cero
                              processed_modules.clear()
                              continue 
                          except:
                              pass

                     print("[INFO] ¡Todos los módulos están completos!")
                     break
                
                module_key = module['title']
                
                if module_key not in skipped_activities_per_module:
                    skipped_activities_per_module[module_key] = set()
                
                # Buscar actividad incompleta
                activity = self.navigator.find_incomplete_activity(
                    module["element"],
                    skip_activities=skipped_activities_per_module[module_key]
                )
                
                if not activity:
                    print(f"[INFO] Módulo {module['title']} no tiene más actividades disponibles")
                    processed_modules.add(module['title'])
                    continue
                
                self.current_activity = activity # Optional tracking
                activity_key = f"{module['title']}_{activity['name']}"
                
                if activity_key not in self.activity_attempts:
                    self.activity_attempts[activity_key] = {"attempts": 0, "completed": False}
                
                if self.activity_attempts[activity_key]["completed"]:
                    print(f"[INFO] Actividad '{activity['name']}' ya completada anteriormente. Saltando...")
                    skipped_activities_per_module[module_key].add(activity['name'])
                    continue
                
                attempts_done = self.activity_attempts[activity_key]["attempts"]
                max_attempts = self._get_max_attempts(attempts_done)
                
                if attempts_done >= max_attempts:
                    print(f"[WARNING] Actividad '{activity['name']}' alcanzó {attempts_done} intentos sin completarse.")
                    skipped_activities_per_module[module_key].add(activity['name'])
                    continue
                
                self.activity_attempts[activity_key]["attempts"] += 1
                print(f"[INFO] Intento {self.activity_attempts[activity_key]['attempts']} de {max_attempts} para '{activity['name']}'")
                
                # Iniciar actividad
                if not self.navigator.click_activity_and_start(activity):
                    print("[ERROR] No se pudo iniciar la actividad")
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
                    
                    if not self.navigator.has_next_question():
                        break
                    
                    self.browser.sleep(1)
                
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
            input("Presiona Enter para cerrar el navegador...")
            self.browser.close()


if __name__ == "__main__":
    agent = ExamAgent()
    agent.run()
