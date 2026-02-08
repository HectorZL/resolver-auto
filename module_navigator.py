
import time
import re
from selectors import SELECTORS

class ModuleNavigator:
    """Handles navigation, login, and identifying incomplete modules/activities."""
    
    def __init__(self, browser, config):
        """
        Initialize with browser controller and configuration.
        
        Args:
            browser: BrowserController instance
            config: Dictionary with configuration (email, password, etc.)
        """
        self.browser = browser
        self.config = config
        self.activities_to_solve = [
            "practice", "quiz", "unit test", "grammar", 
            "vocabulary", "reading", "speaking",
            "video", "match", "fill", "writing"
        ] # Default keywords if not specified elsewhere. 
        # Ideally this should be configurable or passed in, but hardcoding reasonable defaults similar to original agent logic.
        # Actually, in original code `activities_to_solve` was hardcoded or property of agent. 
        # Let's keep it here as a property or passed in init? 
        # The internal logic uses it. I'll define it here for now.

    def login(self) -> bool:
        """Realiza el login en la plataforma."""
        print("[INFO] Iniciando login...")
        
        try:
            # Iniciar navegador
            self.browser.start()
            
            # Ir a la página de login
            self.browser.goto(self.config["login_url"])
            
            # Esperar que el formulario esté listo o detectar si ya está logueado
            form_status = self.browser.wait_for_form_ready(SELECTORS["email_input"], timeout=30)
            
            if form_status == "logged_in":
                # Ya está logueado, ir al dashboard
                print("[INFO] Sesión activa detectada, saltando login...")
                return True
            elif form_status == True:
                # Formulario detectado, llenar credenciales
                print("[INFO] Llenando credenciales...")
                self.browser.fill(SELECTORS["email_input"], self.config["email"])
                self.browser.sleep(0.5)
                self.browser.fill(SELECTORS["password_input"], self.config["password"])
                self.browser.sleep(0.5)
                
                # Click en login
                self.browser.click(SELECTORS["login_button"])
                
                # Esperar que cargue el dashboard
                self.browser.sleep(3)
                self.browser.wait_for_load(timeout=10000)
            else:
                print("[ERROR] No se pudo detectar formulario ni sesión activa")
                return False
            
            # Verificar que estamos logueados
            current_url = self.browser.page.url
            print(f"[DEBUG] URL después de login: {current_url}")
            
            if self.browser.exists(SELECTORS["book_header"]) or "dashboard" in self.browser.page.url.lower():
                print("[SUCCESS] Login exitoso!")
                return True
            else:
                print("[WARNING] Login posiblemente fallido, continuando...")
                return True
                
        except Exception as e:
            print(f"[ERROR] Error en login: {e}")
            return False

    def check_and_restore_session(self) -> bool:
        """Verifica si la sesión se perdió (estamos en login) y reloguea."""
        try:
            current_url = self.browser.page.url
            # Verificar URL o presencia de formulario de login
            if "signin" in current_url or "login" in current_url or \
               self.browser.exists("input[type='password']"):
                print("[WARNING] ⚠️ Sesión perdida detectada. Restaurando sesión...")
                return self.login()
            return True
        except Exception as e:
            print(f"[ERROR] Error verificando sesión: {e}")
            return False

    def find_incomplete_module(self, exclude_modules=None) -> dict:
        """Encuentra el primer módulo incompleto.
        
        Args:
            exclude_modules: Set de títulos de módulos a excluir
        """
        if exclude_modules is None:
            exclude_modules = set()
        print("\n[DEBUG] ========== BUSCANDO MÓDULOS INCOMPLETOS ==========")
        
        try:
            # Verificar que estamos en la página correcta (Dashboard o Autoaprendizaje)
            # A veces la URL cambia o carga lento
            
            # Esperar a que aparezcan los módulos (timeout 10s)
            try:
                self.browser.page.wait_for_selector(SELECTORS["module_container"], timeout=10000)
            except:
                print("[WARNING] Tiempo de espera agotado buscando módulos.")
            
            # Buscar todos los contenedores de módulos
            modules = self.browser.page.query_selector_all(SELECTORS["module_container"])
            
            if len(modules) == 0:
                print(f"[DEBUG] URL actual: {self.browser.page.url}")
                print("[DEBUG] Intentando recargar dashboard...")
                # Intentar ir a autoaprendizaje si no estamos ahí
                if "autoaprendizaje" not in self.browser.page.url:
                     try:
                         # Buscar enlace a cursos/autoaprendizaje
                         link = self.browser.page.get_by_text("Mis cursos", exact=False) or \
                                self.browser.page.get_by_text("Autoaprendizaje", exact=False)
                         if link.count() > 0:
                             link.first.click()
                             self.browser.sleep(3)
                             modules = self.browser.page.query_selector_all(SELECTORS["module_container"])
                     except:
                         pass
            
            print(f"[DEBUG] Encontrados {len(modules)} contenedores de módulos")
            print(f"[DEBUG] Módulos a excluir: {exclude_modules}")
            
            all_modules_info = []  # Para logging al final
            
            for idx, module in enumerate(modules):
                # Obtener el título y progreso
                title_el = module.query_selector(SELECTORS["module_title"])
                
                if not title_el:
                    print(f"[DEBUG] Módulo {idx}: ⚠️ Sin título, saltando")
                    continue
                    
                title = title_el.inner_text()
                # print(f"[DEBUG] Módulo {idx}: '{title}'") # Verbose
                
                # Saltar módulos excluidos
                if title in exclude_modules:
                    # print(f"[DEBUG] Módulo {idx} '{title}': ❌ EN LISTA DE EXCLUSIÓN")
                    continue
                    
                progress_text = ""
                
                # Buscar el texto de progreso
                spans = module.query_selector_all("span")
                for span in spans:
                    text = span.inner_text()
                    if "%" in text and "completed" in text.lower():
                        progress_text = text
                        break
                
                if not progress_text:
                    print(f"[DEBUG] Módulo {idx} '{title}': ⚠️ Sin  texto de progreso")
                    continue
                
                # Extraer porcentaje
                match = re.search(r'(\d+)%', progress_text)
                if match:
                    progress = int(match.group(1))
                    status = "🟢 COMPLETO" if progress == 100 else "🟡 INCOMPLETO"
                    all_modules_info.append(f"  - {title}: {progress}%")
                    
                    if progress < 100:
                        print(f"\n[INFO] ✅ Seleccionado módulo incompleto: {title} ({progress}%)")
                        return {
                            "title": title,
                            "progress": progress,
                            "element": module
                        }
                else:
                    print(f"[DEBUG] Módulo {idx} '{title}': ⚠️ No se pudo extraer % de '{progress_text}'")
            
            print(f"\n[INFO] ❌ No se encontraron módulos incompletos")
            print(f"[DEBUG] Resumen de todos los módulos:")
            for info in all_modules_info:
                print(info)
            print(f"[DEBUG] ===================================================\n")
            return None
            
        except Exception as e:
            print(f"[ERROR] Error buscando módulos: {e}")
            return None

    def find_incomplete_activity(self, module_element, skip_activities=None) -> dict:
        """Encuentra una actividad incompleta dentro de un módulo.
        
        Args:
            module_element: Elemento del módulo donde buscar
            skip_activities: Set de nombres de actividades a saltar
        """
        if skip_activities is None:
            skip_activities = set()
            
        print(f"\n[DEBUG] ========== BUSCANDO ACTIVIDADES INCOMPLETAS ==========")
        # print(f"[DEBUG] Actividades a saltar: {skip_activities}")
        
        try:
            # Buscar tooltips (contenedores de actividades)
            activities = module_element.query_selector_all(SELECTORS["activity_tooltip"])
            print(f"[DEBUG] Encontradas {len(activities)} actividades en el módulo")
            
            all_activities_info = []  # Para logging al final
            
            candidates = []
            
            for idx, activity in enumerate(activities):
                # Obtener nombre de la actividad
                name_el = activity.query_selector(SELECTORS["activity_name"])
                if not name_el:
                    print(f"[DEBUG] Actividad {idx}: Sin nombre, saltando")
                    continue
                    
                name = name_el.inner_text().lower()
                
                # Verificar el progreso (color del bfill)
                bfill = activity.query_selector(SELECTORS["progress_fill"])
                height = 0
                if bfill:
                    style = bfill.get_attribute("style") or ""
                    height_match = re.search(r'height:\s*(\d+)%', style)
                    height = int(height_match.group(1)) if height_match else 0
                
                # Verificar si el botón está deshabilitado
                button = activity.query_selector("button")
                is_disabled = button.get_attribute("disabled") if button else None
                disabled_text = "🔒 BLOQUEADA" if is_disabled else "🔓 disponible"
                
                # Determinar razón de skip
                skip_reason = None
                
                # Verificar si es un tipo de actividad que queremos resolver
                is_target_type = any(key in name for key in self.activities_to_solve)
                
                if name in skip_activities:
                    skip_reason = "❌ En lista de saltar"
                elif not is_target_type:
                    skip_reason = f"⏭️ Tipo no soportado"
                elif is_disabled:
                    skip_reason = "🔒 Botón deshabilitado"
                elif height >= 100:
                    skip_reason = "✅ Ya completa (100%)"
                
                status = skip_reason if skip_reason else "🎯 CANDIDATA"
                all_activities_info.append(f"  - {name}: {height}% ({status})")
                
                if not skip_reason:
                    # Guardar candidato
                    candidates.append({
                        "name": name,
                        "progress": height,
                        "element": activity,
                        "button": button
                    })

            # Mostrar resumen
            print(f"[DEBUG] Resumen de actividades:")
            for info in all_activities_info:
                print(info)
            print(f"[DEBUG] ===================================================\n")

            if candidates:
                # Ordenar por progreso descendente (priorizar empezar lo que ya se empezó)
                # Ordenar por progreso DESC, luego por índice ASC (para mantener orden lógico si empate)
                candidates.sort(key=lambda x: x['progress'], reverse=True)
                
                best = candidates[0]
                print(f"[INFO] ✅ Seleccionada actividad incompleta (Mayor Progreso): {best['name']} ({best['progress']}%)")
                return best
            
            print(f"\n[INFO] ❌ No hay más actividades disponibles en este módulo")
            return None
            
        except Exception as e:
            print(f"[ERROR] Error buscando actividades: {e}")
            return None

    def click_activity_and_start(self, activity: dict) -> bool:
        """Hace click en una actividad y maneja el popup."""
        print(f"[INFO] Iniciando actividad: {activity['name']}")
        
        try:
            # Click en el botón de la actividad
            activity["button"].click()
            self.browser.sleep(1.5)
            
            # Buscar popup y determinar qué botón presionar
            
            # 1. Start
            try:
                if self.browser.page.get_by_text("Start", exact=True).is_visible(timeout=2000):
                    self.browser.page.get_by_text("Start", exact=True).click()
                    print("[INFO] Click en 'Start'")
                    self.browser.sleep(2)
                    return True
            except:
                pass
            
            # 2. Continue
            try:
                if self.browser.page.get_by_text("Continue", exact=False).is_visible(timeout=1000):
                    self.browser.page.get_by_text("Continue", exact=False).first.click()
                    print("[INFO] Click en 'Continue'")
                    self.browser.sleep(2)
                    return True
            except:
                pass
            
            # 3. Review
            try:
                if self.browser.page.get_by_text("Review", exact=True).is_visible(timeout=1000):
                    self.browser.page.get_by_text("Review", exact=True).click()
                    print("[INFO] Click en 'Review'")
                    self.browser.sleep(2)
                    return True
            except:
                pass
            
            # Si no hay popup, probablemente ya estamos en la actividad
            print("[INFO] No se detectó popup, continuando...")
            self.browser.sleep(1)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error iniciando actividad: {e}")
            return False

    def is_activity_complete(self) -> bool:
        """Verifica si la actividad actual está completa."""
        try:
            # Buscar el contador de preguntas (ej: "1/5", "5/5")
            try:
                # El contador está en un span con clase text-green-600
                progress_elements = self.browser.page.query_selector_all(".text-green-600, .text-lg")
                for el in progress_elements:
                    text = el.inner_text().strip()
                    match = re.search(r'(\d+)\s*/\s*(\d+)', text)
                    if match:
                        current, total = int(match.group(1)), int(match.group(2))
                        print(f"[DEBUG] Progreso: {current}/{total}")
                        if current >= total:
                            return True
                        return False
            except:
                pass
            
            # Si volvimos al dashboard, la actividad terminó
            current_url = self.browser.page.url
            if "dashboard" in current_url:
                return True
            
            # Buscar mensaje de completado (más estricto)
            try:
                # Buscar en elementos específicos de éxito o modal
                completion_selectors = [
                    ".swal2-title", # SweetAlert title
                    ".text-green-600.font-bold", # Success text
                    "h1:has-text('Congratulations')",
                    "h2:has-text('Activity Completed')",
                ]
                
                for sel in completion_selectors:
                    if self.browser.page.query_selector(sel):
                        text = self.browser.page.inner_text(sel).lower()
                        if "completed" in text or "congratulations" in text or "finished" in text:
                            print(f"[DEBUG] Actividad completada detectada por: {sel}")
                            return True
            except:
                pass
            
            return False
            
        except:
            return False
    
    def get_question_progress(self) -> tuple:
        """Obtiene el progreso actual de preguntas (current, total)."""
        try:
            body_text = self.browser.page.inner_text("body")
            match = re.search(r'(\d+)\s*/\s*(\d+)', body_text)
            if match:
                return int(match.group(1)), int(match.group(2))
        except:
            pass
        return 0, 0
    
    def has_next_question(self) -> bool:
        """Verifica si hay otra pregunta disponible con reintentos."""
        print("[DEBUG] Verificando si hay siguiente pregunta...")
        max_retries = 5
        for i in range(max_retries):
            try:
                # 1. Verificar visualmente elementos clave
                if self.browser.page.query_selector("h2.font-bold, h2.text-xl, .cardCheck, input[type='text'], [data-rbd-draggable-id], button:has-text('Waiting answer')"):
                    return True
                
                # 2. Verificar progreso numérico
                current, total = self.get_question_progress()
                if total > 0 and current < total:
                    print(f"[DEBUG] Progreso indica más preguntas: {current}/{total}")
                    return True
                
                # Si no encontramos nada, esperar y reintentar (la página podría estar cargando)
                if i < max_retries - 1:
                    self.browser.sleep(1.0)
            
            except:
                pass
        
        print("[DEBUG] No se detectó siguiente pregunta tras reintentos.")
        return False

    def handle_completion_screen(self) -> bool:
        """Maneja explícitamente la pantalla de 'CONGRATULATIONS'."""
        try:
            # Esperar un poco y verificar si aparece el mensaje de completado
            print("[DEBUG] Buscando pantalla de finalización...")
            
            completion_detected = False
            for _ in range(5): 
                try:
                    # 1. Título Congratulations
                    if self.browser.page.query_selector("h1:has-text('CONGRATULATIONS')"):
                        completion_detected = True
                        break
                    
                    # 2. Texto Lesson Completed
                    if self.browser.page.get_by_text("LESSON COMPLETED", exact=False).is_visible():
                        completion_detected = True
                        break
                    
                    # 3. Botón Continue (o el link que lo envuelve) - MUY ESPECÍFICO PARA EL CASO DEL USUARIO
                    if self.browser.page.query_selector("a[href='/dashboard']"):
                         completion_detected = True
                         break
                except: pass
                
                self.browser.sleep(0.5)
            
            if completion_detected:
                print("[INFO] Detectada pantalla de CONGRATULATIONS / LESSON COMPLETED")
                
                # REGLA PRIORITARIA: Cerrar modal SweetAlert si existe antes de intentar navegar
                try:
                    ok_btn = self.browser.page.locator("button.swal2-confirm")
                    if ok_btn.is_visible():
                        print("[INFO] Click en OK del modal de finalización")
                        ok_btn.click()
                        self.browser.sleep(2)
                except: pass
                
                # Intentar clickear CONTINUE
                try:
                    cont_btn = self.browser.page.get_by_text("CONTINUE", exact=True)
                    if cont_btn.is_visible():
                        cont_btn.click()
                        print("[INFO] Click en 'CONTINUE'")
                        self.browser.sleep(3) # Esperar navegación
                        return True
                    
                    # Fallback: Botón CONTINUE por selector
                    cont_btn_sel = self.browser.page.query_selector("button:has-text('CONTINUE')")
                    if cont_btn_sel and cont_btn_sel.is_visible():
                        cont_btn_sel.click()
                        print("[INFO] Click en 'CONTINUE' (Selector)")
                        self.browser.sleep(3)
                        return True
                except: pass
                
                # Fallback: Buscar enlace al dashboard
                dash_link = self.browser.page.query_selector("a[href='/dashboard']")
                if dash_link:
                    dash_link.click()
                    print("[INFO] Click en enlace al dashboard")
                    self.browser.sleep(3)
                    return True
            
            return False
        except Exception as e:
            print(f"[WARNING] Error en handle_completion_screen: {e}")
            return False

