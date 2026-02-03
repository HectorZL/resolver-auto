"""
Agente principal para resolver exámenes automáticamente.
"""

import json
import time
import re
from pathlib import Path

from browser_controller import BrowserController
from gemini_solver import GeminiSolver
from selectors import SELECTORS, ACTIVITY_COLORS


class ExamAgent:
    """Agente de IA para resolver exámenes automáticamente."""
    
    def __init__(self, config_path: str = "config.json"):
        """Inicializa el agente con la configuración."""
        # Cargar configuración
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        # Inicializar componentes
        self.browser = BrowserController(headless=self.config.get("headless", False))
        self.solver = GeminiSolver(self.config["gemini_api_key"])
        self.delay = self.config.get("delay_between_questions", 2)
        self.activities_to_solve = self.config.get("activities_to_solve", ["vocabulary"])
        
        # Estado
        self.logged_in = False
        self.current_module = None
        self.current_activity = None
        self.questions_answered = 0
        
        print("[INFO] Agente inicializado")
    
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
                self.logged_in = True
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
            if self.browser.exists(SELECTORS["book_header"]) or "dashboard" in self.browser.page.url.lower():
                self.logged_in = True
                print("[SUCCESS] Login exitoso!")
                return True
            else:
                print("[WARNING] Login posiblemente fallido, continuando...")
                self.logged_in = True
                return True
                
        except Exception as e:
            print(f"[ERROR] Error en login: {e}")
            return False
    
    def find_incomplete_module(self) -> dict:
        """Encuentra el primer módulo incompleto."""
        print("[INFO] Buscando módulo incompleto...")
        
        try:
            # Buscar todos los contenedores de módulos
            modules = self.browser.page.query_selector_all(SELECTORS["module_container"])
            
            for module in modules:
                # Obtener el título y progreso
                title_el = module.query_selector(SELECTORS["module_title"])
                progress_el = module.query_selector("span.text-green-800, span.text-yellow-400, span")
                
                if not title_el:
                    continue
                    
                title = title_el.inner_text()
                progress_text = ""
                
                # Buscar el texto de progreso
                spans = module.query_selector_all("span")
                for span in spans:
                    text = span.inner_text()
                    if "%" in text and "completed" in text.lower():
                        progress_text = text
                        break
                
                # Extraer porcentaje
                match = re.search(r'(\d+)%', progress_text)
                if match:
                    progress = int(match.group(1))
                    
                    if progress < 100:
                        print(f"[INFO] Módulo incompleto encontrado: {title} ({progress}%)")
                        return {
                            "title": title,
                            "progress": progress,
                            "element": module
                        }
            
            print("[INFO] No se encontraron módulos incompletos")
            return None
            
        except Exception as e:
            print(f"[ERROR] Error buscando módulos: {e}")
            return None
    
    def find_incomplete_activity(self, module_element) -> dict:
        """Encuentra una actividad incompleta dentro de un módulo."""
        print("[INFO] Buscando actividad incompleta...")
        
        try:
            # Buscar tooltips (contenedores de actividades)
            activities = module_element.query_selector_all(SELECTORS["activity_tooltip"])
            
            for activity in activities:
                # Obtener nombre de la actividad
                name_el = activity.query_selector(SELECTORS["activity_name"])
                if not name_el:
                    continue
                    
                name = name_el.inner_text().lower()
                
                # Verificar si es una actividad que queremos resolver
                if name not in self.activities_to_solve:
                    continue
                
                # Verificar el progreso (color del bfill)
                bfill = activity.query_selector(SELECTORS["progress_fill"])
                if bfill:
                    style = bfill.get_attribute("style") or ""
                    
                    # Extraer altura del progreso
                    height_match = re.search(r'height:\s*(\d+)%', style)
                    height = int(height_match.group(1)) if height_match else 0
                    
                    # Si no está al 100%, es incompleta
                    if height < 100:
                        # Obtener el botón
                        button = activity.query_selector("button")
                        
                        print(f"[INFO] Actividad incompleta: {name} ({height}%)")
                        return {
                            "name": name,
                            "progress": height,
                            "element": activity,
                            "button": button
                        }
            
            print("[INFO] No se encontraron actividades incompletas en este módulo")
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
            # Puede ser "Start" o "Review"
            try:
                # Intentar encontrar botón Start primero
                if self.browser.page.get_by_text("Start", exact=True).is_visible(timeout=2000):
                    self.browser.page.get_by_text("Start", exact=True).click()
                    print("[INFO] Click en 'Start'")
                    self.browser.sleep(2)
                    return True
            except:
                pass
            
            try:
                # Intentar encontrar botón Continue o similar
                if self.browser.page.get_by_text("Continue", exact=False).is_visible(timeout=1000):
                    self.browser.page.get_by_text("Continue", exact=False).first.click()
                    print("[INFO] Click en 'Continue'")
                    self.browser.sleep(2)
                    return True
            except:
                pass
            
            try:
                # Intentar Review
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
    
    def solve_current_question(self) -> bool:
        """Resuelve la pregunta actual en pantalla detectando el tipo de pregunta."""
        print("[INFO] Analizando pregunta...")
        
        try:
            # 1. Extraer pregunta del h2
            question_text = self._get_question_text()
            print(f"[INFO] Pregunta: {question_text[:100]}..." if question_text else "[INFO] No se encontró pregunta")
            
            # 2. Detectar tipo de pregunta
            question_type = self._detect_question_type()
            print(f"[INFO] Tipo de pregunta: {question_type}")
            
            # 3. Resolver según el tipo
            if question_type == "multiple_choice":
                return self._solve_multiple_choice(question_text)
            elif question_type == "fill_blanks":
                return self._solve_fill_blanks(question_text)
            elif question_type == "matching_buttons":
                return self._solve_matching_buttons(question_text)
            elif question_type == "image_drag_match":
                return self._solve_image_drag_match(question_text)
            elif question_type == "text_match":
                return self._solve_text_match(question_text)
            elif question_type == "image_with_options":
                return self._solve_image_with_options(question_text)
            elif question_type == "matching_requirements":
                return self._solve_matching_requirements(question_text)
            elif question_type == "sentence_completion":
                return self._solve_sentence_completion(question_text)
            elif question_type == "sentence_ordering":
                return self._solve_sentence_ordering(question_text)
            else:
                # Tipo desconocido - tomar screenshot y usar Gemini para análisis visual
                return self._solve_with_screenshot(question_text)
            
        except Exception as e:
            print(f"[ERROR] Error resolviendo pregunta: {e}")
            return False
    
    def _get_question_text(self) -> str:
        """Extrae el texto de la pregunta."""
        try:
            h2_elements = self.browser.page.query_selector_all("h2.font-bold, h2")
            for h2 in h2_elements:
                text = h2.inner_text().strip()
                if text and len(text) > 10:
                    return text
        except:
            pass
        return ""
    
    def _detect_question_type(self) -> str:
        """Detecta el tipo de pregunta en la página."""
        try:
            # Verificar si hay cardCheck (opción múltiple tradicional)
            cards = self.browser.page.query_selector_all(".cardCheck")
            if len(cards) > 0:
                return "multiple_choice"
            
            # Verificar si hay inputs de texto (fill in blanks)
            inputs = self.browser.page.query_selector_all("input[type='text']")
            if len(inputs) > 0:
                return "fill_blanks"
            
            # Verificar si hay elementos arrastrables para ordenar oraciones
            draggables = self.browser.page.query_selector_all("[data-rbd-draggable-id]")
            if len(draggables) > 0:
                return "sentence_ordering"
            
            # Verificar si hay drag & drop con imágenes (botones "Waiting answer...")
            waiting_btns = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            if len(waiting_btns) > 0:
                h2_text = self._get_question_text().lower()
                if "match the sentence" in h2_text and "option" in h2_text and not self.browser.page.query_selector("img[alt='Descripción de la imagen']"):
                    return "text_match"
                return "image_drag_match"
            
            # Verificar si hay matching con botones activar-btn
            activar_btns = self.browser.page.query_selector_all("button.activar-btn")
            if len(activar_btns) > 0:
                # Verificar si hay imagen o párrafo de texto
                images = self.browser.page.query_selector_all("img[alt='Descripción de la imagen']")
                paragraph = self.browser.page.query_selector(".overflow-y-auto, div[class*='text-justify']")
                if len(images) > 0 or paragraph:
                    return "matching_buttons"
                else:
                    return "sentence_completion"
            
            # Verificar si hay matching de requisitos SIN activar-btn
            requirement_btns = self.browser.page.query_selector_all("button:has-text('MATRIC'), button:has-text('GRADUATE')")
            if len(requirement_btns) >= 4:
                return "matching_requirements"
            
            # Verificar si hay imagen + botones simples (Male, Female, Both)
            images = self.browser.page.query_selector_all("img[alt='Descripción de la imagen']")
            simple_btns = self.browser.page.query_selector_all("button.border-gray-300, button.rounded-xl")
            if len(images) > 0 and len(simple_btns) > 0:
                return "image_with_options"
            
            return "unknown"
        except:
            return "unknown"
    
    def _solve_multiple_choice(self, question_text: str) -> bool:
        """Resuelve preguntas de opción múltiple."""
        try:
            # Extraer opciones
            options = []
            option_elements = []
            cards = self.browser.page.query_selector_all(".cardCheck")
            for card in cards:
                button = card.query_selector("button")
                if button:
                    option_text = button.inner_text().strip()
                    if option_text:
                        options.append(option_text)
                        option_elements.append(card)
            
            print(f"[INFO] Opciones: {options}")
            
            if not options:
                return False
            
            # Verificar si hay imagen
            has_image = self.browser.page.query_selector("img[alt='Descripción de la imagen']") is not None
            
            if has_image:
                # Tomar screenshot y analizar con imagen
                screenshot = self.browser.screenshot()
                
                prompt = f"""PREGUNTA: {question_text}

OPCIONES: {options}

Mira la imagen y selecciona la opción correcta.
Responde SOLO con el número de la opción (0, 1, 2, 3, etc.)"""
                
                image_part = {
                    "mime_type": "image/png",
                    "data": __import__('base64').b64encode(screenshot).decode()
                }
                
                response = self.solver.model.generate_content([prompt, image_part])
                result_text = response.text.strip()
                print(f"[DEBUG] Gemini: {result_text}")
                
                # Extraer número
                import re
                match = re.search(r'(\d+)', result_text)
                if match:
                    answer_index = int(match.group(1))
                else:
                    answer_index = 0
            else:
                # Sin imagen, usar método de solo texto
                result = self.solver.analyze_question_text_only(question_text, options)
                answer_index = result.get("answer_index", 0)
            
            if answer_index < 0 or answer_index >= len(options):
                answer_index = 0
            
            answer_text = options[answer_index]
            print(f"[INFO] Respuesta: {answer_text}")
            
            # Click en la opción
            option_elements[answer_index].click()
            self.browser.sleep(0.3)
            
            # Click en CHECK
            self._click_check_button()
            self.browser.sleep(0.5)
            
            # Click en OK del modal
            self._click_ok_modal()
            
            self.questions_answered += 1
            print(f"[SUCCESS] Pregunta {self.questions_answered} respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en multiple choice: {e}")
            return False
    
    def _solve_fill_blanks(self, question_text: str) -> bool:
        """Resuelve preguntas de llenar espacios con inputs."""
        try:
            # Encontrar los bloques con las pistas y sus inputs
            containers = self.browser.page.query_selector_all(".bg-white.p-6.rounded-2xl")
            
            fill_data = []
            for container in containers:
                # Buscar la pista (texto con guiones)
                hint_el = container.query_selector("span.text-lg, span.font-medium")
                input_el = container.query_selector("input[type='text']")
                
                if hint_el and input_el:
                    hint = hint_el.inner_text().strip()
                    fill_data.append({"hint": hint, "input": input_el})
            
            if not fill_data:
                # Intentar otro selector
                inputs = self.browser.page.query_selector_all("input[type='text']")
                for inp in inputs:
                    parent = inp.evaluate("el => el.closest('.bg-white')")
                    if parent:
                        hint_text = self.browser.page.evaluate("el => el.textContent", parent)
                        # Extraer solo el texto de la pista (antes del input)
                        hint = hint_text.split("...")[0].strip() if "..." in hint_text else hint_text.strip()
                        fill_data.append({"hint": hint[:50], "input": inp})
            
            print(f"[INFO] Encontradas {len(fill_data)} palabras para completar")
            
            if not fill_data:
                return False
            
            # Crear prompt para Gemini
            hints = [item["hint"] for item in fill_data]
            prompt = f"""Pregunta: {question_text}

Las siguientes palabras tienen letras faltantes (representadas por _). 
Completa cada palabra:

"""
            for i, hint in enumerate(hints):
                prompt += f"{i+1}. {hint} = ?\n"
            
            prompt += """
Responde SOLO con las palabras completas, una por línea, en el mismo orden.
Por ejemplo:
Football
Tennis
etc."""
            
            # Llamar a Gemini
            result = self.solver.model.generate_content(prompt)
            response = result.text.strip()
            print(f"[INFO] Respuesta de Gemini:\n{response}")
            
            # Parsear respuestas
            answers = [line.strip() for line in response.split("\n") if line.strip()]
            
            # Llenar los inputs
            for i, item in enumerate(fill_data):
                if i < len(answers):
                    answer = answers[i]
                    # Limpiar respuesta (quitar números, puntos, etc.)
                    answer = re.sub(r'^\d+[\.\)]\s*', '', answer).strip()
                    
                    print(f"[INFO] Llenando: {item['hint']} → {answer}")
                    item["input"].fill(answer)
                    self.browser.sleep(0.3)
            
            self.browser.sleep(0.5)
            
            # Click en CHECK
            self._click_check_button()
            self.browser.sleep(1)
            
            # Click en OK del modal
            self._click_ok_modal()
            
            self.questions_answered += 1
            print(f"[SUCCESS] Pregunta {self.questions_answered} respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en fill blanks: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_sentence_ordering(self, question_text: str) -> bool:
        """Resuelve preguntas de ordenar oraciones (múltiples suportadas)."""
        try:
            print("[INFO] Resolviendo pregunta de ordenar oraciones...")
            
            # 1. Encontrar todos los contenedores de oraciones (droppables) usando índices para evitar stale elements
            droppables_count = len(self.browser.page.query_selector_all("[data-rbd-droppable-id^='droppable-desktop']"))
            selector_prefix = "[data-rbd-droppable-id^='droppable-desktop']"
            
            if droppables_count == 0:
                droppables_count = len(self.browser.page.query_selector_all("[data-rbd-droppable-id^='droppable-mobile']"))
                selector_prefix = "[data-rbd-droppable-id^='droppable-mobile']"
            
            if droppables_count == 0:
                droppables_count = len(self.browser.page.query_selector_all("[data-rbd-droppable-id]"))
                selector_prefix = "[data-rbd-droppable-id]"
            
            if droppables_count == 0:
                print("[WARNING] No se encontraron contenedores droppable")
                return self._solve_with_screenshot(question_text)
            
            print(f"[INFO] Encontradas {droppables_count} oraciones para ordenar")
            
            for index in range(droppables_count):
                print(f"--- Ordenando Oración {index + 1} ---")
                
                # RE-QUERY para obtener handle fresco y valido
                droppables = self.browser.page.query_selector_all(selector_prefix)
                if index >= len(droppables):
                    print("[WARNING] Índice fuera de rango tras refresh")
                    break
                droppable = droppables[index]
                
                # Scroll al contenedor actual
                try:
                    droppable.scroll_into_view_if_needed()
                    self.browser.sleep(0.5)
                except Exception as e:
                    print(f"[WARNING] No se pudo hacer scroll al contenedor: {e}")
                    # Reintentar obtener
                    droppables = self.browser.page.query_selector_all(selector_prefix)
                    droppable = droppables[index]
                
                # 2. Extraer elementos arrastrables y sus textos
                draggables = droppable.query_selector_all("[data-rbd-draggable-id]")
                words = []
                for el in draggables:
                    text = el.inner_text().strip()
                    drag_id = el.get_attribute("data-rbd-draggable-id")
                    words.append({"text": text, "id": drag_id, "element": el})
                
                if not words:
                    continue
                
                current_order = [w['text'] for w in words]
                print(f"[INFO] Palabras actuales: {current_order}")
                
                # 3. Preguntar a Gemini el orden correcto
                prompt = f"""Ordena estas palabras para formar una oración correcta: {current_order}
Responde SOLO con las palabras separadas por | (ejemplo: She | is | happy)"""
                
                response = self.solver.model.generate_content(prompt)
                result = response.text.strip()
                print(f"[DEBUG] Gemini orden: {result}")
                
                # 4. Parsear el orden correcto
                correct_order = [w.strip() for w in result.split("|")]
                print(f"[INFO] Orden correcto: {correct_order}")
                
                # 5. Reordenar
                max_moves = len(correct_order) * len(correct_order)
                moves_made = 0
                last_order = None
                stuck_count = 0
                
                while moves_made < max_moves:
                    self.browser.sleep(0.5) # Aumentar un poco el sleep
                    
                    # CRITICAL FIX: Re-obtener el contenedor padre (droppable) en CADA paso
                    # porque React puede re-renderizar todo el componente tras un drop
                    droppables = self.browser.page.query_selector_all(selector_prefix)
                    if index >= len(droppables):
                        print("[WARNING] Índice de droppable inválido tras refresh")
                        break
                    droppable = droppables[index]

                    # Re-query elements inside THIS droppable
                    current_draggables = droppable.query_selector_all("[data-rbd-draggable-id]")
                    
                    if not current_draggables:
                        # Fallback extra agresivo
                        self.browser.sleep(0.5)
                        droppables = self.browser.page.query_selector_all(selector_prefix)
                        if index < len(droppables):
                            droppable = droppables[index]
                            current_draggables = droppable.query_selector_all("[data-rbd-draggable-id]")
                        else:
                            break

                    current_texts = [el.inner_text().strip().lower() for el in current_draggables]
                    correct_texts = [w.lower() for w in correct_order]
                    
                    # Verificar si coincide
                    if current_texts == correct_texts:
                        print(f"[INFO] Oración {index + 1} ordenada.")
                        break
                    
                    # Detectar stuck
                    if current_texts == last_order:
                        stuck_count += 1
                        if stuck_count >= 3:
                            print("[WARNING] Ordenamiento atascado, pasando a siguiente...")
                            break
                    else:
                        stuck_count = 0
                    last_order = current_texts.copy()
                    
                    # Mover
                    moved = False
                    for i, correct_word in enumerate(correct_texts):
                        if i >= len(current_texts): break
                        if current_texts[i] != correct_word:
                            # Buscar dónde está la palabra correcta
                            for j in range(i + 1, len(current_texts)):
                                if current_texts[j] == correct_word:
                                    # Mover elemento j a posición i usando drag_to
                                    source_el = current_draggables[j]
                                    target_el = current_draggables[i]
                                    
                                    try:
                                        # INTENTO CON TECLADO (Más robusto para items con scroll)
                                        # 1. Enfocar el elemento
                                        source_el.focus()
                                        self.browser.sleep(0.1)
                                        
                                        # 2. Levantar con Espacio
                                        self.browser.page.keyboard.press("Space")
                                        self.browser.sleep(0.1)
                                        
                                        # 3. Mover con flechas
                                        steps = abs(j - i)
                                        key = "ArrowLeft" if j > i else "ArrowRight"
                                        
                                        for _ in range(steps):
                                            self.browser.page.keyboard.press(key)
                                            self.browser.sleep(0.05)
                                        
                                        # 4. Soltar con Espacio
                                        self.browser.page.keyboard.press("Space")
                                        
                                        print(f"[INFO] Movido '{correct_word}' de pos {j} a {i} (teclado)")
                                        moves_made += 1
                                        moved = True
                                        self.browser.sleep(0.5)
                                        
                                    except Exception as key_err:
                                        print(f"[DEBUG] Falló teclado: {key_err}")
                                        # Fallback: Mouse Drag (si el teclado falla)
                                        try:
                                            # Asegurar visibilidad
                                            source_el.scroll_into_view_if_needed()
                                            target_el.scroll_into_view_if_needed()
                                            
                                            box_src = source_el.bounding_box()
                                            box_dst = target_el.bounding_box()
                                            if box_src and box_dst:
                                                self.browser.page.mouse.move(box_src["x"] + box_src["width"]/2, box_src["y"] + box_src["height"]/2)
                                                self.browser.page.mouse.down()
                                                self.browser.page.mouse.move(box_dst["x"] + box_dst["width"]/2, box_dst["y"] + box_dst["height"]/2, steps=10)
                                                self.browser.page.mouse.up()
                                                moves_made += 1
                                                moved = True
                                        except:
                                            pass
                                    break
                            if moved: break
                    
                    if not moved:
                        break

            # 6. CHECK FINAL
            self.browser.sleep(0.5)
            self._click_check_button()
            self.browser.sleep(0.5)
            self._click_ok_modal()
            
            self.questions_answered += 1
            print(f"[SUCCESS] Pregunta (sentence ordering) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en sentence ordering: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_sentence_completion(self, question_text: str) -> bool:
        """Resuelve preguntas de completar oraciones con verbos/palabras."""
        try:
            print("[INFO] Resolviendo pregunta de completar oraciones...")
            
            # 1. Extraer las filas - cada fila tiene botones + texto
            rows_data = []
            row_containers = self.browser.page.query_selector_all(".p-5.bg-white.rounded-xl, div[class*='p-5'][class*='bg-white']")
            
            for container in row_containers:
                # Obtener todos los spans de texto
                spans = container.query_selector_all("span.text-lg, span.font-medium, span.text-gray-700")
                text_parts = [span.inner_text().strip() for span in spans if span.inner_text().strip()]
                
                # Obtener los botones
                buttons = container.query_selector_all("button.activar-btn")
                if not buttons:
                    continue
                    
                options = []
                for btn in buttons:
                    txt = btn.inner_text().strip()
                    if txt:
                        options.append({"text": txt, "element": btn})
                
                if options:
                    # Formar la oración: texto + [BLANK] o [BLANK] + texto
                    sentence = " ".join(text_parts) if text_parts else ""
                    rows_data.append({
                        "sentence": sentence,
                        "options": options
                    })
            
            if not rows_data:
                print("[WARNING] No se encontraron oraciones")
                return self._solve_with_screenshot(question_text)
            
            print(f"[INFO] {len(rows_data)} oraciones a completar:")
            for i, row in enumerate(rows_data):
                print(f"  {i+1}. '{row['sentence']}' → [{', '.join([o['text'] for o in row['options']])}]")
            
            # 2. Crear prompt conciso para Gemini
            sentences_text = ""
            for i, row in enumerate(rows_data):
                opts = ', '.join([o['text'] for o in row['options']])
                sentences_text += f"\n{i+1}. _{row['sentence']}_ → [{opts}]"
            
            prompt = f"""Completa:{sentences_text}

Responde:
1. PALABRA
2. PALABRA
..."""
            
            response = self.solver.model.generate_content(prompt)
            result = response.text.strip()
            print(f"[DEBUG] Gemini: {result}")
            
            # 3. Parsear respuestas y hacer clicks
            import re
            lines = result.split("\n")
            clicked = 0
            
            # Función para normalizar texto (quita espacios, normaliza apóstrofes)
            def normalize(text):
                return text.upper().replace("´", "'").replace("`", "'").strip()
            
            for line in lines:
                match = re.search(r'(\d+)\.\s*(.+)', line)
                if match:
                    idx = int(match.group(1)) - 1
                    answer = normalize(match.group(2))
                    
                    if 0 <= idx < len(rows_data):
                        row = rows_data[idx]
                        
                        # PRIMERO: buscar match EXACTO
                        matched_opt = None
                        
                        # Fix: Mapeo de respuestas semánticas (TRUE/FALSE/VERDADERO) a botones T/F
                        if answer in ["VERDADERO", "TRUE"]:
                            # Buscar si hay opción 'T'
                            if any(normalize(o['text']) == 'T' for o in row['options']):
                                answer = "T"
                        elif answer in ["FALSO", "FALSE"]:
                            if any(normalize(o['text']) == 'F' for o in row['options']):
                                answer = "F"

                        # PRIMERO: buscar match EXACTO
                        for opt in row['options']:
                            opt_norm = normalize(opt['text'])
                            if opt_norm == answer:
                                matched_opt = opt
                                break
                        
                        # SEGUNDO: si no hay exacto, buscar la opción más corta que contenga la respuesta
                        if not matched_opt:
                            candidates = []
                            for opt in row['options']:
                                opt_norm = normalize(opt['text'])
                                if answer in opt_norm:
                                    candidates.append((len(opt_norm), opt))
                            if candidates:
                                # Elegir la más corta (más específica)
                                candidates.sort(key=lambda x: x[0])
                                matched_opt = candidates[0][1]
                        
                        if matched_opt:
                            print(f"[INFO] Oración {idx+1} → {matched_opt['text']}")
                            try:
                                matched_opt['element'].click()
                                clicked += 1
                                self.browser.sleep(0.2)
                            except:
                                # Si falla, intentar con selector de texto
                                try:
                                    self.browser.page.click(f"button.activar-btn:has-text('{matched_opt['text']}')", timeout=2000)
                                    clicked += 1
                                except:
                                    print(f"[WARNING] No se pudo hacer click en {matched_opt['text']}")
            
            print(f"[INFO] Clicks realizados: {clicked}")
            
            # 4. CHECK
            self.browser.sleep(0.3)
            self._click_check_button()
            self.browser.sleep(0.5)
            self._click_ok_modal()
            
            self.questions_answered += 1
            print(f"[SUCCESS] Pregunta {self.questions_answered} (sentence completion) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en sentence completion: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_matching_buttons(self, question_text: str) -> bool:
        """Resuelve preguntas de matching con múltiples botones por fila."""
        try:
            print("[INFO] Resolviendo pregunta de matching con botones...")
            
            # 1. Tomar screenshot para análisis visual
            screenshot = self.browser.screenshot()
            
            # 2. Extraer las filas y sus opciones
            rows_data = []
            row_containers = self.browser.page.query_selector_all(".p-5.bg-white.rounded-xl, div[class*='p-5'][class*='bg-white']")
            
            for container in row_containers:
                # Obtener TODOS los spans de texto (partes de la oración)
                spans = container.query_selector_all("span.text-lg, span.font-medium, span.text-gray-700")
                text_parts = []
                for span in spans:
                    txt = span.inner_text().strip()
                    if txt:
                        text_parts.append(txt)
                
                # Formar el "label" como la oración completa con marcador para opciones
                label = " [___] ".join(text_parts) if text_parts else ""
                if not label:
                    # Si no hay spans, usar el texto completo del contenedor menos los botones
                    full_text = container.inner_text()
                    label = full_text[:100] if len(full_text) > 100 else full_text
                
                # Obtener los botones de opciones
                buttons = container.query_selector_all("button.activar-btn")
                options = []
                for btn in buttons:
                    option_text = btn.inner_text().strip()
                    options.append({"text": option_text, "element": btn})
                
                if options:
                    rows_data.append({"label": label, "options": options})
            
            if not rows_data:
                print("[WARNING] No se encontraron filas de matching")
                return self._solve_with_screenshot(question_text)
            
            print(f"[INFO] Encontradas {len(rows_data)} filas")
            for row in rows_data:
                print(f"  - '{row['label']}': {[opt['text'] for opt in row['options']]}")
            
            # 3. Crear prompt para Gemini
            options_text = ""
            for i, row in enumerate(rows_data):
                options_text += f"\n{i+1}. '{row['label']}'"
            
            # Detectar si es TRUE/FALSE
            is_true_false = all(
                any(o['text'].upper() in ['TRUE', 'FALSE'] for o in row['options'])
                for row in rows_data
            )
            
            # Detectar imagen y párrafo de texto
            has_image = self.browser.page.query_selector("img[alt='Descripción de la imagen']") is not None
            
            # Buscar párrafo de texto (div con overflow que contiene texto de lectura)
            paragraph_text = ""
            paragraph_el = self.browser.page.query_selector(".overflow-y-auto, div[class*='text-justify'], div.w-full.h-100")
            if paragraph_el:
                paragraph_text = paragraph_el.inner_text().strip()
            
            has_sentence_structure = any("[___]" in row['label'] for row in rows_data)
            
            if is_true_false and paragraph_text:
                # TRUE/FALSE con párrafo de texto - SIN imagen
                prompt = f"""Texto: {paragraph_text}

Afirmaciones:{options_text}

Basándote en el texto, responde TRUE o FALSE:
1. TRUE/FALSE
2. TRUE/FALSE
..."""
                # Sin imagen, solo texto
                response = self.solver.model.generate_content(prompt)
            elif is_true_false and has_image:
                # TRUE/FALSE con imagen
                prompt = f"""Afirmaciones:{options_text}

Mira la imagen. Responde TRUE o FALSE:
1. TRUE/FALSE
2. TRUE/FALSE
..."""
                image_part = {
                    "mime_type": "image/png",
                    "data": __import__('base64').b64encode(screenshot).decode()
                }
                response = self.solver.model.generate_content([prompt, image_part])
            elif has_sentence_structure and not has_image:
                # Completar oraciones
                prompt = f"""Oraciones:{options_text}

Elige la opción correcta:
1. OPCIÓN
2. OPCIÓN
..."""
                response = self.solver.model.generate_content(prompt)
            else:
                # Matching con imagen
                prompt = f"""Filas:{options_text}

Elige la opción correcta:
1. OPCIÓN
2. OPCIÓN
..."""
                image_part = {
                    "mime_type": "image/png",
                    "data": __import__('base64').b64encode(screenshot).decode()
                }
                response = self.solver.model.generate_content([prompt, image_part])
            
            result_text = response.text.strip()
            print(f"[DEBUG] Respuesta de Gemini:\n{result_text}")
            
            # 5. Parsear respuestas y hacer clicks
            import re
            
            # Función para normalizar texto
            def normalize(text):
                return text.upper().replace("´", "'").replace("`", "'").replace("*", "").strip()
            
            clicked = 0
            for line in result_text.split("\n"):
                # Buscar varios patrones:
                # Patrón 1: "1. **TRUE** (explicación)" o "1. TRUE"
                # Patrón 2: "1. Label: → Opción"
                
                match = re.search(r'(\d+)\.\s*\*?\*?([A-Za-z\s/\']+)\*?\*?', line)
                if match:
                    row_num = int(match.group(1)) - 1
                    answer = normalize(match.group(2))
                    
                    if row_num < len(rows_data):
                        row = rows_data[row_num]
                        
                        # Buscar match en las opciones
                        matched_opt = None
                        
                        # PRIMERO: Normalizar respuesta de T/F
                        if answer == "TRUE":
                            # Buscar si hay opción 'T'
                            if any(normalize(o['text']) == 'T' for o in row['options']):
                                answer = "T"
                        elif answer == "FALSE":
                            if any(normalize(o['text']) == 'F' for o in row['options']):
                                answer = "F"
                        
                        # PRIMERO: match exacto
                        for opt in row['options']:
                            opt_norm = normalize(opt['text'])
                            if opt_norm == answer:
                                matched_opt = opt
                                break
                        
                        # SEGUNDO: contención
                        if not matched_opt:
                            for opt in row['options']:
                                opt_norm = normalize(opt['text'])
                                if answer in opt_norm or opt_norm in answer:
                                    matched_opt = opt
                                    break
                        
                        if matched_opt:
                            print(f"[INFO] {row['label'][:30]}... → {matched_opt['text']}")
                            try:
                                matched_opt['element'].click()
                                clicked += 1
                                self.browser.sleep(0.2)
                            except:
                                try:
                                    self.browser.page.click(f"button.activar-btn:has-text('{matched_opt['text']}')", timeout=2000)
                                    clicked += 1
                                except:
                                    print(f"[WARNING] No se pudo click en {matched_opt['text']}")
            
            print(f"[INFO] Clicks realizados: {clicked}")
            
            self.browser.sleep(0.5)
            
            # 6. Click en CHECK
            self._click_check_button()
            self.browser.sleep(1)
            
            # 7. Click en OK del modal
            self._click_ok_modal()
            
            self.questions_answered += 1
            print(f"[SUCCESS] Pregunta {self.questions_answered} (matching) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en matching buttons: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_image_drag_match(self, question_text: str) -> bool:
        """Resuelve preguntas de matching imágenes con opciones."""
        try:
            print("[INFO] Resolviendo pregunta de matching imágenes...")
            
            # 1. Obtener zonas pendientes (botones "Waiting answer")
            zone_elements = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            
            if not zone_elements:
                print("[WARNING] No hay zonas pendientes")
                # Verificar si ya está todo lleno antes de hacer CHECK
                all_filled = self.browser.page.query_selector("button:has-text('Waiting answer')") is None
                if all_filled:
                    self._click_check_button()
                    self.browser.sleep(0.5)
                    self._click_ok_modal()
                    self.questions_answered += 1
                    return True
                return False
            
            # 2. Contar imágenes y EXTRAER ETIQUETAS DE TEXTO (para matching sin imágenes)
            images = self.browser.page.query_selector_all("img[alt='Descripción de la imagen']")
            num_images = len(images)
            
            # Extraer texto asociado a cada "Waiting answer"
            zone_labels = []
            for i, btn in enumerate(zone_elements):
                # Usar JS para buscar el contenedor padre (tarjeta) y extraer su texto
                try:
                    label = btn.evaluate("""el => {
                        // Buscar contenedor padre común (tarjeta con sombra/borde)
                        let container = el.closest('.shadow-sm') || el.closest('.border-gray-100') || el.parentElement.parentElement;
                        if (container) {
                            // Obtener texto clones y limpiar
                            let clone = container.cloneNode(true);
                            // Remover el botón de waiting para que no ensucie el texto
                            let btns = clone.querySelectorAll('button');
                            btns.forEach(b => b.remove());
                            return clone.innerText.trim().replace(/\\n/g, ' ').replace(/_+/g, '____');
                        }
                        return '';
                    }""")
                except:
                    label = ""
                
                if not label:
                    label = f"Item {i+1} (ver imagen)"
                
                print(f"[INFO] Zona {i+1}: {label[:50]}...")
                zone_labels.append(label)
                
            print(f"[INFO] {num_images} imágenes encontradas. {len(zone_labels)} zonas de respuesta.")
            
            # 3. Obtener opciones disponibles
            available_options = []
            option_containers = self.browser.page.query_selector_all(".flex.flex-wrap.gap-2 > div, button span")
            
            for container in option_containers:
                btn = container.query_selector("button") if container.query_selector("button") else container
                if btn:
                    text = btn.inner_text().strip()
                    if text and len(text) > 2 and "Waiting" not in text:
                        # Evitar duplicados
                        if not any(o['text'] == text for o in available_options):
                            available_options.append({"text": text, "element": btn})
            
            if not available_options:
                print("[WARNING] No hay opciones disponibles")
                return False
            
            print(f"[INFO] Opciones: {[o['text'] for o in available_options]}")
            
            # 4. Tomar screenshot y hacer UNA llamada a Gemini
            # Usar full_page=True para asegurar que se vean todas las imágenes, incluso con scroll
            screenshot = self.browser.screenshot(full_page=True)
            
            options_str = ", ".join([o['text'] for o in available_options])
            
            # Construir texto de items para el prompt
            items_text = ""
            for i, label in enumerate(zone_labels):
                items_text += f"{i+1}. {label}\n"
            
            prompt = f"""Pregunta: {question_text}

Hay {len(zone_elements)} items para completar/relacionar (ordenados de arriba hacia abajo).
ITEMS/PREGUNTAS:
{items_text}

OPCIONES DISPONIBLES: {options_str}

Instrucciones:
1. Mira el texto de cada item y la imagen (si hay).
2. Asigna la opción correcta de la lista de opciones disponibles.
3. Responde en orden numérico.

Respuesta:
1. OPCIÓN
2. OPCIÓN
3. OPCIÓN
..."""
            
            image_part = {
                "mime_type": "image/png",
                "data": __import__('base64').b64encode(screenshot).decode()
            }
            
            response = self.solver.model.generate_content([prompt, image_part])
            result = response.text.strip()
            print(f"[DEBUG] Gemini responde:\n{result}")
            
            # 5. Parsear respuestas y hacer clicks
            import re
            lines = result.split("\n")
            clicks_done = 0
            
            for line in lines:
                match = re.search(r'(\d+)\.\s*(.+)', line)
                if match:
                    idx = int(match.group(1)) - 1
                    answer = match.group(2).strip().lower()
                    
                    if idx < len(zone_elements):
                        # Buscar la MEJOR coincidencia (Exacta > Contenida más larga)
                        best_match = None
                        best_score = -1
                        
                        for opt in available_options:
                            opt_lower = opt['text'].lower()
                            current_score = -1
                            
                            # 1. Match Exacto (Prioridad Máxima 1000)
                            if opt_lower == answer:
                                current_score = 1000
                            
                            # 2. Contenido (Score = longitud, para preferir 'plural countable' sobre 'countable')
                            elif opt_lower in answer:
                                current_score = len(opt_lower)
                            elif answer in opt_lower:
                                current_score = len(answer)
                            
                            if current_score > best_score:
                                best_score = current_score
                                best_match = opt
                        
                        if best_match:
                            print(f"[INFO] Imagen {idx+1} → {best_match['text']} (Score: {best_score})")
                            try:
                                best_match['element'].click()
                                clicks_done += 1
                                self.browser.sleep(0.3)
                            except:
                                try:
                                    self.browser.page.click(f"button:has-text('{best_match['text']}')", timeout=2000)
                                    clicks_done += 1
                                except:
                                    print(f"[WARNING] No se pudo click en {best_match['text']}")
                                break
            
            print(f"[INFO] Clicks realizados: {clicks_done}")
            
            # 6. Verificar si quedan zonas pendientes antes de hacer CHECK
            self.browser.sleep(1.0) # Esperar a que la UI se actualice
            remaining_waiting = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            
            if len(remaining_waiting) == 0 and clicks_done > 0:
                self.browser.sleep(0.5)
                self._click_check_button()
                self.browser.sleep(0.5)
                self._click_ok_modal()
                
                self.questions_answered += 1
                print(f"[SUCCESS] Pregunta {self.questions_answered} (image drag) respondida")
                self.browser.sleep(self.delay)
                return True
            else:
                if len(remaining_waiting) > 0:
                    print(f"[WARNING] Aún quedan {len(remaining_waiting)} zonas 'Waiting answer'. No se hará CHECK.")
                else:
                    print("[WARNING] No se realizaron clicks.")
                return False
            

            
        except Exception as e:
            print(f"[ERROR] Error en image drag match: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_image_with_options(self, question_text: str) -> bool:
        """Resuelve preguntas con imagen + opciones simples (Male, Female, Both, etc.)."""
        try:
            print("[INFO] Resolviendo pregunta de imagen con opciones simples...")
            
            # 1. Tomar screenshot
            screenshot = self.browser.screenshot()
            
            # 2. Obtener todas las opciones disponibles
            buttons = self.browser.page.query_selector_all("button.rounded-xl, button.border-gray-300")
            options = []
            for btn in buttons:
                text = btn.inner_text().strip()
                if text and len(text) > 0 and "CHECK" not in text.upper() and "SKIP" not in text.upper():
                    options.append({"text": text, "element": btn})
            
            if not options:
                print("[WARNING] No se encontraron opciones")
                return False
            
            options_str = ", ".join([opt['text'] for opt in options])
            print(f"[INFO] Opciones encontradas: {options_str}")
            
            # 3. Crear prompt para Gemini
            prompt = f"""Analiza esta captura de pantalla.

PREGUNTA: {question_text}

OPCIONES DISPONIBLES: {options_str}

Mira la imagen y lee el texto del anuncio cuidadosamente.
Responde SOLO con la opción correcta exacta, nada más:"""
            
            image_part = {
                "mime_type": "image/png",
                "data": __import__('base64').b64encode(screenshot).decode()
            }
            
            response = self.solver.model.generate_content([prompt, image_part])
            answer = response.text.strip().split('\n')[0].strip()
            print(f"[DEBUG] Gemini responde: {answer}")
            
            # 4. Buscar y hacer click en la opción correcta
            matched = None
            for opt in options:
                if (answer.lower() in opt['text'].lower() or 
                    opt['text'].lower() in answer.lower()):
                    matched = opt
                    break
            
            if matched:
                print(f"[INFO] Seleccionando: '{matched['text']}'")
                matched['element'].click()
                self.browser.sleep(0.3)
                
                # Click en CHECK
                self._click_check_button()
                self.browser.sleep(0.5)
                self._click_ok_modal()
                
                self.questions_answered += 1
                print(f"[SUCCESS] Pregunta {self.questions_answered} (image with options) respondida")
                self.browser.sleep(self.delay)
                return True
            else:
                print(f"[WARNING] No se encontró match para '{answer}'")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error en image with options: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_matching_requirements(self, question_text: str) -> bool:
        """Resuelve preguntas de matching de vacantes con requisitos."""
        try:
            print("[INFO] Resolviendo matching de vacantes con requisitos...")
            
            # 1. Tomar screenshot
            screenshot = self.browser.screenshot()
            
            # 2. Buscar todas las secciones con formato "Label:" seguido de botones
            # Los contenedores son divs que tienen un span con ":" y luego botones
            all_sections = self.browser.page.query_selector_all("div.flex.flex-col.gap-2")
            
            rows = []
            for section in all_sections:
                # Buscar el texto del label (Manager:, Accountant:, etc.)
                section_text = section.inner_text()
                if ":" in section_text and ("Manager" in section_text or "Accountant" in section_text or 
                    "Cleaning" in section_text or "Assistant" in section_text or "Staff" in section_text):
                    
                    # El label es la primera línea
                    label = section_text.split(":")[0].strip()
                    
                    # Buscar botones
                    btns = section.query_selector_all("button")
                    if btns:
                        btn_data = []
                        for btn in btns:
                            txt = btn.inner_text().strip()
                            if txt:
                                btn_data.append((txt, btn))
                        if btn_data:
                            rows.append({"label": label, "buttons": btn_data})
            
            if not rows:
                print("[WARNING] No se encontraron filas, usando fallback con screenshot...")
                # Fallback: usar análisis visual puro
                return self._solve_with_screenshot(question_text)
            
            print(f"[INFO] Filas: {[r['label'] for r in rows]}")
            
            # 3. Crear prompt para Gemini con la imagen
            all_options = set()
            for r in rows:
                for btn_txt, _ in r['buttons']:
                    all_options.add(btn_txt)
            
            prompt = f"""Mira este anuncio de trabajo y responde:

{question_text}

PUESTOS: {', '.join([r['label'] for r in rows])}
OPCIONES DE REQUISITOS: {', '.join(all_options)}

Lee cuidadosamente el anuncio y busca la calificación/requisito para cada puesto.
En la imagen dice algo como "Qualification: ..." al lado de cada puesto.

Responde con una línea por puesto en formato "Puesto: Requisito":"""
            
            image_part = {
                "mime_type": "image/png",
                "data": __import__('base64').b64encode(screenshot).decode()
            }
            
            response = self.solver.model.generate_content([prompt, image_part])
            result = response.text.strip()
            print(f"[DEBUG] Gemini:\n{result}")
            
            # 4. Parsear y hacer clicks rápidamente
            import re
            clicked = 0
            for line in result.split("\n"):
                match = re.search(r'(.+?):\s*(.+)', line)
                if match:
                    job = match.group(1).strip()
                    req = match.group(2).strip()
                    
                    for row in rows:
                        if job.lower() in row['label'].lower() or row['label'].lower() in job.lower():
                            for btn_text, btn_el in row['buttons']:
                                if (req.lower() in btn_text.lower() or 
                                    btn_text.lower() in req.lower() or
                                    req.replace(" ", "").lower() in btn_text.replace(" ", "").lower()):
                                    print(f"[INFO] {row['label']} -> {btn_text}")
                                    try:
                                        btn_el.click()
                                        clicked += 1
                                        self.browser.sleep(0.2)  # Más rápido
                                    except:
                                        pass
                                    break
                            break
            
            print(f"[INFO] Seleccionados: {clicked} botones")
            
            # 5. CHECK
            self.browser.sleep(0.3)
            self._click_check_button()
            self.browser.sleep(0.5)
            self._click_ok_modal()
            
            self.questions_answered += 1
            print(f"[SUCCESS] Pregunta {self.questions_answered} (matching requirements) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en matching requirements: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _solve_with_screenshot(self, question_text: str) -> bool:
        """Resuelve pregunta desconocida usando screenshot + HTML + análisis visual."""
        try:
            print("[INFO] Tipo de pregunta desconocido, usando análisis visual + HTML...")
            
            # 1. Tomar screenshot
            screenshot = self.browser.screenshot()
            print("[INFO] Screenshot capturado")
            
            # 2. Capturar HTML de la página (área principal de contenido)
            html_content = self.browser.get_page_html("main") or self.browser.get_page_html("body")
            print(f"[INFO] HTML capturado ({len(html_content)} caracteres)")
            
            # 3. Analizar con Gemini (imagen + HTML)
            result = self.solver.analyze_unknown_question(screenshot, html_content, question_text)
            
            print(f"[INFO] Tipo detectado: {result.get('question_type', 'N/A')}")
            print(f"[INFO] Descripción: {result.get('description', 'N/A')}")
            print(f"[INFO] Estrategia: {result.get('strategy', 'N/A')}")
            
            # 4. Intentar resolver según la respuesta
            answer = result.get("answer")
            if answer:
                print(f"[INFO] Respuesta identificada: {answer}")
                
                # Intentar diferentes estrategias de interacción
                success = False
                
                # Estrategia 1: Click directo en texto
                try:
                    self.browser.page.get_by_text(answer, exact=False).first.click(timeout=3000)
                    success = True
                    print("[INFO] Click directo exitoso")
                except:
                    pass
                
                # Estrategia 2: Usar selectores proporcionados por Gemini
                if not success and result.get("selectors"):
                    for selector in result["selectors"]:
                        try:
                            if selector.startswith(".") or selector.startswith("#"):
                                self.browser.page.click(selector, timeout=2000)
                                success = True
                                print(f"[INFO] Click en selector {selector} exitoso")
                                break
                            else:
                                # Asumir que es texto
                                self.browser.page.get_by_text(selector, exact=False).first.click(timeout=2000)
                                success = True
                                print(f"[INFO] Click en texto '{selector}' exitoso")
                                break
                        except:
                            continue
                
                # Estrategia 3: Buscar en botones
                if not success:
                    buttons = self.browser.page.query_selector_all("button")
                    for btn in buttons:
                        try:
                            btn_text = btn.inner_text().strip().lower()
                            if answer.lower() in btn_text or btn_text in answer.lower():
                                btn.click()
                                success = True
                                print(f"[INFO] Click en botón '{btn_text}' exitoso")
                                break
                        except:
                            continue
                
                if success:
                    self.browser.sleep(0.5)
                    self._click_check_button()
                    self.browser.sleep(1)
                    self._click_ok_modal()
                    self.questions_answered += 1
                    return True
            
            # Si no pudimos resolver automáticamente, mostrar la información
            print("[WARNING] No se pudo resolver automáticamente. Información obtenida:")
            print(f"  - Tipo: {result.get('question_type')}")
            print(f"  - Respuesta sugerida: {result.get('answer')}")
            print(f"  - Acciones: {result.get('actions')}")
            
            return False
            
        except Exception as e:
            print(f"[ERROR] Error en análisis visual + HTML: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _click_answer_option(self, answer_text: str) -> bool:
        """Encuentra y hace click en la opción de respuesta."""
        try:
            # Limpiar el texto de respuesta
            answer_clean = answer_text.strip().lower()
            
            # Buscar todos los botones de opción
            buttons = self.browser.page.query_selector_all("button")
            
            best_match = None
            best_score = 0
            
            for button in buttons:
                button_text = button.inner_text().strip().lower()
                
                # Ignorar botones de navegación
                if button_text in ["check", "skip", "next", "continue", "back"]:
                    continue
                
                # Verificar coincidencia
                if answer_clean in button_text or button_text in answer_clean:
                    print(f"[INFO] Coincidencia encontrada: '{button_text}'")
                    button.click()
                    return True
                
                # Calcular similitud simple
                common_words = set(answer_clean.split()) & set(button_text.split())
                score = len(common_words)
                
                if score > best_score:
                    best_score = score
                    best_match = button
            
            # Si no hay coincidencia exacta, usar la mejor aproximación
            if best_match and best_score > 0:
                print(f"[INFO] Usando mejor aproximación (score: {best_score})")
                best_match.click()
                return True
            
            # Último intento: buscar por texto parcial con Playwright
            try:
                # Tomar las primeras palabras de la respuesta
                first_words = " ".join(answer_clean.split()[:3])
                self.browser.page.get_by_text(first_words, exact=False).first.click()
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"[ERROR] Error haciendo click en opción: {e}")
            return False
    
    def _click_check_button(self) -> bool:
        """Hace click en el botón CHECK."""
        try:
            # Buscar botón CHECK
            check_selectors = [
                "button:has-text('CHECK')",
                "button:has-text('Check')",
                ".check-button",
                "button.bg-green-500",
                "button.bg-teal-500"
            ]
            
            for selector in check_selectors:
                try:
                    if self.browser.page.locator(selector).is_visible(timeout=1000):
                        self.browser.page.locator(selector).click()
                        print("[INFO] Click en CHECK")
                        return True
                except:
                    continue
            
            # Intento directo
            try:
                self.browser.page.get_by_text("CHECK", exact=True).click()
                return True
            except:
                pass
            
            return False
            
        except Exception as e:
            print(f"[ERROR] Error haciendo click en CHECK: {e}")
            return False
    
    def _click_ok_modal(self) -> bool:
        """Hace click en el botón OK del modal de confirmación (SweetAlert2)."""
        try:
            # Esperar un poco a que aparezca el modal
            self.browser.sleep(0.5)
            
            # Intentar diferentes selectores para el modal
            ok_selectors = [
                "button.swal2-confirm",
                ".swal2-confirm",
                "button:has-text('OK')",
                "button:has-text('Continue')",
                ".swal2-actions button",
            ]
            
            for selector in ok_selectors:
                try:
                    if self.browser.page.locator(selector).is_visible(timeout=2000):
                        self.browser.page.locator(selector).click()
                        print("[INFO] Click en OK del modal")
                        self.browser.sleep(0.5)
                        return True
                except:
                    continue
            
            return False
            
        except Exception as e:
            print(f"[DEBUG] Modal no detectado: {e}")
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
    
    def _solve_text_match(self, question_text: str) -> bool:
        """
        Resuelve preguntas de tipo 'MATCH THE SENTENCE WITH THE RIGHT OPTION'.
        Extrae texto de items y opciones, y usa lógica 1-a-1.
        """
        try:
            print("[INFO] Resolviendo pregunta de MATCHING DE TEXTO (1-a-1)...")
            
            # 1. Encontrar zonas de 'Waiting answer'
            zone_elements = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            if not zone_elements:
                print("[WARNING] No se encontraron zonas drop")
                return False
            
            # 2. Extraer etiquetas de texto (contexto)
            # Usamos query selector específico para la estructura dada en el ejemplo
            zone_labels = []
            for i, btn in enumerate(zone_elements):
                # Buscar el h2 hermano o en el contenedor
                try:
                    label = btn.evaluate("""el => {
                        let container = el.closest('.flex-col');
                        if (container) {
                             let h2 = container.querySelector('h2');
                             if (h2) return h2.innerText.trim();
                        }
                        return '';
                    }""")
                    
                    # Si falla selector simple, usar closest más amplio
                    if not label:
                        label = btn.evaluate("""el => {
                            let container = el.closest('.shadow-sm') || el.closest('.border-gray-100') || el.parentElement.parentElement;
                            if (container) {
                                let clone = container.cloneNode(true);
                                let btns = clone.querySelectorAll('button');
                                btns.forEach(b => b.remove());
                                return clone.innerText.trim().replace(/\\n/g, ' ').replace(/_+/g, '____');
                            }
                            return '';
                        }""")
                    
                except:
                    label = ""
                
                if not label:
                    label = f"Item {i+1}"
                
                print(f"[INFO] Item {i+1}: {label}")
                zone_labels.append(label)
            
            # 3. Obtener opciones disponibles
            available_options = []
            option_containers = self.browser.page.query_selector_all(".flex.flex-wrap.gap-2 > div, button span")
            
            for container in option_containers:
                btn = container.query_selector("button") if container.query_selector("button") else container
                # En algunos casos el span es hijo directo
                if not btn and container.evaluate("el => el.tagName === 'BUTTON'"):
                     btn = container
                
                # Si sigue sin encontrarse, buscar padre botón
                if not btn:
                     try:
                        btn = container.query_selector("xpath=ancestor::button")
                     except:
                        pass

                if btn:
                    text = btn.inner_text().strip()
                    if text and len(text) > 2 and "Waiting" not in text:
                         # Evitar duplicados? No, aquí necesitamos todos los botones físicos aunque tengan mismo texto
                         if not any(o['element'] == btn for o in available_options):
                             available_options.append({"text": text, "element": btn})

            options_str = ", ".join([o['text'] for o in available_options])
            print(f"[INFO] Opciones encontradas: {options_str}")
            
            # 4. Construir Prompt
            items_text = ""
            for i, label in enumerate(zone_labels):
                items_text += f"{i+1}. {label}\n"
            
            prompt = f"""Pregunta de Emparejamiento: {question_text}

ITEMS:
{items_text}

OPCIONES DISPONIBLES: {options_str}

Instrucciones:
1. Asigna UNA opción a cada item.
2. Cada opción debe usarse EXACTAMENTE UNA VEZ (relación 1-a-1).
3. Responde en el formato: "1. OPCIÓN"
4. Fíjate bien en diferencias sutiles (ej: 'plural countable' vs 'countable').

Respuesta:"""

            # 5. Consultar a Gemini
            response = self.solver.model.generate_content(prompt)
            result = response.text.strip()
            print(f"[DEBUG] Gemini responde:\n{result}")
            
            # 6. Parsear y Ejecutar
            import re
            lines = result.split("\n")
            
            used_indices = set() # Trackear qué opciones (por índice) ya usamos
            
            clicks_done = 0
            
            for line in lines:
                match = re.search(r'(\d+)\.\s*(.+)', line)
                if match:
                    q_idx = int(match.group(1)) - 1
                    answer = match.group(2).strip().lower()
                    
                    if q_idx < len(zone_elements):
                        # Buscar la MEJOR opción DISPONIBLE
                        best_match_idx = -1
                        best_score = -1
                        
                        for opt_idx, opt in enumerate(available_options):
                            if opt_idx in used_indices: continue # Skip if already used

                            opt_lower = opt['text'].strip().lower()
                            current_score = -1
                            
                            # Prioridad 1: Exacto
                            if opt_lower == answer:
                                current_score = 1000
                            # Prioridad 2: Contenido
                            elif opt_lower in answer:
                                current_score = len(opt_lower)
                            elif answer in opt_lower:
                                current_score = len(answer)
                            
                            if current_score > best_score:
                                best_score = current_score
                                best_match_idx = opt_idx
                        
                        if best_match_idx != -1:
                            best_match = available_options[best_match_idx]
                            print(f"[INFO] Item {q_idx+1} → {best_match['text']} (Score: {best_score})")
                            
                            # Click
                            try:
                                best_match['element'].click()
                                clicks_done += 1
                                used_indices.add(best_match_idx) # Marcar como usada
                                self.browser.sleep(0.3)
                            except:
                                print(f"[WARNING] Falló click en {best_match['text']}")
            
            print(f"[INFO] Clicks realizados: {clicks_done}")
            
            # Verificar finalización
            remaining = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            if len(remaining) == 0 and clicks_done > 0:
                 self.browser.sleep(0.5)
                 self._click_check_button()
            
            return True

        except Exception as e:
            print(f"[ERROR] Error en text match: {e}")
            import traceback
            traceback.print_exc()
            return False

    def run(self):
        """Ejecuta el agente principal."""
        print("\n" + "="*60)
        print("   AGENTE DE EXÁMENES UTM - INICIANDO")
        print("="*60 + "\n")
        
        try:
            # 1. Login
            if not self.login():
                print("[FATAL] No se pudo iniciar sesión")
                return
            
            # 2. Buscar y resolver módulos incompletos
            while True:
                # Asegurarse de estar en el dashboard
                if "dashboard" not in self.browser.page.url and "autoaprendizaje" in self.browser.page.url:
                    # Navegar al dashboard si es necesario
                    pass
                
                # Buscar módulo incompleto
                module = self.find_incomplete_module()
                
                if not module:
                    print("[INFO] ¡Todos los módulos están completos!")
                    break
                
                self.current_module = module
                
                # Buscar actividad incompleta
                activity = self.find_incomplete_activity(module["element"])
                
                if not activity:
                    print(f"[INFO] Módulo {module['title']} no tiene actividades incompletas de las seleccionadas")
                    continue
                
                self.current_activity = activity
                
                # Iniciar actividad
                if not self.click_activity_and_start(activity):
                    print("[ERROR] No se pudo iniciar la actividad")
                    continue
                
                # Esperar a que cargue la primera pregunta
                self.browser.sleep(2)
                
                # Resolver todas las preguntas de la actividad
                while not self.is_activity_complete():
                    if not self.solve_current_question():
                        print("[WARNING] Problema resolviendo pregunta, intentando continuar...")
                        self.browser.sleep(2)
                    
                    # Verificar si hay más preguntas
                    if not self.has_next_question():
                        break
                    
                    self.browser.sleep(1)
                
                print(f"[SUCCESS] Actividad '{activity['name']}' completada!")
                
                # Volver al dashboard
                self.browser.sleep(2)
                try:
                    self.browser.page.go_back()
                    self.browser.sleep(2)
                except:
                    pass
            
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
            # No cerrar el navegador para que el usuario pueda ver el resultado
            print("[INFO] El navegador permanecerá abierto")
            input("Presiona Enter para cerrar el navegador...")
            self.browser.close()


if __name__ == "__main__":
    agent = ExamAgent()
    agent.run()
