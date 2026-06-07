
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
            "vocabulary", "reading", "speaking", "listening",
            "video", "match", "fill", "writing"
        ] # Default keywords if not specified elsewhere. 
        # Ideally this should be configurable or passed in, but hardcoding reasonable defaults similar to original agent logic.
        # Actually, in original code `activities_to_solve` was hardcoded or property of agent. 
        # Let's keep it here as a property or passed in init? 
        # The internal logic uses it. I'll define it here for now.

    # ── Fallback selectors for login form detection ──────────────────────────────

    _FALLBACK_EMAIL_SELECTORS = [
        "input[name='email']",
        "input[type='email']",
        "input[id='username']",
        "input[name='username']",
        "input[id='email']",
        "#username",
        "#email",
        "input[placeholder*='mail']",
        "input[placeholder*='email']",
        "input[placeholder*='usuario']",
        "input[placeholder*='correo']",
        "input[placeholder*='user']",
        "input[autocomplete='username']",
        "input[autocomplete='email']",
    ]

    _FALLBACK_PASSWORD_SELECTORS = [
        "input[type='password']",
        "#password",
        "input[name='pass']",
        "input[id='pass']",
        "input[autocomplete='current-password']",
    ]

    _FALLBACK_LOGIN_BUTTON_SELECTORS = [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Login')",
        "button:has-text('Sign in')",
        "button:has-text('Iniciar')",
        "button:has-text('Entrar')",
        "button:has-text('Ingresar')",
        "button:has-text('Acceder')",
        "button:has-text('Submit')",
    ]

    # ── Login ───────────────────────────────────────────────────────────────────

    def login(self) -> bool:
        """Realiza el login en la plataforma."""
        print("[INFO] Iniciando login...")

        try:
            # Iniciar navegador
            self.browser.start()

            # Ir a la página de login
            self.browser.goto(self.config["login_url"])

            # Esperar que el formulario esté listo o detectar si ya está logueado
            try:
                form_status = self.browser.wait_for_form_ready(
                    SELECTORS["email_input"], timeout=30
                )
            except Exception as exc:
                print(f"[ERROR] Error durante la espera del formulario: {exc}")
                self._capture_login_screenshot()
                return False

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
                print("[INFO] Esperando redirección al dashboard...")
                try:
                    # Wait for either the book header or a button containing 'BOOK'
                    self.browser.wait_for_selector(f"{SELECTORS['book_header']}, button:has-text('BOOK')", timeout=15000)
                except Exception:
                    pass
                
                self.browser.sleep(2)
                self.browser.wait_for_load(timeout=10000)
            else:
                # Timeout: formulario no detectado con el selector principal
                print("[ERROR] Tiempo de espera agotado: no se encontró el formulario de login.")
                self._capture_login_screenshot()
                print("[INFO] Intentando detectar formulario con selectores alternativos...")

                if not self._try_fallback_login():
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
            self._capture_login_screenshot()
            # Diagnóstico de página
            try:
                html_preview = self.browser.page.content()[:500]
                print(f"[DEBUG] HTML preview: {html_preview[:200]}...")
                # Listar inputs disponibles
                inputs = self.browser.page.evaluate("""() => {
                    const inputs = document.querySelectorAll('input, button');
                    return Array.from(inputs).map(el => ({
                        tag: el.tagName,
                        type: el.type || '',
                        name: el.name || '',
                        id: el.id || '',
                        placeholder: el.placeholder || '',
                        text: (el.innerText || '').substring(0, 50)
                    }));
                }""")
                print(f"[DEBUG] Form inputs found: {inputs}")
            except Exception as diag_err:
                print(f"[DEBUG] No se pudo obtener diagnóstico: {diag_err}")
            return False

    def _capture_login_screenshot(self) -> None:
        """Toma una captura de pantalla de la página de login para diagnóstico."""
        try:
            self.browser.screenshot("login_error.png")
            print("[INFO] Captura de pantalla guardada como 'login_error.png'")
        except Exception as exc:
            print(f"[WARNING] No se pudo tomar la captura de pantalla: {exc}")

    def _try_fallback_login(self) -> bool:
        """Intenta llenar el formulario de login con selectores alternativos.

        Recorre listas de selectores candidatos para email, contraseña y
        botón de envío. Si todos se encuentran, completa el formulario y
        retorna True. En caso contrario retorna False.

        Returns:
            True si se logró enviar el formulario, False si no.
        """
        email_sel = self._find_first_visible(self._FALLBACK_EMAIL_SELECTORS)
        if email_sel is None:
            print("[ERROR] No se encontró ningún campo de email/usuario "
                  "con selectores alternativos.")
            return False

        password_sel = self._find_first_visible(self._FALLBACK_PASSWORD_SELECTORS)
        if password_sel is None:
            print("[ERROR] No se encontró ningún campo de contraseña "
                  "con selectores alternativos.")
            return False

        login_sel = self._find_first_visible(self._FALLBACK_LOGIN_BUTTON_SELECTORS)
        if login_sel is None:
            print("[ERROR] No se encontró ningún botón de login "
                  "con selectores alternativos.")
            return False

        print(f"[INFO] Selectores alternativos encontrados: "
              f"email='{email_sel}', password='{password_sel}', "
              f"button='{login_sel}'")

        self.browser.fill(email_sel, self.config["email"])
        self.browser.sleep(0.5)
        self.browser.fill(password_sel, self.config["password"])
        self.browser.sleep(0.5)

        try:
            self.browser.click(login_sel)
        except Exception as exc:
            print(f"[ERROR] No se pudo hacer clic en el botón de login: {exc}")
            return False

        self.browser.sleep(3)
        self.browser.wait_for_load(timeout=10000)
        return True

    def _find_first_visible(self, selectors: list) -> str | None:
        """Retorna el primer selector de la lista que coincida con un elemento visible."""
        for sel in selectors:
            try:
                if self.browser.page.query_selector(sel):
                    return sel
            except Exception:
                continue
        return None

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
            # Detectar si estamos en la página principal sin sesión (redirect por session loss)
            current_url = self.browser.page.url.lower()
            if current_url.rstrip("/").endswith(":8443") or ("/signin" in current_url and "dashboard" not in current_url):
                print("[WARNING] Detectada redirección a pagina principal. Intentando login...")
                # Cerrar modal de "Bienvenidos" si existe
                try:
                    cerrar_btn = self.browser.page.query_selector("button:has-text('Cerrar')")
                    if cerrar_btn and cerrar_btn.is_visible():
                        cerrar_btn.click()
                        self.browser.sleep(0.5)
                        print("[INFO] Modal 'Bienvenidos' cerrado")
                except:
                    pass
                # Intentar login
                if self.login():
                    self.browser.sleep(2)
                else:
                    print("[ERROR] No se pudo hacer login tras redirección.")
                    return []
            
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
            
            candidates = []
            all_modules_info = []
            
            for idx, module in enumerate(modules):
                # ... loop logic remains the same ...
                title_el = module.query_selector(SELECTORS["module_title"])
                if not title_el:
                    for fallback in ["h2", "h3", "h1", "span"]:
                        title_el = module.query_selector(fallback)
                        if title_el and title_el.inner_text().strip():
                            break
                if not title_el or not title_el.inner_text().strip():
                    continue
                title = title_el.inner_text().strip()
                original_title = title
                # Duplicate naming logic
                count = 0
                for m_prev in modules[:idx+1]:
                    t_prev_el = m_prev.query_selector(SELECTORS["module_title"])
                    if not t_prev_el:
                        for fallback in ["h2", "h3", "h1", "span"]:
                            t_prev_el = m_prev.query_selector(fallback)
                            if t_prev_el and t_prev_el.inner_text().strip(): break
                    t_prev = t_prev_el.inner_text().strip() if t_prev_el else ""
                    if t_prev == original_title: count += 1
                if count > 1: title = f"{original_title} ({count})"

                if title in exclude_modules or original_title in exclude_modules or \
                   any(x in title.lower() for x in ["total progress", "navegación", "ajustes", "salir", "dashboard", "resultados", "results from"]):
                    continue
                
                # IMPORTANT: Also filter out generic activity names that are mistakenly picked up as modules because of class reuse
                if title.lower() in ["writing", "reading", "vocabulary", "grammar", "listening", "speaking", "practice", "quiz"]:
                    continue
                
                # Progress extraction
                progress_text = ""
                progress_el = module.query_selector(SELECTORS.get("module_progress", ""))
                if progress_el: progress_text = progress_el.inner_text().strip()
                if not progress_text or "%" not in progress_text:
                    spans = module.query_selector_all("span")
                    for span in spans:
                        text = span.inner_text().strip()
                        if "%" in text:
                            if "completed" in text.lower() or "progress" in text.lower() or "grade" in text.lower():
                                progress_text = text
                                break
                            if not progress_text: progress_text = text
                
                if not progress_text: continue
                
                match = re.search(r'(\d+)%', progress_text)
                if match:
                    progress = int(match.group(1))
                    all_modules_info.append(f"  - {title}: {progress}%")
                    if progress < 100:
                        candidates.append({
                            "title": title,
                            "progress": progress,
                            "element": module
                        })

            if candidates:
                # To prevent all agents from hitting the exact same module at the same time:
                # 1. Sort by progress descending (so we prioritize what's already started)
                # 2. But shuffle modules that have the EXACT same progress score
                import random
                from collections import defaultdict
                
                # Group by progress
                progress_bins = defaultdict(list)
                for c in candidates:
                    progress_bins[c['progress']].append(c)
                
                # Shuffle within each bin and re-flatten
                shuffled_candidates = []
                # Sort the keys (progress levels) descending
                for prog in sorted(progress_bins.keys(), reverse=True):
                    current_bin = progress_bins[prog]
                    random.shuffle(current_bin)
                    shuffled_candidates.extend(current_bin)
                    
                candidates = shuffled_candidates
                print(f"\n[INFO] Encontrados {len(candidates)} módulos incompletos.")
                return candidates

            print(f"\n[INFO] ❌ No se encontraron módulos incompletos")
            print(f"[DEBUG] Resumen de todos los módulos:")
            for info in all_modules_info:
                print(info)
            print(f"[DEBUG] ===================================================\n")
            
            # --- MANEJO DE NAVEGACIÓN ENTRE LIBROS ---
            # Si estamos aquí, es porque no hay módulos válidos o todos están al 100% en esta pantalla.
            # Intentar navegar a otros libros en el panel lateral.
            print("[INFO] Explorando panel de navegación lateral para otros 'BOOKS'...")
            try:
                # Buscar todos los elementos que parecen enlaces a libros (ej: "BOOK 1", "BOOK 2")
                book_links = self.browser.page.locator("text=/^BOOK [0-9]+$/i").all()
                if book_links:
                    print(f"[DEBUG] Se encontraron {len(book_links)} enlaces de libros detectados.")
                    
                    # Identificar el libro activo (suele tener diferente clase CSS, o simplemente probamos todos)
                    # Primero intentamos averiguar si hay un indicador visible de "completado"
                    # o si estamos actualmente en él (ej. título de página coincide).
                    for link in book_links:
                        link_text = link.inner_text().strip()
                        # Clickear todos los links de libros 1 por 1 buscando uno que tenga módulos al abrirse
                        # Haremos un simple check de visibilidad de progreso incompleto en la derecha.
                        print(f"[INFO] Revisando '{link_text}'...")
                        link.click()
                        self.browser.sleep(3) # Esperar a que los módulos carguen
                        
                        # Check rapidly if this new book has incomplete modules
                        new_modules = self.browser.page.query_selector_all(SELECTORS["module_container"])
                        has_incomplete = False
                        for idx_new, m in enumerate(new_modules):
                            t_el = m.query_selector(SELECTORS["module_title"])
                            if not t_el:
                                for fallback in ["h2", "h3", "h1", "span"]:
                                    t_el = m.query_selector(fallback)
                                    if t_el and t_el.inner_text().strip(): break
                            raw_title = t_el.inner_text().strip() if t_el else ""
                            m_title = raw_title
                            
                            # Duplicate naming logic
                            count = 0
                            for m_prev in new_modules[:idx_new+1]:
                                t_prev_el = m_prev.query_selector(SELECTORS["module_title"])
                                if not t_prev_el:
                                    for fallback in ["h2", "h3", "h1", "span"]:
                                        t_prev_el = m_prev.query_selector(fallback)
                                        if t_prev_el and t_prev_el.inner_text().strip(): break
                                t_prev = t_prev_el.inner_text().strip() if t_prev_el else ""
                                if t_prev == raw_title: count += 1
                            if count > 1: m_title = f"{raw_title} ({count})"

                            if m_title in exclude_modules or raw_title in exclude_modules:
                                continue
                            
                            # Skip widgets
                            if any(x in m_title.lower() for x in ["total progress", "navegación", "dashboard", "results from"]) or m_title.lower() in ["writing", "reading", "vocabulary", "grammar", "listening", "speaking"]:
                                continue
                                
                            p_el = m.query_selector(SELECTORS.get("module_progress", ""))
                            p_text = p_el.inner_text().strip() if p_el else ""
                            if not p_text or "%" not in p_text:
                                for span in m.query_selector_all("span"):
                                    t = span.inner_text().strip()
                                    if "%" in t: 
                                        p_text = t
                                        break
                            
                            if p_text:
                                p_match = re.search(r'(\d+)%', p_text)
                                if p_match and int(p_match.group(1)) < 100:
                                    # Encontramos un módulo incompleto!
                                    print(f"[SUCCESS] Se encontró trabajo en '{link_text}' - {m_title} ({p_match.group(1)}%)")
                                    has_incomplete = True
                                    break
                                    
                        if has_incomplete:
                            # Hacer llamada recursiva ahora que la página tiene módulos
                            print("[INFO] Reiniciando búsqueda en el nuevo libro...")
                            return self.find_incomplete_module(exclude_modules=exclude_modules)
                            
                print("[INFO] Se revisaron todos los libros. No hay más trabajo pendiente.")
            except Exception as e:
                print(f"[WARNING] Error explorando otros libros: {e}")
                
            return []
            
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
                is_disabled = button.get_attribute("disabled") is not None if button else False
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
                
                if skip_reason:
                     print(f"[DEBUG] SKIPPING {name}: {skip_reason}")
                elif height >= 100:
                    skip_reason = "✅ Ya completa (100%)"
                
                status = skip_reason if skip_reason else "🎯 CANDIDATA"
                print(f"[DEBUG] Actividad: '{name}' | Progreso: {height}% | Disabled: {is_disabled} | Status: {status}")
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
            
            # Verificar si no hay candidatos porque están todos en skip_activities (ocupados)
            busy_count = 0
            for idx, activity in enumerate(activities):
                name_el = activity.query_selector(SELECTORS["activity_name"])
                if name_el:
                    name = name_el.inner_text().lower()
                    if name in skip_activities:
                        # Es una actividad que el agente intentó pero estaba ocupada
                        busy_count += 1
            
            if busy_count > 0:
                # print(f"[DEBUG] Módulo tiene {busy_count} actividades ocupadas por otros agentes.")
                return {"status": "busy"}

            # FALLBACK: Si el módulo no está al 100% pero no encontramos candidatas,
            # tal vez sea porque 'listening' u otra actividad crítica aparece como '0%' o sin barra
            print("[DEBUG] No se encontraron candidatos con progreso > 0. Buscando actividades disponibles (0%)...")
            for idx, activity in enumerate(activities):
                 name_el = activity.query_selector(SELECTORS["activity_name"])
                 if not name_el: continue
                 name = name_el.inner_text().lower()
                 
                 # Si es un target válido y NO está bloqueada y NO está 100%
                 button = activity.query_selector("button")
                 is_disabled = button.get_attribute("disabled") is not None if button else False
                 
                 # Check progress again
                 bfill = activity.query_selector(SELECTORS["progress_fill"])
                 height = 0
                 if bfill:
                    style = bfill.get_attribute("style") or ""
                    match = re.search(r'height:\s*(\d+)%', style)
                    if match: height = int(match.group(1))

                 if any(key in name for key in self.activities_to_solve) and not is_disabled and height < 100:
                      if name in skip_activities:
                          # Ya lo contamos arriba como busy, pero por si acaso
                          continue
                      
                      print(f"[INFO] ⚠️ FALLBACK: Seleccionando actividad '{name}' (0% o invisible) para intentar avanzar.")
                      return {
                        "name": name,
                        "progress": height,
                        "element": activity,
                        "button": button
                    }

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
    
    def advance_if_possible(self) -> bool:
        """
        Intenta avanzar manualmente si existe botón de 'Next'.
        Retorna True si se hizo click en un botón de avance.
        Esta función SOLO avanza, no detecta.
        """
        print("[NAV] Buscando botón de avance...")
        next_selectors = [
             "button[aria-label='Next']",
             "button[data-action='next']",
             "button.next-btn",
             "div[title='Next']",
             "i.fa-chevron-right",
             "i.fa-arrow-right",
             "button:has(i.fa-chevron-right)",
             ".carousel-control-next",
             "button:has-text('Next')",
             "button:has-text('Continue')"
        ]
        
        for sel in next_selectors:
            try:
                if self.browser.page.query_selector(sel):
                    if self.browser.page.is_visible(sel):
                        print(f"[NAV] Encontrado botón de avance '{sel}', haciendo click...")
                        self.browser.page.click(sel)
                        # Esperar dinámicamente la carga tras el avance
                        try:
                            self.browser.page.wait_for_load_state("networkidle", timeout=5000)
                        except:
                            pass
                        self.browser.sleep(0.2)
                        return True
            except Exception as e:
                print(f"[WARNING] Error intentando avanzar con '{sel}': {e}")
        
        return False
    
    def has_next_question(self) -> bool:
        """Verifica si hay otra pregunta disponible (SIN efectos secundarios)."""
        print("[DEBUG] Verificando si hay siguiente pregunta...")
        
        # Primero, esperar dinámicamente que aparezca un elemento de pregunta
        question_selectors = [
            "h2.font-bold", "h2.text-xl", ".cardCheck", 
            "input[type='text']", "[data-rbd-draggable-id]", 
            "button:has-text('Waiting answer')"
        ]
        for qsel in question_selectors:
            try:
                self.browser.page.wait_for_selector(qsel, timeout=2000)
                return True
            except:
                continue
        
        # Fallback: reintentar con sleeps cortos si el wait dinámico falló
        for i in range(3):
            try:
                # 1. Verificar visualmente elementos clave
                for qsel in question_selectors:
                    if self.browser.page.query_selector(qsel):
                        return True
                
                # 2. Verificar progreso numérico
                current, total = self.get_question_progress()
                if total > 0 and current < total:
                    print(f"[DEBUG] Progreso indica más preguntas: {current}/{total}")
                    return True
                
                # 3. Verificar si la actividad está completa
                if self.is_activity_complete():
                    return False
                
                if i < 2:
                    self.browser.sleep(0.3)
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

