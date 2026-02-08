import time
import re
import base64
import random
import traceback
import json
import os
import hashlib
from typing import List, Dict, Any, Optional
from playwright.sync_api import Page, Locator
from selectors import SELECTORS

class QuestionSolvers:
    """Handles solving all question types for the exam bot."""
    
    def __init__(self, browser, solver, config, delay=2):
        """
        Initialize the QuestionSolvers.
        
        Args:
            browser: BrowserController instance
            solver: GeminiSolver instance
            config: Config dictionary with credentials
            delay: Delay in seconds between actions
        """
        self.browser = browser
        self.solver = solver
        self.config = config
        self.delay = 1

        self.knowledge_file = "learned_answers.json"
        self.knowledge = self._load_knowledge()

    def _load_knowledge(self) -> Dict:
        if os.path.exists(self.knowledge_file):
            try:
                with open(self.knowledge_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: return {}
        return {}

    def _save_knowledge(self):
        try:
            with open(self.knowledge_file, 'w', encoding='utf-8') as f:
                json.dump(self.knowledge, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[ERROR] Saving knowledge: {e}")

    def _get_question_signature(self, text: str, extra_context: str = "") -> str:
        """Genera un hash único para el texto de la pregunta normalizado, opcionalmente con contexto extra."""
        normalized_q = re.sub(r'\s+', ' ', text.strip().upper())
        normalized_ctx = re.sub(r'\s+', ' ', extra_context.strip().upper())
        combined = f"{normalized_q}|{normalized_ctx}"
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def learn_from_mistake(self, question_text: str, extra_context: str = ""):
        """
        Intenta detectar el modal de error, extraer la respuesta correcta y guardarla.
        """
        try:
            # Check for error icon/modal
            error_icon = self.browser.page.locator(".swal2-icon-error")
            if error_icon.is_visible(timeout=2000):
                print("[LEARNING] Detectado error. Intentando aprender...")
                
                # Get the content
                content_loc = self.browser.page.locator("#swal2-html-container")
                if content_loc.is_visible():
                    # Intento 1: Parsing por texto (más robusto que HTML)
                    text_content = content_loc.inner_text()
                    print(f"[DEBUG] Modal text: {text_content!r}")
                    
                    answers_list = []
                    if "Correct Answer:" in text_content:
                        # "Correct Answer: \nBasketball\nhorses..."
                        # Split by "Correct Answer:" and take the rest
                        raw_answers = text_content.split("Correct Answer:", 1)[1]
                        # Split by newlines
                        answers_list = [
                            line.strip() 
                            for line in raw_answers.split("\n") 
                            if line.strip()
                        ]
                    else:
                        # Fallback to HTML parsing if text format differs
                        html_content = content_loc.inner_html()
                        print(f"[DEBUG] Modal HTML: {html_content!r}")
                        parts = html_content.split("</p>")
                        if len(parts) > 1:
                            raw_answers = parts[1]
                            answers_list = [
                                ans.strip() 
                                for ans in raw_answers.split("<br>") 
                                if ans.strip()
                            ]

                    if answers_list:
                        sig = self._get_question_signature(question_text, extra_context)
                        self.knowledge[sig] = answers_list
                        self._save_knowledge()
                        print(f"[LEARNING] Aprendido para '{sig}': {answers_list}")
                        return True
                    else:
                        print("[WARNING] No se pudieron extraer respuestas del modal")
        except Exception as e:
            print(f"[ERROR] Learning failed: {e}")
        return False

    def try_solve_with_knowledge(self, question_text: str, extra_context: str = "") -> Optional[List[str]]:
        """Intenta resolver usando conocimiento previo guardado."""
        sig = self._get_question_signature(question_text, extra_context)
        if sig in self.knowledge:
            answers = self.knowledge[sig]
            print(f"[KNOWLEDGE] Aplicando respuesta aprendida: {answers}")
            # Logic to apply answers depends on the question type.
            # For now, we return the answers so the caller can use them?
            # Or we implement a generic clicker here?
            # Most learned answers are just text to click.
            
            try:
                # Generic attempt to click buttons with these texts in order
                # This works well for "Complete sentences" and "Order" types
                
                # We need to target buttons.
                # Assuming sequential blocks or just finding buttons by text.
                
                # Strategy: Identify clickable buttons matching the text.
                # Since 'answers' is a sequence, we might need to be careful about order.
                
                # Global generic approach:
                # Find all logical groups/rows? 
                # Or just search and click?
                pass # Caller should handle correct application if generic fails?
                # Let's try a generic sequential click approach
                
                # Re-reading logic: The user wants to use this.
                # Let's implement a generic row-based clicker if possible
                pass
            except: pass
            
            return answers # Return the list for the specific solver to use
        return None
    
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
        """Hace click en el botón OK del modal de confirmación (SweetAlert2). Intenta varias veces."""
        try:
            # Intentar clickear hasta 5 veces (aprox 3-4 segundos)
            for i in range(5):
                # Selectores para el botón OK
                ok_selectors = [
                    "button.swal2-confirm",
                    ".swal2-confirm",
                    "button:has-text('OK')",
                    "button:has-text('Continue')",
                    ".swal2-actions button",
                ]
                
                found = False
                for selector in ok_selectors:
                    try:
                        if self.browser.page.locator(selector).is_visible():
                            # Forzar click si es necesario
                            self.browser.page.locator(selector).click(force=True)
                            print(f"[INFO] Click en OK del modal ({selector})")
                            found = True
                            self.browser.sleep(0.5)
                            break
                    except:
                        continue
                
                # Verificar si el contenedor del modal sigue visible
                still_visible = False
                try:
                    # swal2-container suele ser el wrapper overlay
                    if self.browser.page.locator(".swal2-container").is_visible():
                         still_visible = True
                except: pass
                
                if found and not still_visible:
                    return True
                
                # Si no encontramos botón pero tampoco hay modal visible (y ya esperamos un poco), asumimos éxito/ausencia
                if not found and not still_visible and i > 0:
                     return True

                self.browser.sleep(0.5)
            
            return False
            
        except Exception as e:
            print(f"[DEBUG] Error en _click_ok_modal: {e}")
            # Si falla, no bloqueamos el flujo
            return True

    def solve_multiple_choice(self, question_text: str) -> bool:
        """Resuelve preguntas de opción múltiple con mejor extracción de texto de lectura."""
        try:
            # --- HARDCODED ANSWERS START ---
            if "DO MOST PEOPLE CELEBRATE THEIR BIRTHDAY WITH A PARTY" in question_text.upper():
                print("[OVERRIDE] Detectada pregunta de Birthday Party. Aplicando respuesta hardcoded.")
                try:
                    # Buscar y clickear la respuesta correcta directamente
                    yes_btn = self.browser.page.get_by_text("Yes, they do.", exact=False)
                    if yes_btn.count() > 0:
                        yes_btn.first.click()
                        self.browser.sleep(0.3)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self._click_ok_modal()
                        print("[SUCCESS] Pregunta contestada via hardcode.")
                        return True
                except Exception as e:
                    print(f"[ERROR] Falló hardcode birthday: {e}")
            
            if "WHERE CAN I BUY CLOTHES FROM RECOGNIZED BRANDS" in question_text.upper():
                print("[OVERRIDE] Detectada pregunta de Clothes Brands. Aplicando respuesta hardcoded.")
                try:
                    # Buscar y clickear la respuesta correcta directamente
                    # Nota: El texto en la plataforma tiene un acento agudo ´ en vez de apóstrofe '
                    designers_btn = self.browser.page.get_by_text("Designers´shop", exact=False)
                    if designers_btn.count() > 0:
                        designers_btn.first.click()
                        self.browser.sleep(0.3)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self._click_ok_modal()
                        print("[SUCCESS] Pregunta contestada via hardcode.")
                        return True
                    else:
                        print("[WARNING] No se encontró el botón 'Designers´shop'")
                except Exception as e:
                    print(f"[ERROR] Falló hardcode clothes brands: {e}")
            
            if "I AM ___________" in question_text.upper():
                print("[OVERRIDE] Detectada pregunta 'I AM...'. Aplicando respuesta hardcoded.")
                try:
                    # Texto del botón tal cual aparece en las opciones (con error gramatical incluido si es el caso)
                    hurry_btn = self.browser.page.get_by_text("always is a hurry", exact=False)
                    if hurry_btn.count() > 0:
                        hurry_btn.first.click()
                        self.browser.sleep(0.3)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self._click_ok_modal()
                        print("[SUCCESS] Pregunta contestada via hardcode.")
                        return True
                    else:
                        print("[WARNING] No se encontró el botón 'always is a hurry'")
                except Exception as e:
                    print(f"[ERROR] Falló hardcode I AM: {e}")
            
            if "IN WHICH AD CAN YOU GET HELP INSTALLING SOME NEW SOFTWARE" in question_text.upper():
                print("[OVERRIDE] Detectada pregunta 'Ads Software'. Aplicando respuesta hardcoded.")
                try:
                    # Buscar y clickear la respuesta correcta "Ad A"
                    ad_a_btn = self.browser.page.get_by_text("Ad A", exact=True)
                    if ad_a_btn.count() > 0:
                        ad_a_btn.first.click()
                        self.browser.sleep(0.3)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self._click_ok_modal()
                        print("[SUCCESS] Pregunta contestada via hardcode.")
                        return True
                    else:
                        print("[WARNING] No se encontró el botón 'Ad A'")
                except Exception as e:
                    print(f"[ERROR] Falló hardcode Ads Software: {e}")
            
            if "READ THE AD. WHAT IS IT FOR?" in question_text.upper():
                print("[OVERRIDE] Detectada pregunta 'Product Sales'. Aplicando respuesta hardcoded.")
                try:
                    product_btn = self.browser.page.get_by_text("Product sales", exact=False)
                    if product_btn.count() > 0:
                        product_btn.first.click()
                        self.browser.sleep(0.3)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self._click_ok_modal()
                        print("[SUCCESS] Pregunta contestada via hardcode.")
                        return True
                    else:
                        print("[WARNING] No se encontró el botón 'Product sales'")
                except Exception as e:
                     print(f"[ERROR] Falló hardcode Product Sales: {e}")
            # --- HARDCODED ANSWERS END ---

            # ====== DETECTAR Y PROCESAR AUDIO (si existe) ======
            audio_element = self.browser.page.query_selector("audio")
            has_audio = audio_element is not None
            audio_answer_index = -1  # Índice de respuesta del audio (si se procesa)
            
            if has_audio:
                print("[INFO] 🎵 Audio detectado en pregunta de opción múltiple")
                try:
                    # Extraer opciones primero (las necesitamos para enviar a Gemini)
                    temp_options = []
                    cards = self.browser.page.query_selector_all(".cardCheck")
                    for card in cards:
                        button = card.query_selector("button")
                        if button:
                            option_text = button.inner_text().strip()
                            if option_text:
                                temp_options.append(option_text)
                    
                    if temp_options:
                        # Extraer la URL del audio
                        audio_url = audio_element.get_attribute("src")
                        if not audio_url:
                            source_element = audio_element.query_selector("source")
                            if source_element:
                                audio_url = source_element.get_attribute("src")
                        
                        if audio_url:
                            print(f"[INFO] URL de audio: {audio_url[:80]}...")
                            
                            # Descargar audio
                            if audio_url.startswith("blob:"):
                                print("[INFO] Convirtiendo blob URL a bytes...")
                                audio_base64 = self.browser.page.evaluate("""
                                    async (audioUrl) => {
                                        const response = await fetch(audioUrl);
                                        const blob = await response.blob();
                                        return new Promise((resolve) => {
                                            const reader = new FileReader();
                                            reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                            reader.readAsDataURL(blob);
                                        });
                                    }
                                """, audio_url)
                                import base64
                                audio_bytes = base64.b64decode(audio_base64)
                            else:
                                import requests
                                response = requests.get(audio_url, timeout=10)
                                audio_bytes = response.content
                            
                            print(f"[INFO] Audio descargado: {len(audio_bytes)} bytes")
                            
                            # Analizar con Gemini
                            result = self.solver.analyze_audio_question(audio_bytes, question_text, temp_options)
                            audio_answer_index = result.get("answer_index", -1)
                            
                            if audio_answer_index >= 0 and audio_answer_index < len(temp_options):
                                print(f"[INFO] ✅ Gemini sugiere (audio): {temp_options[audio_answer_index]}")
                            else:
                                print(f"[WARNING] Índice de audio inválido: {audio_answer_index}")
                                audio_answer_index = -1
                        else:
                            print("[WARNING] No se pudo extraer URL del audio")
                except Exception as e:
                    print(f"[WARNING] Error procesando audio: {e}")
                    print("[INFO] Continuando con flujo normal de multiple_choice...")
            
            # ====== FIN DE PROCESAMIENTO DE AUDIO ======

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
            
            # Extraer texto de lectura si existe (pasajes, cartas, menús, etc.)
            reading_text = ""
            try:
                # Método 1: Buscar contenedores de texto específicos
                reading_selectors = [
                    ".overflow-y-auto",           # Contenedor con scroll
                    ".text-justify",              # Texto justificado
                    ".bg-gray-50 .p-4",          # Fondo gris con padding
                    "[class*='text-justify']",    # Cualquier clase con text-justify
                    ".prose",                     # Contenedores de texto
                    ".reading-passage",           # Pasajes de lectura
                    "article",                    # Artículos
                    ".card-body",                 # Cuerpo de card
                    "div.p-4:not(.cardCheck)"     # Divs con padding que no sean opciones
                ]
                
                for selector in reading_selectors:
                    containers = self.browser.page.query_selector_all(selector)
                    for container in containers:
                        try:
                            # CRITICAL: Ignore hidden containers (prevent reading stale text)
                            if not container.is_visible():
                                continue

                            # Verificar que no sea un contenedor de opciones
                            is_option_container = container.evaluate("""el => {
                                return el.closest('.cardCheck') !== null || 
                                       el.querySelector('.cardCheck') !== null;
                            }""")
                            
                            if is_option_container:
                                continue
                            
                            text = container.inner_text().strip()
                            # Solo agregar textos significativos (más de 50 chars y no duplicados)
                            if len(text) > 50 and text not in reading_text:
                                reading_text += text + "\n\n"
                        except:
                            continue
                
                # Método 2: Si aún no hay texto, intentar extracción más agresiva
                # Método 2 Optimizado: Buscar cabeceras y párrafos grandes si falla lo anterior
                if len(reading_text) < 50:
                    potential_texts = self.browser.page.query_selector_all("h2, h3, h4, p.text-lg, p.font-medium")
                    for el in potential_texts:
                         try:
                             if not el.is_visible(): continue
                             t = el.inner_text().strip()
                             # Evitar texto de opciones
                             if len(t) > 30 and t not in reading_text:
                                 # Simple heuristic: don't include if it matches an option exactly
                                 if not any(o == t for o in options):
                                     reading_text += t + "\n"
                         except: pass
                            
            except Exception as e:
                print(f"[DEBUG] Error extrayendo texto: {e}")
            
            # Log del texto extraído (truncado)
            if reading_text:
                preview = reading_text[:200].replace('\n', ' ')
                print(f"[INFO] Texto de lectura extraído ({len(reading_text)} chars): {preview}...")

            # Extract Breadcrumbs (Book/Mod/Unit)
            breadcrumbs = ""
            try:
                bc_el = self.browser.page.query_selector("p.tracking-widest.uppercase")
                if bc_el:
                    breadcrumbs = bc_el.inner_text().strip()
            except: pass
            
            # Extract Question Counter (e.g. 8/9) to handle identical questions at different positions
            q_counter = ""
            try:
                # Based on user HTML: <span class="text-green-600 text-lg">8</span>...<span class="text-gray-400">9</span>
                # or finding the container closest to the breadcrumbs
                counter_el = self.browser.page.query_selector("div.flex-shrink-0.font-bold.text-gray-700")
                if counter_el:
                    q_counter = counter_el.inner_text().replace("\n", "").strip()
            except: pass

            # Include OPTIONS, BREADCRUMBS in the signature (REMOVED COUNTER for better generalization)
            options_text = " | ".join(options)
            combined_context = f"TITLE: {breadcrumbs} || TEXT: {reading_text[:50]}... || OPTIONS: {options_text}"
            
            # Full context for signature generation (uses hash)
            full_context_for_sig = f"TITLE: {breadcrumbs} || TEXT: {reading_text} || OPTIONS: {options_text}"

            print(f"[DEBUG] Context Signature Data: {combined_context}")
            
            print("[DEBUG] Step: Checking Knowledge Base...")
            known_answers = self.try_solve_with_knowledge(question_text, full_context_for_sig)
            
            if known_answers:
                 # Standard Multiple Choice usually has one answer in the list
                 target_ans = known_answers[0].replace("´", "'").replace("`", "'").strip().upper()
                 print(f"[INFO] Buscando respuesta aprendida (con contexto): '{target_ans}'")
                 
                 found_idx = -1
                 # 1. Exact match
                 for i, opt in enumerate(options):
                     if opt.upper().replace("´", "'").replace("`", "'").strip() == target_ans:
                         found_idx = i
                         break
                 
                 # 2. Containment match
                 if found_idx == -1:
                     for i, opt in enumerate(options):
                         opt_norm = opt.upper().replace("´", "'").replace("`", "'").strip()
                         if target_ans in opt_norm or opt_norm in target_ans:
                             found_idx = i
                             break
                 
                 if found_idx != -1:
                     print(f"[INFO] Encontrado match aprendido en índice {found_idx}")
                     option_elements[found_idx].click()
                     self.browser.sleep(0.3)
                     self._click_check_button()
                     self.browser.sleep(1.0)
                     # Learn again using the SAME context (text + options)
                     self.learn_from_mistake(question_text, full_context_for_sig) 
                     self._click_ok_modal()
                     print("[SUCCESS] Pregunta contestada via knowledge.")
                     self.browser.sleep(self.delay)
                     return True
                 else:
                     print(f"[WARNING] No se encontró la opción aprendida '{target_ans}' entre {options}")
            
            print("[DEBUG] Step: Knowledge check finished. Proceeding to Gemini...")
            
            # Verificar si hay imagen
            has_image = self.browser.page.query_selector("img[alt='Descripción de la imagen']") is not None
            
            # Detectar tipo de pregunta para ajustar prompt
            q_lower = question_text.lower()
            is_vocabulary = any(word in q_lower for word in ['similar', 'mean', 'synonym', 'bold word', 'word mean'])
            is_reading_comprehension = any(word in q_lower for word in ['read the text', 'according to', 'paragraph'])
            
            # ====== DECISIÓN: Usar respuesta de AUDIO o llamar a Gemini ======
            if audio_answer_index >= 0:
                # Ya tenemos la respuesta del audio, usarla directamente
                answer_index = audio_answer_index
                print(f"[INFO] 🎵 Usando respuesta del análisis de audio")
            elif has_image or reading_text:
                # Tomar screenshot SOLO si es necesario (imagen o poco texto)
                print("[DEBUG] Step: Taking screenshot...")
                if has_image:
                     # Capture ONLY the image element to reduce size/latency
                     screenshot = None
                     try:
                         img_locator = self.browser.page.locator("img[alt='Descripción de la imagen']").first
                         if img_locator.is_visible():
                             screenshot = img_locator.screenshot()
                             if screenshot:
                                 print("[DEBUG] Step: Screenshot of IMAGE element taken.")
                         else:
                             screenshot = self.browser.screenshot()
                             if screenshot:
                                 print("[DEBUG] Step: Fallback to full page screenshot.")
                     except Exception as e:
                         print(f"[WARNING] Failed to capture screenshot: {e}")
                         screenshot = None
                     
                     # Si screenshot falló, forzar modo solo texto
                     if screenshot is None:
                         print("[INFO] Screenshot failed, forcing text-only mode")
                         has_image = False
                elif len(reading_text) < 100:
                     # If text is very short, screenshot might be better
                     screenshot = self.browser.screenshot()
                     if screenshot is None:
                         print("[INFO] Screenshot failed, using text-only mode")
                else:
                     # Pure text mode - FASTEST
                     screenshot = None
                print("[DEBUG] Step: Screenshot taken (or skipped).")
                
                # Construir prompt específico según tipo de pregunta
                print("[DEBUG] Step: Generating content with Gemini...")
                if has_image:
                    prompt = f"""ANALIZA LA IMAGEN PROPORCIONADA:
PREGUNTA: {question_text}

OPCIONES:
{[f"{i}. {opt}" for i, opt in enumerate(options)]}

INSTRUCCIONES:
1. Mira la imagen cuidadosamente (puede ser una carta, email, póster, etc.)
2. Lee la pregunta y busca la respuesta en la información visual/texto de la imagen.
3. Responde SOLO con el número de la opción correcta.
"""
                elif is_vocabulary or is_reading_comprehension:
                    prompt = f"""PREGUNTA DE COMPRENSIÓN DE LECTURA:
{question_text}

TEXTO DE LECTURA:
{reading_text[:2500]}

OPCIONES DISPONIBLES:
{[f"{i}. {opt}" for i, opt in enumerate(options)]}

INSTRUCCIONES:
- Lee el texto cuidadosamente
- Busca la palabra o frase mencionada en la pregunta (ej: "moved in")
- Determina su significado en contexto
- Selecciona la opción que sea sinónimo o tenga significado similar

Responde SOLO con el NÚMERO de la opción correcta (0, 1, 2, etc.).
NO des explique nada. SOLO el número."""
                else:
                    prompt = f"""PREGUNTA: {question_text}

TEXTO/CONTEXTO:
{reading_text[:2000]}

OPCIONES: {options}

Analiza el contexto y selecciona la opción correcta.
Responde SOLO con el número de la opción (0, 1, 2, 3, etc.).
NO expliques tu respuesta. SOLO envía el número."""
                
                if screenshot:
                    t0 = time.time()
                    result_text = self.solver.generate_content_with_image(prompt, screenshot, timeout=25)
                    print(f"[DEBUG] Gemini Image Gen took {time.time()-t0:.2f}s")
                else:
                    try:
                        print("[DEBUG] Step: Using FAST text-only model...")
                        t0 = time.time()
                        
                        # Clean reading_text if it's just a subset/duplicate of question
                        clean_reading = reading_text
                        if question_text in reading_text or len(reading_text) < len(question_text) + 20:
                             # If reading text is basically the question, ignore it to save tokens/confusion
                             if len(reading_text) < 200: 
                                 clean_reading = ""
                        
                        # Update prompt for ELSE case if reading text is empty
                        if "TEXTO/CONTEXTO:" in prompt and not clean_reading.strip():
                             prompt = prompt.replace(f"TEXTO/CONTEXTO:\n{reading_text[:2000]}", "")

                        # Debug Prompt Size
                        print(f"[DEBUG] Prompt size: {len(prompt)} chars")

                        # Call with TIMEOUT & RETRY
                        try:
                            response = self.solver.model.generate_content(
                                prompt, 
                                request_options={"timeout": 20}
                            )
                            result_text = response.text
                            print(f"[DEBUG] Gemini Text Gen took {time.time()-t0:.2f}s")
                        except Exception as e_first:
                             print(f"[WARNING] Gemini First Attempt Failed: {e_first}")
                             print("[INFO] Retrying with MINIMAL prompt (Question + Options)...")
                             
                             # MINIMAL PROMPT RETRY
                             minimal_prompt = f"PREGUNTA: {question_text}\nOPCIONES: {options}\nResponde SOLO con el número de la opción (0, 1, 2...)."
                             try:
                                 t1 = time.time()
                                 response_retry = self.solver.model.generate_content(
                                     minimal_prompt,
                                     request_options={"timeout": 20}
                                 )
                                 result_text = response_retry.text
                                 print(f"[DEBUG] Gemini Text Retry took {time.time()-t1:.2f}s")
                             except Exception as e_retry:
                                 print(f"[ERROR] Gemini Retry Failed: {e_retry}")
                                 print("[WARNING] FALLBACK: Seleccionando opción 0 para desbloquear aprendizaje.")
                                 result_text = "0"

                    except Exception as e:
                        print(f"[ERROR] Gemini Text Error (General): {e}")
                        result_text = ""
                
                if not result_text:
                    print("[ERROR] Falló la generación con Gemini (posible timeout)")
                    print("[WARNING] FALLBACK FINAL: Seleccionando opción 0.")
                    result_text = "0"

                print(f"[DEBUG] Gemini (Raw): {result_text}")
                
                # Extraer número
                match = re.search(r'(\d+)', result_text)
                if match:
                    answer_index = int(match.group(1))
                else:
                    answer_index = 0
            else:
                # Sin imagen ni texto, usar método de solo texto
                result = self.solver.analyze_question_text_only(question_text, options)
                answer_index = result.get("answer_index", 0)
            
            if answer_index < 0 or answer_index >= len(options):
                answer_index = 0
            
            answer_text = options[answer_index]
            print(f"[INFO] Respuesta seleccionada: {answer_text}")
            
            # Click en la opción
            option_elements[answer_index].click()
            self.browser.sleep(0.3)
            
            # Click en CHECK
            self._click_check_button()
            self.browser.sleep(0.5)
            
            # Click en OK del modal
            self.learn_from_mistake(question_text, full_context_for_sig)
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta (multiple choice) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en multiple choice: {e}")
            traceback.print_exc()
            return False

    def solve_audio_question(self, question_text: str) -> bool:
        """Resuelve preguntas de listening con audio."""
        try:
            print("[INFO] Detectado audio en la pregunta")
            
            # Encontrar elemento de audio
            audio_element = self.browser.page.query_selector("audio")
            if not audio_element:
                print("[ERROR] No se encontró elemento de audio")
                return False
            
            # Extraer la URL del audio
            audio_url = audio_element.get_attribute("src")
            if not audio_url:
                # Buscar en source child
                source_element = audio_element.query_selector("source")
                if source_element:
                    audio_url = source_element.get_attribute("src")
            
            print(f"[INFO] URL de audio: {audio_url}")
            
            # Descargar audio - Manejar blob URLs
            try:
                if audio_url.startswith("blob:"):
                    print("[INFO] Detectado blob URL, convirtiendo a bytes...")
                    # Usar JavaScript para convertir blob a base64
                    audio_base64 = self.browser.page.evaluate("""
                        async (audioUrl) => {
                            const response = await fetch(audioUrl);
                            const blob = await response.blob();
                            return new Promise((resolve) => {
                                const reader = new FileReader();
                                reader.onloadend = () => resolve(reader.result.split(',')[1]);
                                reader.readAsDataURL(blob);
                            });
                        }
                    """, audio_url)
                    audio_bytes = base64.b64decode(audio_base64)
                    print(f"[INFO] Audio descargado: {len(audio_bytes)} bytes")
                else:
                    # URL directa - descargar con requests
                    import requests
                    response = requests.get(audio_url, timeout=10)
                    audio_bytes = response.content
                    print(f"[INFO] Audio descargado: {len(audio_bytes)} bytes")
            except Exception as e:
                print(f"[ERROR] Error descargando audio: {e}")
                return False
            
            # Extraer opciones de respuesta
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
            
            print(f"[INFO] Opciones encontradas: {options}")
            
            if not options:
                print("[ERROR] No se encontraron opciones")
                return False
            
            # Enviar a Gemini para análisis
            print("[INFO] Enviando audio a Gemini para análisis...")
            result = self.solver.analyze_audio_question(audio_bytes, question_text, options)
            
            answer_index = result.get("answer_index", -1)
            answer_text = result.get("answer_text")
            
            if answer_index < 0 or answer_index >= len(options):
                print(f"[WARNING] Índice de respuesta inválido: {answer_index}, usando 0")
                answer_index = 0
            
            print(f"[INFO] Respuesta seleccionada: {options[answer_index]}")
            
            # Click en la opción correcta
            option_elements[answer_index].click()
            self.browser.sleep(0.3)
            
            # Click en CHECK
            self._click_check_button()
            self.browser.sleep(0.5)
            
            # Click en OK del modal
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta de audio respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en solve_audio_question: {e}")
            traceback.print_exc()
            return False

    def solve_fill_blanks(self, question_text: str) -> bool:
        """
        Resuelve preguntas de llenar espacios con inputs.
        OPTIMIZADO: Usa page.evaluate para extracción masiva y evita round-trips.
        """
        try:
            # OPTIMIZATION: Extract all hints and inputs in ONE go using JavaScript
            # This also assigns unique IDs to inputs to make filling them instant
            extraction_script = """() => {
                const results = [];
                let counter = 0;
                
                // Helper to clean text
                const clean = (text) => text ? text.replace(/\\s+/g, ' ').trim() : '';
                
                // Strategy 1: Find inputs and look for nearby hints
                const inputs = Array.from(document.querySelectorAll('input[type="text"]'));
                
                inputs.forEach(input => {
                    // Assign unique ID for fast access later
                    const uniqueId = 'bot-input-' + counter++;
                    input.setAttribute('data-bot-id', uniqueId);
                    
                    let hint = '';
                    
                    // Try 1: Container based
                    const container = input.closest('.bg-white') || input.closest('.rounded-xl') || input.parentElement;
                    if (container) {
                        // Clone to remove inputs from text extraction
                        const clone = container.cloneNode(true);
                        clone.querySelectorAll('input, button, .hidden').forEach(el => el.remove());
                        hint = clean(clone.textContent);
                    }
                    
                    // Try 2: Previous Sibling
                    if (!hint || hint.length < 3) {
                         let prev = input.previousElementSibling;
                         while(prev) {
                             if(prev.textContent.trim().length > 2) {
                                 hint = clean(prev.textContent);
                                 break;
                             }
                             prev = prev.previousElementSibling;
                         }
                    }
                    
                    // Limit text length
                    results.push({
                        id: uniqueId,
                        hint: hint.substring(0, 150),
                        selector: `input[data-bot-id="${uniqueId}"]`
                    });
                });
                
                // Optional: Extract breadcrumbs for context
                const breadcrumbEl = document.querySelector("p.tracking-widest.uppercase");
                const breadcrumb = breadcrumbEl ? breadcrumbEl.innerText.trim() : "";
                
                return { items: results, breadcrumb: breadcrumb };
            }"""
            
            # Execute JS
            data = self.browser.page.evaluate(extraction_script)
            fill_data = data.get('items', [])
            breadcrumbs = data.get('breadcrumb', "")
            
            print(f"[INFO] Encontradas {len(fill_data)} palabras para completar (Optimizado)")
            
            if not fill_data:
                return False
                
            # --- CONTEXT GENERATION ---
            hints_text = ""
            for i, item in enumerate(fill_data):
                hints_text += f"{i+1}. {item['hint']}\n"
                
            full_context_sig = f"TITLE: {breadcrumbs} || HINTS: {hints_text}"
            
            # --- LEARNED KNOWLEDGE CHECK ---
            print(f"[DEBUG] Checking knowledge with context: {full_context_sig[:100]}...")
            known_answers = self.try_solve_with_knowledge(question_text, full_context_sig)
            
            if known_answers:
                print(f"[INFO] Aplicando knowledge en FillBlanks: {known_answers}")
                filled_k = 0
                for i, ans in enumerate(known_answers):
                    if i < len(fill_data):
                        item = fill_data[i]
                        clean_ans = ans.replace("<br>", "").strip()
                        print(f"[INFO] Llenando learned [{i+1}]: {clean_ans}")
                        try:
                            # Use the ID selector directly
                            self.browser.page.fill(item['selector'], clean_ans)
                            filled_k += 1
                        except Exception as e:
                            print(f"[WARNING] Error filling learned answer {i+1}: {e}")
                
                if filled_k > 0:
                     self.browser.sleep(0.5)
                     self._click_check_button()
                     self.browser.sleep(1.0)
                     self.learn_from_mistake(question_text, full_context_sig)
                     self._click_ok_modal()
                     self.browser.sleep(self.delay)
                     return True
            
            # --- GEMINI GENERATION (unchanged logic, just using new data structure) ---
            # Detectar tipo de pregunta para ajustar el prompt
            q_lower = question_text.lower()
            is_anagram = "order" in q_lower and "letter" in q_lower
            is_emotion = "emotion" in q_lower
            is_incomplete = "_" in " ".join([d["hint"] for d in fill_data])
            
            if is_anagram:
                prompt = f"""Pregunta: {question_text}
Ordena las letras de cada palabra para formar la palabra correcta:
{hints_text}
INSTRUCCIONES:
- Responde SOLO con las palabras formadas, una por línea
- NO incluyas números ni puntos"""
            elif is_incomplete:
                prompt = f"""Completa las palabras (los guiones bajos _ representan letras faltantes):
{hints_text}
INSTRUCCIONES:
- Responde SOLO con las palabras completas, una por línea"""
            else:
                prompt = f"""Pregunta: {question_text}
Responde cada una de estas preguntas/pistas:
{hints_text}
INSTRUCCIONES:
- Responde con UNA palabra o frase corta por línea
- Responde en el MISMO ORDEN que las preguntas"""
            
            # Call Gemini
            result = self.solver.model.generate_content(prompt)
            response = result.text.strip()
            print(f"[DEBUG] Gemini responde:\n{response}")
            
            # Parse responses
            raw_lines = response.split("\n")
            answers = []
            for line in raw_lines:
                line = line.strip()
                if not line: continue
                clean = re.sub(r'^[\d]+[\.)\-:\s]+', '', line)
                clean = re.sub(r'^\*+\s*', '', clean)
                clean = re.sub(r'\*+$', '', clean)
                if clean: answers.append(clean.strip())
            
            print(f"[INFO] Respuestas parseadas: {answers}")
            
            # Fill inputs using direct selectors
            filled = 0
            for i, item in enumerate(fill_data):
                if i < len(answers):
                    answer = answers[i]
                    print(f"[INFO] Llenando [{i+1}]: {item['hint'][:30]}... → {answer}")
                    try:
                        self.browser.page.fill(item['selector'], answer)
                        filled += 1
                    except Exception as e:
                        print(f"[WARNING] Error llenando input {i+1}: {e}")
            
            print(f"[INFO] {filled}/{len(fill_data)} campos llenados")
            
            if filled == 0:
                return False
            
            self.browser.sleep(0.3)
            self._click_check_button()
            self.browser.sleep(0.5)
            self.learn_from_mistake(question_text, full_context_sig)
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta (fill blanks) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en fill blanks: {e}")
            traceback.print_exc()
            return False


    def solve_login_screen(self) -> bool:
        """Maneja la pantalla de login si aparece en medio de la actividad."""
        try:
            print("[INFO] Detectada pantalla de Login. Intentando autenticación automática...")
            
            email = self.config.get("email")
            password = self.config.get("password")
            
            if not email or not password:
                print("[ERROR] No hay credenciales en config.json para auto-login")
                return False
                
            # Verificar selectores
            if self.browser.page.locator("#mail-address").is_visible():
                print(f"[INFO] Ingresando email: {email}")
                self.browser.page.fill("#mail-address", email)
                self.browser.sleep(0.5)
                
                print("[INFO] Ingresando contraseña...")
                self.browser.page.fill("#password", password)
                self.browser.sleep(0.5)
                
                print("[INFO] Click en Ingresar")
                self.browser.page.click("button[type='submit']")
                self.browser.sleep(5) # Wait for redirects
                
                # Verificar si salimos del login
                if not self.browser.page.locator("#mail-address").is_visible():
                    print("[SUCCESS] Login recuperado exitosamente")
                    return True
                else:
                    print("[ERROR] Falló el login (campos siguen visibles)")
                    return False
            else:
                print("[WARNING] No se encontraron campos de login (falso positivo)")
                return False
                
        except Exception as e:
            print(f"[ERROR] Excepción en solve_login_screen: {e}")
            return False

    def solve_sentence_ordering(self, question_text: str) -> bool:
        prompt_parts = []
        correct_orders = []
        result = ""
        """Resuelve preguntas de ordenar oraciones (optimizado para velocidad)."""
        try:
            print("[INFO] Resolviendo pregunta de ordenar oraciones...")
            
            # 1. Encontrar contenedores droppable
            selector_prefix = "[data-rbd-droppable-id^='droppable-desktop']"
            droppables_count = len(self.browser.page.query_selector_all(selector_prefix))
            
            if droppables_count == 0:
                selector_prefix = "[data-rbd-droppable-id^='droppable-mobile']"
                droppables_count = len(self.browser.page.query_selector_all(selector_prefix))
            
            if droppables_count == 0:
                selector_prefix = "[data-rbd-droppable-id]"
                droppables_count = len(self.browser.page.query_selector_all(selector_prefix))
            
            if droppables_count == 0:
                print("[WARNING] No se encontraron contenedores droppable")
                return self.solve_with_screenshot(question_text)
            
            print(f"[INFO] Encontradas {droppables_count} oraciones para ordenar")
            
            # OPTIMIZACIÓN: Recolectar TODAS las oraciones primero, luego una sola llamada a Gemini
            all_sentences_data = []
            
            for index in range(droppables_count):
                droppables = self.browser.page.query_selector_all(selector_prefix)
                if index >= len(droppables):
                    break
                droppable = droppables[index]
                
                try:
                    droppable.scroll_into_view_if_needed()
                    self.browser.sleep(0.2)
                except:
                    pass
                
                # Intentos de encontrar items draggables (palabras o párrafos)
                draggables = droppable.query_selector_all("[data-rbd-draggable-id]")
                
                # Si no hay, intentar con tarjeta blanca típica de palabras
                if not draggables:
                    draggables = droppable.query_selector_all(".bg-white")
                
                # Extraer texto limpio
                words = []
                for el in draggables:
                    # Limpieza agresiva para párrafos que pueden tener "Check" u otros textos ocultos
                    # Usamos inner_text() y removemos saltos de línea extra
                    clean_text = el.inner_text().strip().replace("\n", " ")
                    if clean_text:
                        words.append(clean_text)
                
                # Si encontramos texto, lo agregamos como una "secuencia" a ordenar
                if words:
                    # DEBUG: Verificar si son párrafos largos
                    is_paragraph = any(len(w) > 50 for w in words)
                    if is_paragraph:
                         print(f"[INFO] Detectado ordenamiento de párrafos/oraciones largas en índice {index}")
                    
                    all_sentences_data.append({
                        "index": index,
                        "words": words,
                        "selector": selector_prefix,
                        "is_paragraph": is_paragraph
                    })
            
            if not all_sentences_data:
                return False
            
            # context_data for specific signature
            # FIX: Sort items to ensure signature is deterministic regardless of shuffle
            ctx_sentences = " | ".join([" ".join(sorted(d['words'])) for d in all_sentences_data])
            
            # --- ORDEN DE PRIORIDAD: KNOWLEDGE > HARDCODE > FAIL-FAST PARAGRAPHS > GEMINI ---
            
            # 1. KNOWLEDGE
            known_answers = self.try_solve_with_knowledge(question_text, ctx_sentences)
            
            if known_answers:
                 print(f"[INFO] Aplicando orden aprendido: {known_answers}")
                 
                 # Caso especial: Respuesta aprendida es un solo bloque de texto (concatenado)
                 full_learned_text = " ".join(known_answers).lower().replace("\n", " ")
                 
                 # Verificar si podemos usar estratégia de "Posición en texto"
                 # Esto ocurre cuando el modal devuelve "SentenceA SentenceB SentenceC" todo junto
                 valid_items_count = 0
                 matched_items_with_pos = []
                 
                 for data in all_sentences_data:
                     # Reconstruir la oración del item
                     item_text = " ".join(data['words']).lower().strip()
                     # Normalizar espacios
                     item_text = " ".join(item_text.split())
                     
                     if item_text in full_learned_text:
                         valid_items_count += 1
                         # Guardar posición para ordenar
                         pos = full_learned_text.find(item_text)
                         matched_items_with_pos.append( (pos, data['words']) )
                     else:
                         # Intento más flexible (primeras 5 palabras)
                         short_text = " ".join(data['words'][:5]).lower().strip()
                         if short_text in full_learned_text:
                             valid_items_count += 1
                             pos = full_learned_text.find(short_text)
                             matched_items_with_pos.append( (pos, data['words']) )
                 
                 blob_ratio = valid_items_count / len(all_sentences_data) if all_sentences_data else 0
                 
                 if blob_ratio >= 0.75 and len(known_answers) < len(all_sentences_data):
                     print(f"[INFO] Detectado Blob de texto ({blob_ratio:.2f}). Ordenando por posición en texto aprendido.")
                     matched_items_with_pos.sort(key=lambda x: x[0])
                     correct_orders.append([x[1] for x in matched_items_with_pos])
                     
                 else:
                     # Estrategia Mejorada: Mapeo Inteligente por Oración
                     # Para cada conjunto de palabras desordenadas, buscar cuál de las frases aprendidas les corresponde
                     for data in all_sentences_data:
                         available_lower = [w.lower().strip() for w in data['words']]
                         
                         best_learned_sent = None
                         best_ratio = 0
                         
                         # Detectar si estamos tratando con tokens largos (frases)
                         is_long_phrase_tokens = any(len(w) > 20 for w in available_lower)

                         # Buscar la frase aprendida que mejor encaje con estas palabras
                         for learned_sent in known_answers:
                             l_lower = learned_sent.lower()
                             
                             # Estrategia unificada: Substring matching robusto
                             # Funciona para palabras sueltas Y para frases
                             matches = 0
                             for token in available_lower:
                                 # Limpiar puntuación para búsqueda más flexible
                                 t_clean = token.strip(".,;:?!")
                                 # Verificar si el token (o su versión limpia) es substring de la frase aprendida
                                 if t_clean and t_clean in l_lower:
                                    matches += 1
                                    
                             ratio = matches / len(available_lower) if available_lower else 0
                             
                             if ratio > best_ratio:
                                 best_ratio = ratio
                                 best_learned_sent = l_lower

                         print(f"[DEBUG] Best match ratio for row: {best_ratio:.2f}")

                         if best_ratio < 0.50 or not best_learned_sent:
                             print(f"[WARNING] No se encontró frase aprendida compatible para: {available_lower}")
                             correct_orders.append(data['words'])
                             continue
                             
                         # Determinar estrategia: Palabras vs Párrafos
                         is_paragraph_mode = any(len(w.strip().split()) > 1 for w in data['words'])
                         item_priorities = []
                         
                         if is_paragraph_mode:
                             # Estrategia Párrafos: Búsqueda exacta + case sensitive + manejo de duplicados
                             
                             # 1. Mapear todas las posiciones ocupadas para no repetir
                             occupied_mask = [False] * len(best_learned_sent)
                             
                             for word in data['words']:
                                 w_strip = word.strip() # Respetar casing original
                                 w_low = w_strip.lower()
                                 
                                 best_pos = -1
                                 best_match_type = 0 # 0: None, 1: Lower, 2: Exact
                                 
                                 # Buscar t-o-d-a-s las ocurrencias posibles y elegir la mejor libre
                                 # Iteramos sobre el string aprendido
                                 search_start = 0
                                 while True:
                                     # Buscamos versión lowercase para encontrar candidatos
                                     try:
                                         p = best_learned_sent.lower().find(w_low, search_start)
                                     except:
                                         p = -1
                                         
                                     if p == -1:
                                         break
                                     
                                     # Candidato encontrado en 'p'
                                     # Verificar si choca con ocupados (intersección de rangos)
                                     is_occupied = any(occupied_mask[i] for i in range(p, p + len(w_strip)))
                                     
                                     if not is_occupied:
                                         # Verificar calidad del match
                                         # Check 1: Boundaries (palabra completa)
                                         # Check 2: Case match
                                         
                                         # Extraer fragmento real del texto aprendido
                                         fragment = best_learned_sent[p : p + len(w_strip)]
                                         
                                         match_type = 1 # Match básico (lowercase)
                                         if fragment == w_strip:
                                             match_type = 2 # Match exacto (case sensitive)
                                             
                                         # Priorizar: Exact > Lower. Si ya tenemos uno Exact, no cambiamos salvo que sea anterior?
                                         # En realidad, si hay duplicados "She" y "she", queremos asignar "She" al match "She" y "she" al match "she".
                                         
                                         if match_type > best_match_type:
                                             best_pos = p
                                             best_match_type = match_type
                                             # Si encontramos exacto, ¿paramos? 
                                             # No necesariamente, podría haber otro exacto antes? 
                                             # Asumimos que queremos el PRIMER match exacto disponible.
                                             if match_type == 2:
                                                 break 
                                         elif match_type == best_match_type and best_pos == -1:
                                             best_pos = p
                                             
                                     search_start = p + 1
                                 
                                 # Si no encontramos nada decente, fallback a búsqueda simple sin mask (aunque se repita)
                                 if best_pos == -1:
                                     # Fallback desesperado
                                     best_pos = best_learned_sent.lower().find(w_low)
                                     
                                 # Registrar ocupación
                                 if best_pos != -1:
                                    for i in range(best_pos, min(best_pos + len(w_strip), len(best_learned_sent))):
                                        occupied_mask[i] = True
                                 else:
                                    best_pos = 999999
                                     
                                 item_priorities.append((best_pos, word))
                                 
                         else:
                             # Estrategia Palabras: Tokens exactos (evita match parcial 'a' en 'can')
                             l_tokens = best_learned_sent.split()
                             
                             token_positions = {}
                             for idx_tok, tok in enumerate(l_tokens):
                                 t_clean = tok.strip().strip(".,;:?!")
                                 if t_clean not in token_positions:
                                     token_positions[t_clean] = []
                                 token_positions[t_clean].append(idx_tok)
                            
                             used_counters = {k: 0 for k in token_positions} 
                             
                             for word in data['words']:
                                 w_low = word.lower().strip().strip(".,;:?!")
                                 
                                 pos = 999999
                                 if w_low in token_positions:
                                     count = used_counters[w_low]
                                     if count < len(token_positions[w_low]):
                                         pos = token_positions[w_low][count]
                                         used_counters[w_low] += 1
                                     else:
                                         pos = token_positions[w_low][-1] + 1
                                 
                                 item_priorities.append((pos, word))
                         
                         item_priorities.sort(key=lambda x: x[0])
                         correct_orders.append([x[1] for x in item_priorities])

                         




                         









                         

            


            # 3. FAIL-FAST PARAGRAPHS (Si no hay nada y son párrafos)
            if not correct_orders:
                any_paragraph = any(d.get('is_paragraph', False) for d in all_sentences_data)
                if any_paragraph:
                    print("[INFO] Estrategia Fail-Fast para Párrafos: Click CHECK para aprender inmediatamente.")
                    self._click_check_button()
                    self.browser.sleep(0.5)
                    self.learn_from_mistake(question_text, ctx_sentences)
                    self._click_ok_modal()
                    return True

            # 4. GEMINI (Si no hay nada más)
            if not correct_orders:
                prompt_parts = []
                for i, data in enumerate(all_sentences_data):
                    prompt_parts.append(f"{i+1}. {data['words']}")
                
                prompt = f"""Ordena las palabras para formar oraciones correctas en inglés:
{chr(10).join(prompt_parts)}
Responde SOLO con: 1. Word | Word | Word"""
                
                response = self.solver.model.generate_content(prompt)
                result = response.text.strip()
                print(f"[DEBUG] Gemini ordenamiento:\n{result}")
                
                for line in result.split("\n"):
                    line = line.strip()
                    if not line: continue
                    clean = re.sub(r'^\d+[\.\):\s]+', '', line)
                    words = [w.strip() for w in clean.split("|") if w.strip()]
                    if words:
                        correct_orders.append(words)
            # --- HARDCODED ANSWERS END ---
            
            # for line in result.split("\n"): 
            # (El código original de parsing se movió dentro del else)
            
            print(f"[INFO] Órdenes parseados: {len(correct_orders)} oraciones")
            
            # 4. Reordenar cada oración (OPTIMIZADO)
            for data_idx, data in enumerate(all_sentences_data):
                if data_idx >= len(correct_orders):
                    continue
                    
                correct_order = correct_orders[data_idx]
                index = data["index"]
                
                print(f"--- Ordenando Oración {index + 1} ---")
                print(f"[INFO] Orden objetivo: {correct_order}")
                
                # Máximo de intentos para evitar loops infinitos
                max_attempts = len(correct_order) * 2
                attempts = 0
                
                while attempts < max_attempts:
                    attempts += 1
                    
                    # Re-query elementos
                    droppables = self.browser.page.query_selector_all(data["selector"])
                    if index >= len(droppables):
                        break
                    droppable = droppables[index]
                    
                    current_draggables = droppable.query_selector_all("[data-rbd-draggable-id]")
                    current_texts = [el.inner_text().strip().lower() for el in current_draggables]
                    correct_texts = [w.lower() for w in correct_order]
                    
                    # Verificar si ya está ordenado
                    if current_texts == correct_texts:
                        print(f"[INFO] Oración {index + 1} ordenada correctamente.")
                        break
                    
                    # Encontrar primera discrepancia y mover
                    moved = False
                    for target_pos, correct_word in enumerate(correct_texts):
                        if target_pos >= len(current_texts):
                            break
                        if current_texts[target_pos] != correct_word:
                            # Buscar dónde está la palabra correcta
                            for current_pos in range(target_pos + 1, len(current_texts)):
                                if current_texts[current_pos] == correct_word:
                                    # Mover usando teclado (más rápido)
                                    source_el = current_draggables[current_pos]
                                    
                                    try:
                                        source_el.focus()
                                        self.browser.sleep(0.05)
                                        
                                        # Levantar
                                        self.browser.page.keyboard.press("Space")
                                        self.browser.sleep(0.05)
                                        
                                        # Mover todas las posiciones de una vez
                                        steps = current_pos - target_pos
                                        for _ in range(steps):
                                            self.browser.page.keyboard.press("ArrowLeft")
                                            self.browser.sleep(0.02)  # Muy rápido
                                        
                                        # Soltar
                                        self.browser.page.keyboard.press("Space")
                                        self.browser.sleep(0.15)  # Pequeña pausa para que React actualice
                                        
                                        print(f"[INFO] '{correct_word}' movido de {current_pos} → {target_pos}")
                                        moved = True
                                        
                                    except Exception as e:
                                        print(f"[WARNING] Error moviendo: {e}")
                                    break
                            if moved:
                                break
                    
                    if not moved:
                        # No pudimos mover nada, salir para evitar loop infinito
                        print("[WARNING] No se pudo mover más elementos")
                        break
            
            # 5. CHECK FINAL
            # 5. CHECK FINAL
            self.browser.sleep(0.3)
            self._click_check_button()
            self.browser.sleep(0.5)
            self.learn_from_mistake(question_text, ctx_sentences)
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta (sentence ordering) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en sentence ordering: {e}")
            traceback.print_exc()
            return False

    def solve_with_screenshot(self, question_text: str) -> bool:
        """Resuelve pregunta desconocida usando screenshot + HTML + análisis visual."""
        try:
            print("[INFO] Tipo de pregunta desconocido, usando análisis visual + HTML...")
            
            # 0. Check for Login Screen explicitly
            if self.browser.page.locator("#mail-address").is_visible() and self.browser.page.locator("#password").is_visible():
                print("[INFO] Detectado formulario de Login (heurística).")
                return self.solve_login_screen()

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
                
                # Check if gemini detected login
                if "login" in str(result.get("question_type", "")).lower() or "inicio de sesión" in str(result.get("description", "")).lower():
                     print("[INFO] Gemini detectó Login. Ejecutando solve_login_screen...")
                     return self.solve_login_screen()

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
                    return True
            
            # Si no pudimos resolver automáticamente, mostrar la información
            print("[WARNING] No se pudo resolver automáticamente. Información obtenida:")
            print(f"  - Tipo: {result.get('question_type')}")
            print(f"  - Respuesta sugerida: {result.get('answer')}")
            print(f"  - Acciones: {result.get('actions')}")
            
            return False
            
        except Exception as e:
            print(f"[ERROR] Error en análisis visual + HTML: {e}")
            traceback.print_exc()
            return False

    def solve_sentence_completion(self, question_text: str) -> bool:
        """Resuelve preguntas de completar oraciones con verbos/palabras."""
        try:
            print("[INFO] Resolviendo pregunta de completar oraciones...")

            # Función para normalizar texto (quita espacios, normaliza apóstrofes)
            def normalize(text):
                return text.upper().replace("´", "'").replace("`", "'").strip()
            
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
                return self.solve_with_screenshot(question_text)
            
            # --- LEARNED KNOWLEDGE CHECK ---
            # Generar clave única basada en el contenido real, no solo el título
            # --- LEARNED KNOWLEDGE CHECK ---
            # Generar clave única basada en el contenido real
            unique_key = question_text
            if rows_data:
                # Usar todos los textos para ser inequívoco
                sentences_signature = " | ".join([r['sentence'][:30] for r in rows_data])
                unique_key += " || " + sentences_signature
            
            print(f"[DEBUG] Generated Knowledge Key: {unique_key[:100]}...")
            
            known_answers = self.try_solve_with_knowledge(unique_key)
            if known_answers:
                print(f"[INFO] Usando respuestas aprendidas en Sentence Completion: {known_answers}")
                clicks_made = 0
                for i, ans in enumerate(known_answers):
                    # ... (rest of loop logic) ...
                    # Reimplementing loop logic here since I'm replacing the block
                    if i >= len(rows_data): break
                    
                    target_ans = ans.upper().strip()
                    row = rows_data[i]
                    
                    found = False
                    # PRIMERO: buscar match EXACTO
                    for opt in row['options']:
                        if normalize(opt['text']) == target_ans:
                            try:
                                opt['element'].click()
                                clicks_made += 1
                                found = True
                                self.browser.sleep(0.2)
                            except: pass
                            break
                    
                    # SEGUNDO: buscar match sin normalizar (literal)
                    if not found:
                         for opt in row['options']:
                            if opt['text'].upper().strip() == target_ans:
                                try:
                                    opt['element'].click()
                                    clicks_made += 1
                                    found = True
                                    self.browser.sleep(0.2)
                                except: pass
                                break
                                
                if clicks_made > 0:
                    self.browser.sleep(0.5)
                    self._click_check_button()
                    self.browser.sleep(1.0)
                    self.learn_from_mistake(unique_key) # Usar la clave única para aprender
                    self._click_ok_modal()
                    return True


            print(f"[INFO] {len(rows_data)} oraciones a completar:")
            for i, row in enumerate(rows_data):
                print(f"  {i+1}. '{row['sentence']}' → [{', '.join([o['text'] for o in row['options']])}]")
            
            # 2. Crear prompt conciso para Gemini
            sentences_text = ""
            all_options = set()
            for i, row in enumerate(rows_data):
                opts = ', '.join([o['text'] for o in row['options']])
                sentences_text += f"\n{i+1}. {row['sentence']} → [{opts}]"
                for o in row['options']:
                    all_options.add(o['text'].upper())
            
            # Prompt ultra-conciso que fuerza respuesta exacta
            prompt = f"""{question_text}
{sentences_text}

Responde SOLO con UNA de estas opciones para cada oración: {', '.join(all_options)}
Formato exacto:
1. OPCIÓN
2. OPCIÓN"""
            
            response = self.solver.model.generate_content(prompt)
            result = response.text.strip()
            print(f"[DEBUG] Gemini: {result}")
            
            # 3. Parsear respuestas y hacer clicks
            lines = result.split("\n")
            clicked = 0
            

            
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
            self.browser.sleep(1.0)
            self.learn_from_mistake(unique_key)
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta (sentence completion) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en sentence completion: {e}")
            traceback.print_exc()
            return False

    def solve_matching_buttons(self, question_text: str) -> bool:
        """Resuelve preguntas de matching con múltiples botones por fila."""
        try:
            print("[INFO] Resolviendo pregunta de BOTONES EN LÍNEA / MATCHING...")
            self.browser.sleep(1)
            

            


            # 1. Tomar screenshot para análisis visual (con timeout handling)
            screenshot = None
            try:
                screenshot = self.browser.screenshot()
            except Exception as screenshot_err:
                print(f"[WARNING] No se pudo tomar screenshot (continuando sin imagen): {screenshot_err}")
                screenshot = None
            
            # 2. Extraer las filas y sus opciones de forma robusta
            rows_data = []
            
            # Scroll para asegurar que todo el DOM está renderizado
            try:
                self.browser.page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                self.browser.sleep(0.3)
                self.browser.page.evaluate("window.scrollTo(0, 0)") # Volver arriba para no afectar clicks
                self.browser.sleep(0.3)
            except: pass

            # Selector mejorado: Busca contenedores de items (generalmente p-5 o estilo tarjeta) que tengan botones activar-btn
            selector = "div.bg-white:has(button.activar-btn), div.bg-gray-50:has(button.activar-btn), div.p-5:has(button.activar-btn)"
            raw_containers = self.browser.page.query_selector_all(selector)
            
            # Deduplicar contenedores (por texto o referencia) para evitar procesar el mismo bloqe dos veces
            row_containers = []
            seen_content = set()
            
            for rc in raw_containers:
                 # Verificar que no es un contenedor "padre" gigante (ej. el wrapper principal)
                 # Los items suelen ser pequeños.
                 # Estrategia: Verificar texto. Si ya vimos este inicio de texto, es duplicado.
                 try:
                     txt = rc.inner_text().strip()[:50]
                     if txt and txt not in seen_content:
                         row_containers.append(rc)
                         seen_content.add(txt)
                 except: continue
            
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
                return self.solve_with_screenshot(question_text)
            
            print(f"[INFO] Encontradas {len(rows_data)} filas")
            for row in rows_data:
                print(f"  - '{row['label']}': {[opt['text'] for opt in row['options']]}")
            
            # Detectar imagen y párrafo de texto
            has_image = self.browser.page.query_selector("img[alt='Descripción de la imagen']") is not None
            
            # Buscar párrafo de texto (div con overflow que contiene texto de lectura)
            paragraph_text = ""
            
            # Intentar selectores específicos para lecturas
            reading_selectors = [
                 # Selector exacto del caso reportado de Andrea
                "div.w-full.h-100.overflow-y-auto.text-justify.p-4",
                ".overflow-y-auto", 
                "div[class*='text-justify']",
                ".bg-gray-50.p-4", # A veces el texto está en un cuadro gris
            ]
            
            for sel in reading_selectors:
                el = self.browser.page.query_selector(sel)
                if el:
                    text = el.inner_text().strip()
                    if len(text) > 20: # Filtrar textos muy cortos
                        paragraph_text = text
                        print(f"[INFO] Texto de lectura encontrado ({len(text)} chars): {text[:50]}...")
                        break
            
            if not paragraph_text:
                print("[WARNING] No se encontró texto de lectura explícito")

            # --- KNOWLEDGE CHECK ---
            unique_key = question_text
            if rows_data:
                # Firma única basada en las preguntas/items (para ser más específico)
                row_sig = " | ".join([r['label'][:30] for r in rows_data])
                unique_key = f"{question_text} || {row_sig}"
            
            print(f"[DEBUG] Knowledge Key (base): {unique_key[:80]}...")
            known_answers = self.try_solve_with_knowledge(unique_key, paragraph_text)
            
            if known_answers:
                print(f"[INFO] Usando respuestas aprendidas (con contexto): {known_answers}")
                clicks_k = 0
                for i, ans in enumerate(known_answers):
                    if i >= len(rows_data): break
                    
                    target = ans.strip().upper().replace("´", "'").replace("`", "'")
                    row = rows_data[i]
                    
                    # Buscar opción coincidente
                    found_opt = None
                    for opt in row['options']:
                         opt_txt = opt['text'].strip().upper().replace("´", "'").replace("`", "'")
                         if opt_txt == target:
                             found_opt = opt
                             break
                    
                    if found_opt:
                        try:
                            found_opt['element'].click()
                            print(f"[INFO] Row {i+1} (Known) -> {found_opt['text']}")
                            clicks_k += 1
                            self.browser.sleep(0.2)
                        except: pass
                
                if clicks_k > 0:
                    self.browser.sleep(0.5)
                    self._click_check_button()
                    self.browser.sleep(1.0)
                    self.learn_from_mistake(unique_key, paragraph_text)
                    self._click_ok_modal()
                    return True
            
            has_sentence_structure = any("[___]" in row['label'] for row in rows_data)

            # 3. Crear prompt para Gemini (Restaurado)
            options_text = ""
            for i, row in enumerate(rows_data):
                # Extraer texto de opciones para el prompt para restringir alucinaciones
                opts_str = ", ".join([f"'{o['text']}'" for o in row['options']])
                options_text += f"\n{i+1}. Pregunta: '{row['label']}'\n   Opciones Disponibles: [{opts_str}]"
            
            # Detectar si es TRUE/FALSE (Restaurado)
            is_true_false = all(
                any(o['text'].upper() in ['TRUE', 'FALSE'] for o in row['options'])
                for row in rows_data
            )
            
            if is_true_false and paragraph_text and not has_image:
                # TRUE/FALSE con párrafo de texto - SIN imagen
                prompt = f"""Texto: {paragraph_text}

Afirmaciones:{options_text}

IMPORTANTE: Responde SOLO con el formato:
1. TRUE
2. FALSE
3. TRUE
...

Sin asteriscos, sin explicaciones, sin formato markdown. Solo el número y TRUE o FALSE."""
                # Sin imagen, solo texto
                response = self.solver.model.generate_content(prompt)
            elif is_true_false and has_image and screenshot:
                # TRUE/FALSE con imagen
                prompt = f"""Afirmaciones:{options_text}
 
 IMPORTANTE: Responde SOLO con el formato:
 1. TRUE
 2. FALSE
 ...
 
 Sin asteriscos, sin explicaciones, sin formato markdown. Solo el número y TRUE o FALSE.
 
 Ejemplos de RAZONAMIENTO:
 - Si dice "two sofas" y ves solo uno -> FALSE.
 - Si dice "big dining room" y no hay comedor o es pequeño -> FALSE.
 - Si dice "washing machine in bathroom" y la ves -> TRUE.
 - Si dice "She lives in a big house" -> TRUE (la casa de la imagen es grande, 2 pisos).
 - Si dice "There are two bedrooms" -> FALSE (solo se ve una habitación o no son dos).
 """
                image_part = {
                    "mime_type": "image/png",
                    "data": base64.b64encode(screenshot).decode()
                }
                response = self.solver.model.generate_content([prompt, image_part])
            elif has_sentence_structure and not has_image:
                # Completar oraciones
                prompt = f"""Oraciones:{options_text}

IMPORTANTE: Responde SOLO con el formato:
1. OPCIÓN_CORRECTA
2. OPCIÓN_CORRECTA
...

REGLAS:
- Elige la respuesta ÚNICAMENTE de las "Opciones Disponibles" de esa oración.
- NO uses opciones de otras oraciones.
Sin asteriscos, sin explicaciones, sin formato markdown."""
                response = self.solver.model.generate_content(prompt)
            elif screenshot:
                # Matching con imagen (si hay screenshot disponible)
                prompt = f"""Preguntas y Opciones:{options_text}

IMPORTANTE: Responde SOLO con el formato:
1. RESPUESTA_CORRECTA
2. RESPUESTA_CORRECTA
...

REGLAS:
- Para cada pregunta, elige la respuesta CORRECTA ÚNICAMENTE de sus "Opciones Disponibles".
- NO elijas opciones de otras preguntas.
- Si es porcentaje, escribe el porcentaje exacto del botón.
"""
                image_part = {
                    "mime_type": "image/png",
                    "data": base64.b64encode(screenshot).decode()
                }
                response = self.solver.model.generate_content([prompt, image_part])
            else:
                # Fallback sin imagen
                prompt = f"""Preguntas y Opciones:{options_text}

IMPORTANTE: Responde SOLO con el formato:
1. RESPUESTA_CORRECTA
2. RESPUESTA_CORRECTA
...

REGLAS:
- Para cada pregunta, elige la respuesta CORRECTA ÚNICAMENTE de sus "Opciones Disponibles".
- NO elijas opciones de otras preguntas.
- ELIGE SOLO DE LAS OPCIONES MOSTRADAS. NO INVENTES PALABRAS.
- Si es porcentaje, escribe el número (ej: 7,2%). Sin explicaciones"""
                response = self.solver.model.generate_content(prompt)
            
            result_text = response.text.strip()
            print(f"[DEBUG] Respuesta de Gemini:\n{result_text}")
            
            # 5. Parsear respuestas y hacer clicks
            
            # Función para normalizar texto
            def normalize(text):
                # Normalizar TODOS los tipos de apóstrofes y comillas a apóstrofe recto
                normalized = text.upper()
                # Reemplazar TODOS los apóstrofes tipográficos (Unicode) por apóstrofe recto (ASCII)
                normalized = normalized.replace("\u2019", "'").replace("\u2018", "'").replace("\u201D", "'").replace("\u201C", "'").replace("`", "'").replace("´", "'")
                # Remover asteriscos de markdown
                normalized = normalized.replace("*", "")
                # Normalizar espacios múltiples a uno solo
                normalized = " ".join(normalized.split())
                return normalized.strip()
            
            clicked = 0
            
            print(f"[DEBUG] Parseando {len(result_text.splitlines())} líneas de respuesta...")
            for line in result_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                
                
                # Buscar formato simple: "1. TRUE" o "1. NO, HE ISN'T"
                # Regex más flexible: Acepta números, porcentajes, etc.
                match = re.search(r'(\d+)[\.\):\s]+(.+)', line)
                if not match:
                    print(f"[DEBUG] Línea no matchea regex: '{line}'")
                    continue
                
                row_num = int(match.group(1)) - 1
                raw_answer = match.group(2).strip()
                answer = normalize(raw_answer)
                
                print(f"[DEBUG] Parseado: Fila {row_num + 1}, Respuesta = '{answer}'")
                
                if row_num < len(rows_data):
                    # --- RE-QUERY ROW CONTAINER PARA EVITAR STALE ELEMENTS ---
                    # Re-buscamos los contenedores frescos
                    try:
                        selector = "div.bg-white:has(button.activar-btn), div.bg-gray-50:has(button.activar-btn), div.p-5:has(button.activar-btn)"
                        fresh_containers = self.browser.page.query_selector_all(selector)
                        
                        target_row_container = None
                        target_row_label = rows_data[row_num]['label']
                        
                        # Intentar encontrar el contenedor que corresponda a esta fila
                        # Mapeo por índice si la cantidad coincide
                        if len(fresh_containers) == len(rows_data):
                            target_row_container = fresh_containers[row_num]
                        else:
                            # Fallback: Comparar texto (contenido)
                            # Esto es lento pero seguro
                            label_fragment = target_row_label.replace("[___]", "")[:20]
                            for fc in fresh_containers:
                                if label_fragment in fc.inner_text():
                                    target_row_container = fc
                                    break
                    except:
                        target_row_container = None

                    matched_opt_element = None
                    matched_opt_text = ""

                    # Si pudimos refrescar el contenedor, buscamos botones dentro
                    if target_row_container:
                        buttons = target_row_container.query_selector_all("button.activar-btn")
                        
                        # 1. Match Exacto (Normalizado)
                        for btn in buttons:
                            btn_text = btn.inner_text().strip()
                            btn_norm = normalize(btn_text)
                            if btn_norm == answer:
                                matched_opt_element = btn
                                matched_opt_text = btn_text
                                print(f"[DEBUG] Match Exacto (Fresh): '{btn_norm}' == '{answer}'")
                                break
                        
                        # 2. Match Contención
                        if not matched_opt_element:
                            for btn in buttons:
                                btn_text = btn.inner_text().strip()
                                btn_norm = normalize(btn_text)
                                if (len(answer) > 2 and answer in btn_norm) or (len(btn_norm) > 2 and btn_norm in answer):
                                     matched_opt_element = btn
                                     matched_opt_text = btn_text
                                     print(f"[DEBUG] Match Contención (Fresh): '{btn_norm}' ~ '{answer}'")
                                     break
                    else:
                        print(f"[WARNING] No se pudo refrescar contenedor para fila {row_num+1}. Usando referencias viejas (riesgo de StaleElement).")
                        # Fallback a rows_data original (código viejo)
                        row = rows_data[row_num]
                        for opt in row['options']:
                            opt_norm = normalize(opt['text'])
                            if opt_norm == answer:
                                matched_opt_element = opt['element']
                                matched_opt_text = opt['text']
                                break

                    # CLICK
                    if matched_opt_element:
                        print(f"[INFO] {rows_data[row_num]['label'][:30]}... → {matched_opt_text}")
                        
                        # ESTRATEGIA: JS Click Forzado (Solicitado por usuario)
                        # Evita problemas de visibilidad, scrolling o overlays.
                        try:
                            # Intento 1: JS Click directo
                            matched_opt_element.evaluate("el => el.click()")
                            clicked += 1
                            self.browser.sleep(0.3) 
                        except Exception as e:
                            print(f"[WARNING] Falló JS Click: {e}. Intentando click nativo...")
                            try:
                                matched_opt_element.scroll_into_view_if_needed()
                                matched_opt_element.click(force=True)
                                clicked += 1
                            except:
                                print(f"[WARNING] No se pudo click en {matched_opt_text} (FINAL)")
                    
                    else:
                        print(f"[WARNING] NO se encontró match para '{answer}' en fila {row_num + 1}")
                    
                    # FALLBACK: Random Choice (Updated for new variable)
                    if not matched_opt_element and row['options']:
                         print(f"[WARNING] No match found for row {row_num+1} ('{answer}'). Selecting RANDOM fallback to ensure completion.")
                         # Re-query random option from fresh buttons if possible
                         try:
                             if target_row_container:
                                  opts = target_row_container.query_selector_all("button.activar-btn")
                                  if opts:
                                      rnd_btn = random.choice(opts)
                                      rnd_btn.scroll_into_view_if_needed()
                                      rnd_btn.click(force=True)
                                      clicked += 1
                                      print(f"[INFO] Random Click -> {rnd_btn.inner_text()}")
                         except: pass
            
            print(f"[INFO] Clicks realizados: {clicked}")
            
            self.browser.sleep(0.5)
            
            # 6. Click en CHECK
            self._click_check_button()
            self.browser.sleep(1)
            
            # 7. Click en OK del modal
            self.browser.sleep(0.5)
            # Ahora unique_key está definida gracias al refactor
            try:
                # FIX: Pasar paragraph_text para que el hash coincida con try_solve_with_knowledge
                self.learn_from_mistake(unique_key, paragraph_text)
            except Exception as e:
                print(f"[ERROR] Learning failed: {e}")
                
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta (matching) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en matching buttons: {e}")
            traceback.print_exc()
            return False

    def solve_image_drag_match(self, question_text: str) -> bool:
        """Resuelve preguntas de matching imágenes con opciones."""
        try:
            print("[INFO] Resolviendo pregunta de matching imágenes...")
            
            # --- HARDCODED ANSWERS START ---
            if "LOOK AT THE PICTURES. GRAB THE CORRESPONDING NAME OF THE OCCASION" in question_text.upper():
                print("[OVERRIDE] Detectada pregunta de Occasions. Aplicando respuestas hardcoded.")
                try:
                    # Orden correcto basado en visualización (L-R, T-B): 
                    # 1. Birthday (Pastel)
                    # 2. Valentine's day (Corazón)
                    # 3. Christmas (Santa)
                    # 4. Mother's day (Silueta mamá)
                    correct_order = ["Birthday", "Valentine's day", "Christmas", "Mother's day"]
                    
                    zone_elements = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
                    clicks_made = 0
                    
                    for i, zone_btn in enumerate(zone_elements):
                        if i >= len(correct_order):
                            break
                            
                        target_answer = correct_order[i]
                        print(f"[INFO] Hardcode Zona {i+1} -> Buscando '{target_answer}'")
                        
                        # Buscar el botón de opción correspondiente
                        # Usamos selectores amplios para encontrar el botón correcto
                        try:
                            # Intentar clickear la opción directamente
                            # Buscamos botones que contengan el texto, ignorando case
                            option_btn = self.browser.page.get_by_role("button", name=re.compile(re.escape(target_answer), re.IGNORECASE))
                            
                            # Filtrar botones que no son de opciones (ej. no el mismo Waiting answer si tuviera texto)
                            if option_btn.count() > 0:
                                # A veces hay múltiples, tomamos el que parece estar en el panel de opciones
                                # O simplemente el primero visible
                                for k in range(option_btn.count()):
                                    btn = option_btn.nth(k)
                                    if btn.is_visible():
                                        btn.click()
                                        print(f"[SUCCESS] Click en '{target_answer}'")
                                        clicks_made += 1
                                        self.browser.sleep(0.3)
                                        break
                        except Exception as e:
                            print(f"[WARNING] No se pudo clickear '{target_answer}': {e}")
                            
                    if clicks_made > 0:
                        self.browser.sleep(0.5)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self._click_ok_modal()
                        return True
                        
                except Exception as e:
                    print(f"[ERROR] Falló hardcode occasions: {e}")
                    # Si falla, dejamos que continúe con el flujo normal
            # --- HARDCODED ANSWERS END ---
            


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
            
            # 3. Obtener opciones disponibles (filtrar ocultas)
            available_options = []
            option_containers = self.browser.page.query_selector_all(
                ".flex.flex-wrap.gap-2 > div, .options-container button, .flex-wrap button, button.group, div.sticky button"
            )
            
            for container in option_containers:
                btn = container if container.evaluate("el => el.tagName === 'BUTTON'") else container.query_selector("button")
                if btn:
                    # Verificar que no esté oculto/usado (opacity-0 = ya clickeado)
                    class_attr = btn.get_attribute("class") or ""
                    
                    # Check parent hierarchy for opacity-0 or pointer-events-none (up to 3 levels)
                    is_disabled = False
                    curr = container
                    for _ in range(3):
                        if not curr: break
                        p_cls = curr.get_attribute("class") or ""
                        if "opacity-0" in p_cls or "pointer-events-none" in p_cls or "invisible" in p_cls:
                            is_disabled = True
                            break
                        curr = curr.query_selector("xpath=..") # Go up
                    
                    if is_disabled:
                        continue

                    if "opacity-0" in class_attr or "pointer-events-none" in class_attr:
                        continue
                    
                    text = btn.inner_text().strip()
                    if text and len(text) > 1 and "Waiting" not in text:
                        if not any(o['text'] == text for o in available_options):
                            available_options.append({"text": text, "element": btn})
            
            if not available_options:
                print("[WARNING] No hay opciones disponibles")
                return False
            
            print(f"[INFO] Opciones: {[o['text'] for o in available_options]}")
            
            options_str = ", ".join([o['text'] for o in available_options])

            # Prepare Context for Learning/Knowledge
            options_text_sig = " | ".join([o['text'] for o in available_options])
            items_text_sig = " | ".join(zone_labels)
            
            # Use standardized context: TITLE (empty here/TODO) || ITEMS || OPTIONS
            # Need to get breadcrumbs if possible, but for drag match usually items + options is unique enough per question text
            # Extract Breadcrumbs if not done yet
            breadcrumbs = ""
            try:
                bc_el = self.browser.page.query_selector("p.tracking-widest.uppercase")
                if bc_el: breadcrumbs = bc_el.inner_text().strip()
            except: pass
            
            # FULL CONTEXT SIGNATURE
            full_context_sig = f"TITLE: {breadcrumbs} || ITEMS: {items_text_sig} || OPTIONS: {options_text_sig}"
            
            # --- LEARNED KNOWLEDGE CHECK (Relocated) ---
            print(f"[DEBUG] Checking knowledge with context: {full_context_sig[:100]}...")
            known_answers = self.try_solve_with_knowledge(question_text, full_context_sig)
            
            if known_answers:
                print(f"[INFO] Aplicando knowledge en Drag/Match: {known_answers}")
                clicks_k = 0
                used_local_indices = set()
                
                # Iterate known answers and apply
                # Assumption: known_answers order matches zone_elements order (0..N)
                for i, ans in enumerate(known_answers):
                    if i >= len(zone_elements): break
                    
                    target_ans = ans.strip().upper().replace("´", "'").replace("`", "'")
                    
                    # Find matching option in available_options
                    best_match = None
                    for opt in available_options:
                        opt_text = opt['text'].upper().replace("´", "'").replace("`", "'")
                        if opt_text == target_ans:
                            best_match = opt
                            break
                    
                    # Fallback containment
                    if not best_match:
                         for opt in available_options:
                            opt_text = opt['text'].upper().replace("´", "'").replace("`", "'")
                            if target_ans in opt_text or opt_text in target_ans:
                                best_match = opt
                                break
                    
                    if best_match:
                        try:
                            # 1. Click Zone
                            zone_elements[i].scroll_into_view_if_needed()
                            zone_elements[i].click(force=True)
                            self.browser.sleep(0.15)
                            
                            # 2. Click Option
                            best_match['element'].scroll_into_view_if_needed()
                            best_match['element'].click(force=True)
                            clicks_k += 1
                            self.browser.sleep(0.2)
                            print(f"[INFO] Learned click: Zone {i+1} -> {best_match['text']}")
                        except Exception as e:
                            print(f"[WARNING] Click error (learned): {e}")
                
                if clicks_k > 0:
                     self.browser.sleep(0.5)
                     self._click_check_button()
                     self.browser.sleep(1.0)
                     # Learn again to reinforce/update
                     self.learn_from_mistake(question_text, full_context_sig)
                     self._click_ok_modal()
                     self.browser.sleep(self.delay)
                     return True
            
            # Construir texto de items para el prompt
            items_text = ""
            for i, label in enumerate(zone_labels):
                items_text += f"{i+1}. {label}\n"
            
            prompt = f"""Pregunta: {question_text}

Hay {len(zone_elements)} items para completar/relacionar.
ITEMS/PREGUNTAS:
{items_text}

OPCIONES DISPONIBLES: {options_str}

Instrucciones:
1. Asigna la opción correcta a cada item.
2. Cada opción debe usarse UNA sola vez (1-a-1).
3. Responde en formato: "1. OPCIÓN"

Respuesta:"""
            
            # 4. Decidir si usar imagen o solo texto
            if num_images > 0:
                # Con imágenes: tomar screenshot
                screenshot = self.browser.screenshot(full_page=True)
                image_part = {
                    "mime_type": "image/png",
                    "data": base64.b64encode(screenshot).decode()
                }
                response = self.solver.model.generate_content([prompt, image_part])
            else:
                # Sin imágenes: solo texto (MÁS RÁPIDO)
                response = self.solver.model.generate_content(prompt)
            
            result = response.text.strip()
            print(f"[DEBUG] Gemini responde:\n{result}")
            
            # 5. Parsear respuestas y hacer clicks
            lines = result.split("\n")
            clicks_done = 0
            
            # Tracking local para evitar loops en esta ejecución
            locally_used_opt_texts = set()
            
            for line in lines:
                match = re.search(r'(\d+)\.\s*(.+)', line)
                if match:
                    idx = int(match.group(1)) - 1
                    answer = match.group(2).strip().lower() # Gemini suele devolver texto exacto
                    
                    if idx < len(zone_elements):
                        # Skip if answer already used locally
                        if answer.upper() in locally_used_opt_texts:
                            print(f"[WARNING] Gemini repitió respuesta '{answer}' para zona {idx+1}. Ignorando.")
                            continue

                        # Buscar la MEJOR coincidencia (Exacta > Contenida más larga > Normalizada)
                        best_match = None
                        best_score = -1
                        
                        # Normalizar respuesta target (Gemini)
                        # "non- defining" -> "non defining" -> "nondefining"
                        ans_norm = answer.replace("-", "").replace(" ", "")
                        
                        # Fallback: Si solo queda una opción y una zona (y no hemos usado nada), forzarla?
                        # Mejor hacerlo al final del loop si no hay match
                        
                        for opt in available_options:
                            # Skip if option used in this run
                            if opt['text'].upper() in locally_used_opt_texts:
                                continue

                            opt_text = opt['text'].lower()
                            opt_norm = opt_text.replace("-", "").replace(" ", "")
                            
                            current_score = -1
                            
                            # 1. Match Exacto
                            if opt_text == answer:
                                current_score = 1000
                            
                            # 2. Match Normalizado (ignora espacios y guiones)
                            elif opt_norm == ans_norm:
                                current_score = 900
                                
                            # 3. Contenido (Score = longitud)
                            elif opt_text in answer:
                                current_score = len(opt_text)
                            elif answer in opt_text:
                                current_score = len(answer)
                            
                            if current_score > best_score:
                                best_score = current_score
                                best_match = opt
                        
                        # Fallback desperate: Si solo queda 1 opción disponible y 1 zona pendiente
                        if not best_match and len(available_options) - len(locally_used_opt_texts) == 1:
                             for opt in available_options:
                                 if opt['text'].upper() not in locally_used_opt_texts:
                                      best_match = opt
                                      best_score = 10 # Low score fallback
                                      print(f"[INFO] Fallback: Forzando única opción restante '{opt['text']}'")
                                      break
                        
                        if best_match:
                            print(f"[INFO] Zone {idx+1} → {best_match['text']} (Score: {best_score})")
                            try:
                                # 1. Click en la ZONA primero
                                zone_elements[idx].scroll_into_view_if_needed()
                                zone_elements[idx].click(force=True)
                                self.browser.sleep(0.15)
                                
                                # 2. Click en la OPCIÓN
                                best_match['element'].scroll_into_view_if_needed()
                                best_match['element'].click(force=True)
                                clicks_done += 1
                                
                                # Mark as used locally
                                locally_used_opt_texts.add(best_match['text'].upper())
                                
                                self.browser.sleep(0.2)
                            except:
                                try:
                                    # Fallback: solo click en opción por texto
                                    self.browser.page.click(f"button:has-text('{best_match['text']}')", timeout=2000)
                                    clicks_done += 1
                                    locally_used_opt_texts.add(best_match['text'].upper())
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
                self.browser.sleep(1.0) # Wait for animation
                self.learn_from_mistake(question_text, full_context_sig)
                self._click_ok_modal()
                
                print(f"[SUCCESS] Pregunta (image drag) respondida")
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
            traceback.print_exc()
            return False

    def solve_image_with_options(self, question_text: str) -> bool:
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
            
            options_str = ", ".join([o['text'] for o in options])
            print(f"[INFO] Opciones encontradas: {options_str}")

            # --- CONTEXT & KNOWLEDGE CHECK ---
            breadcrumbs = ""
            try:
                bc_el = self.browser.page.query_selector("p.tracking-widest.uppercase")
                if bc_el: breadcrumbs = bc_el.inner_text().strip()
            except: pass
            
            full_context_sig = f"TITLE: {breadcrumbs} || OPTIONS: {options_str}"
            
            known_answers = self.try_solve_with_knowledge(question_text, full_context_sig)
            if known_answers:
                target = known_answers[0].upper().replace("´", "'").replace("`", "'")
                print(f"[INFO] Using learned answer: {target}")
                for opt in options:
                    if opt['text'].upper().replace("´", "'").replace("`", "'") == target:
                        opt['element'].click()
                        self.browser.sleep(0.3)
                        self._click_check_button()
                        self.browser.sleep(0.5)
                        self.learn_from_mistake(question_text, full_context_sig)
                        self._click_ok_modal()
                        self.browser.sleep(self.delay)
                        return True
            
            # 3. Crear prompt para Gemini
            prompt = f"""Analiza esta captura de pantalla.

PREGUNTA: {question_text}

OPCIONES DISPONIBLES: {options_str}

Mira la imagen y lee el texto del anuncio cuidadosamente.
Responde SOLO con la opción correcta exacta, nada más:"""
            
            image_part = {
                "mime_type": "image/png",
                "data": base64.b64encode(screenshot).decode()
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
                self.learn_from_mistake(question_text, full_context_sig)
                self._click_ok_modal()
                
                print(f"[SUCCESS] Pregunta (image with options) respondida")
                self.browser.sleep(self.delay)
                return True
            else:
                print(f"[WARNING] No se encontró match para '{answer}'")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error en image with options: {e}")
            traceback.print_exc()
            return False

    def solve_matching_requirements(self, question_text: str) -> bool:
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
                return self.solve_with_screenshot(question_text)
            
            print(f"[INFO] Filas: {[r['label'] for r in rows]}")
            
            # --- CONTEXT & KNOWLEDGE CHECK ---
            jobs_str = ", ".join([r['label'] for r in rows])
            all_opts_str = ", ".join(sorted(list(set([btn_txt for r in rows for btn_txt, _ in r['buttons']]))))

            # Breadcrumbs extraction (if available)
            breadcrumbs = ""
            try:
                bc_el = self.browser.page.query_selector("p.tracking-widest.uppercase")
                if bc_el: breadcrumbs = bc_el.inner_text().strip()
            except: pass

            full_context_sig = f"TITLE: {breadcrumbs} || JOBS: {jobs_str} || OPTIONS: {all_opts_str}"

            print(f"[DEBUG] Checking knowledge with context: {full_context_sig[:100]}...")
            known_answers = self.try_solve_with_knowledge(question_text, full_context_sig)
            
            if known_answers:
                print(f"[INFO] Aplicando knowledge en Matching Requirements: {known_answers}")
                clicks_k = 0
                
                # Format likely: "Job Name: Requirement Text"
                for ans in known_answers:
                    if ":" in ans:
                        k_job, k_req = ans.split(":", 1)
                        k_job = k_job.strip().lower()
                        k_req = k_req.strip().lower()
                        
                        found_click = False
                        for row in rows:
                            if k_job in row['label'].lower() or row['label'].lower() in k_job:
                                for btn_text, btn_el in row['buttons']:
                                    if (k_req in btn_text.lower() or btn_text.lower() in k_req):
                                        try:
                                            btn_el.click()
                                            clicks_k += 1
                                            found_click = True
                                            self.browser.sleep(0.2)
                                        except: pass
                                        break
                            if found_click: break
                
                if clicks_k > 0:
                     self.browser.sleep(0.5)
                     self._click_check_button()
                     self.browser.sleep(1.0)
                     self.learn_from_mistake(question_text, full_context_sig)
                     self._click_ok_modal()
                     self.browser.sleep(self.delay)
                     return True
            
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
                "data": base64.b64encode(screenshot).decode()
            }
            
            response = self.solver.model.generate_content([prompt, image_part])
            result = response.text.strip()
            print(f"[DEBUG] Gemini:\n{result}")
            
            # 4. Parsear y hacer clicks rápidamente
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
            self.learn_from_mistake(question_text, full_context_sig)
            self._click_ok_modal()
            
            print(f"[SUCCESS] Pregunta (matching requirements) respondida")
            self.browser.sleep(self.delay)
            return True
            
        except Exception as e:
            print(f"[ERROR] Error en matching requirements: {e}")
            traceback.print_exc()
            return False

    def solve_text_match(self, question_text: str) -> bool:
        """
        Resuelve preguntas de tipo 'MATCH THE SENTENCE WITH THE RIGHT OPTION'.
        Extrae texto de items y opciones, y usa lógica 1-a-1.
        OPTIMIZADO: Re-busca opciones antes de cada click para evitar stale elements.
        """
        try:
            print("[INFO] Resolviendo pregunta de MATCHING DE TEXTO (1-a-1)...")
            
            # 1. Encontrar zonas de 'Waiting answer'
            zone_elements = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            if not zone_elements:
                print("[WARNING] No se encontraron zonas drop")
                return False
            
            num_zones = len(zone_elements)
            
            # 2. Extraer etiquetas de texto (contexto)
            zone_labels = []
            for i, btn in enumerate(zone_elements):
                try:
                    label = btn.evaluate("""el => {
                        let container = el.closest('.flex-col') || el.closest('.shadow-sm') || el.closest('.border-gray-100') || el.parentElement.parentElement;
                        if (container) {
                            let h2 = container.querySelector('h2');
                            if (h2) return h2.innerText.trim();
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
            
            # 3. Función para obtener opciones DISPONIBLES (re-usable)
            def get_available_options():
                options = []
                seen_texts = set()  # Para evitar duplicados por texto
                
                option_containers = self.browser.page.query_selector_all(
                    ".flex.flex-wrap.gap-2 > div, .options-container button, .flex-wrap button, button.group, div.sticky button"
                )
                
                for container in option_containers:
                    try:
                        btn = container if container.evaluate("el => el.tagName === 'BUTTON'") else container.query_selector("button")
                        if not btn:
                            continue
                        
                        # Verificar que no esté oculto/usado
                        is_hidden = btn.evaluate("""el => {
                            let style = window.getComputedStyle(el);
                            let parent = el.parentElement;
                            let parentStyle = parent ? window.getComputedStyle(parent) : null;
                            return (
                                style.opacity === '0' || 
                                style.pointerEvents === 'none' ||
                                style.display === 'none' ||
                                (parentStyle && parentStyle.opacity === '0')
                            );
                        }""")
                        
                        if is_hidden:
                            continue
                        
                        text = btn.inner_text().strip()
                        if text and len(text) > 1 and "Waiting" not in text:
                            # Evitar duplicados por texto (mantener solo el primero visible)
                            if text.lower() not in seen_texts:
                                seen_texts.add(text.lower())
                                options.append({"text": text, "element": btn})
                    except:
                        continue
                
                return options
            
            # Obtener opciones iniciales para el prompt
            initial_options = get_available_options()
            
            # context for signature
            items_sig = " | ".join([label[:30] for label in zone_labels])
            options_sig = " | ".join(sorted([o['text'] for o in initial_options]))
            
            # Breadcrumbs extraction (if available)
            breadcrumbs = ""
            try:
                bc_el = self.browser.page.query_selector("p.tracking-widest.uppercase")
                if bc_el: breadcrumbs = bc_el.inner_text().strip()
            except: pass

            full_context_sig = f"TITLE: {breadcrumbs} || ITEMS: {items_sig} || OPTIONS: {options_sig}"

            # --- LEARNED KNOWLEDGE CHECK ---
            print(f"[DEBUG] Checking knowledge with context: {full_context_sig[:100]}...")
            known_answers = self.try_solve_with_knowledge(question_text, full_context_sig)
            
            if known_answers:
                print(f"[INFO] Aplicando knowledge en Text Match: {known_answers}")
                clicks_k = 0
                used_texts = set()
                
                # Re-query
                current_opts = get_available_options()
                
                for i, ans in enumerate(known_answers):
                    if i >= num_zones: break
                    
                    target_ans = ans.strip().lower()
                    
                    # Find best match
                    best_match = None
                    for opt in current_opts:
                        opt_txt = opt['text'].lower()
                        if opt_txt in used_texts: continue
                        
                        if opt_txt == target_ans:
                            best_match = opt
                            break
                        elif target_ans in opt_txt or opt_txt in target_ans:
                            best_match = opt # Fallback
                            
                    if best_match:
                         try:
                             # Try clicking exact element first
                             best_match['element'].click()
                             clicks_k += 1
                             used_texts.add(best_match['text'].lower())
                             self.browser.sleep(0.3)
                         except:
                             # Fallback click by text
                             try:
                                 self.browser.page.click(f"button:has-text('{best_match['text']}')")
                                 clicks_k += 1
                                 used_texts.add(best_match['text'].lower())
                             except: pass
                
                if clicks_k > 0:
                     self.browser.sleep(0.5)
                     self._click_check_button()
                     self.browser.sleep(1.0)
                     self.learn_from_mistake(question_text, full_context_sig)
                     self._click_ok_modal()
                     self.browser.sleep(self.delay)
                     return True

            unique_options_str = ", ".join(set([o['text'] for o in initial_options]))
            print(f"[INFO] Opciones únicas: {unique_options_str}")
            
            # 4. Construir Prompt
            items_text = ""
            for i, label in enumerate(zone_labels):
                items_text += f"{i+1}. {label}\n"
            
            prompt = f"""Pregunta de Emparejamiento: {question_text}

ITEMS:
{items_text}

OPCIONES DISPONIBLES: {unique_options_str}

Instrucciones:
1. Asigna UNA opción a cada item.
2. Cada opción debe usarse EXACTAMENTE UNA VEZ (relación 1-a-1).
3. Responde en el formato: "1. OPCIÓN"
4. Las opciones distinguen entre 'a few' (countable), 'few' (plural countable), 'a little' (singular uncountable).
5. GRAMÁTICA:
   - "There are..." -> Busca opciones PLURALES (ej: "two bedrooms...", "a small sofa and a TV" [son 2 cosas]).
   - "There is..." -> Busca opciones SINGULARES (ej: "a small sofa...", "a big bathroom...").
   - "I have..." -> Busca posesiones lógicas (ej: "two windows", "a small bed").

Respuesta:"""

            # 5. Consultar a Gemini
            response = self.solver.model.generate_content(prompt)
            result = response.text.strip()
            print(f"[DEBUG] Gemini responde:\n{result}")
            
            # 6. Parsear respuestas
            answers = []
            for line in result.split("\n"):
                match = re.search(r'(\d+)\.\s*(.+)', line)
                if match:
                    idx = int(match.group(1)) - 1
                    answer = match.group(2).strip()
                    answers.append({"idx": idx, "answer": answer})
            
            # 7. Ejecutar clicks UNO POR UNO (re-queryando cada vez)
            clicks_done = 0
            used_texts = set()  # Trackear por TEXTO, no por índice
            
            for ans in answers:
                q_idx = ans["idx"]
                target_answer = ans["answer"].lower()
                
                if q_idx >= num_zones:
                    continue
                
                # Re-query opciones DISPONIBLES antes de cada click
                current_options = get_available_options()
                
                # Buscar la mejor opción que aún no hemos usado
                best_match = None
                best_score = -1
                
                for opt in current_options:
                    opt_text_lower = opt['text'].lower()
                    
                    # Skip si ya usamos este texto
                    if opt_text_lower in used_texts:
                        continue
                    
                    score = -1
                    if opt_text_lower == target_answer:
                        score = 1000  # Match exacto
                    elif opt_text_lower in target_answer:
                        score = len(opt_text_lower)
                    elif target_answer in opt_text_lower:
                        score = len(target_answer)
                    
                    if score > best_score:
                        best_score = score
                        best_match = opt
                
                if best_match:
                    print(f"[INFO] Item {q_idx+1} → {best_match['text']} (Score: {best_score})")
                    
                    try:
                        best_match['element'].click()
                        clicks_done += 1
                        used_texts.add(best_match['text'].lower())
                        self.browser.sleep(0.3)
                    except Exception as e:
                        # Fallback: buscar por texto
                        print(f"[DEBUG] Click directo falló, intentando por texto...")
                        try:
                            self.browser.page.click(f"button.group:has-text('{best_match['text']}')", timeout=2000)
                            clicks_done += 1
                            used_texts.add(best_match['text'].lower())
                            self.browser.sleep(0.3)
                        except:
                            print(f"[WARNING] Falló click en '{best_match['text']}'")
                else:
                    print(f"[WARNING] No se encontró match disponible para '{target_answer}'")
            
            print(f"[INFO] Clicks realizados: {clicks_done}/{num_zones}")
            
            # 8. Verificar y hacer CHECK
            self.browser.sleep(0.5)
            remaining = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            
            if len(remaining) == 0 and clicks_done > 0:
                self._click_check_button()
                self.browser.sleep(0.5)
                self.learn_from_mistake(question_text, full_context_sig)
                self._click_ok_modal()
                print(f"[SUCCESS] Pregunta (text match) respondida")
            elif clicks_done > 0:
                # Intentar CHECK de todos modos
                self._click_check_button()
                self.browser.sleep(0.5)
                self.learn_from_mistake(question_text, full_context_sig)
                self._click_ok_modal()
            
            self.browser.sleep(self.delay)
            return True

        except Exception as e:
            print(f"[ERROR] Error en text match: {e}")
            traceback.print_exc()
            return False

    def solve_inline_choice(self, question_text: str) -> bool:
        """
        Resuelve preguntas donde hay múltiples oraciones/bloques y cada una tiene sus propias opciones.
        Ejemplo: "CHOOSE THE BEST OPTION: HOLIDAY / VACATION"
        """
        try:
            print("[INFO] Resolviendo pregunta de OPCIÓN EN LÍNEA (Inline Choice)...")
            
            # 1. Encontrar los contenedores de pregutas (cards)
            # Buscamos divs que tengan texto y botones dentro
            potential_cards = self.browser.page.query_selector_all(".bg-white.rounded-xl, .border.rounded-xl, .shadow-sm")
            
            rows_data = []
            
            for card in potential_cards:
                # Verificar si este card tiene botones
                buttons = card.query_selector_all("button")
                # Filtramos botones que sean opciones (no el botón de audio ni iconos)
                option_buttons = [
                    btn for btn in buttons 
                    if len(btn.inner_text().strip()) > 1 # Texto significativo
                    and not btn.query_selector("svg") # No iconos solos
                    and "Waiting" not in btn.inner_text()
                ]
                
                if len(option_buttons) >= 2:
                    # Es una tarjeta de pregunta válida
                    # Extraer el texto de la pregunta (todo el texto del card menos los botones)
                    full_text = card.inner_text()
                    for btn in option_buttons:
                        full_text = full_text.replace(btn.inner_text(), "___") # Reemplazar botón por placeholder
                    
                    question_part = full_text.strip().replace("\n", " ")
                    if len(question_part) < 5: continue # Skip if no text
                    
                    options = []
                    for btn in option_buttons:
                        options.append({"text": btn.inner_text().strip(), "element": btn})
                    
                    rows_data.append({
                        "question": question_part,
                        "options": options
                    })
            
            if not rows_data:
                print("[WARNING] No se encontraron bloques de preguntas inline")
                return False
            
            print(f"[INFO] {len(rows_data)} preguntas encontradas.")
            
            # 2. Construir Prompt
            items_text = ""
            for i, row in enumerate(rows_data):
                opts_str = " / ".join([o['text'] for o in row['options']])
                items_text += f"{i+1}. {row['question']}  OPTIONS: [{opts_str}]\n"
            
            prompt = f"""Responde seleccionando la mejor opción para cada oración.
Contexto General: {question_text}

Preguntas:
{items_text}

Instrucciones:
1. Responde SOLO con la opción correcta textual.
2. Formato: "1. OPCIÓN"
"""
            # 3. Consultar a Gemini o Knowledge
            # Generate Full Context Signature
            # Breadcrumbs extraction (if available)
            breadcrumbs = ""
            try:
                bc_el = self.browser.page.query_selector("p.tracking-widest.uppercase")
                if bc_el: breadcrumbs = bc_el.inner_text().strip()
            except: pass

            full_context_sig = f"TITLE: {breadcrumbs} || ITEMS: {items_text}"

            print(f"[DEBUG] Checking knowledge with context: {full_context_sig[:100]}...")
            known_answers = self.try_solve_with_knowledge(question_text, full_context_sig)
            
            if known_answers:
                # Use known answers
                print(f"[INFO] Usando respuestas aprendida ({len(known_answers)}): {known_answers}")
                clicks = 0
                for i, ans in enumerate(known_answers):
                    if i < len(rows_data):
                        # Clean answer text
                        target_text = ans.replace("´", "'").replace("`", "'").strip().upper()
                        
                        row = rows_data[i]
                        best_btn = None
                        for opt in row['options']:
                            opt_text = opt['text'].upper().replace("´", "'").replace("`", "'").strip()
                            if opt_text == target_text:
                                best_btn = opt['element']
                                break
                        
                        # Fallback: substring match
                        if not best_btn:
                            for opt in row['options']:
                                opt_text = opt['text'].upper().replace("´", "'").replace("`", "'").strip()
                                if target_text in opt_text or opt_text in target_text:
                                    best_btn = opt['element']
                                    break
                                    
                        if best_btn:
                            try:
                                best_btn.click()
                                print(f"[INFO] P {i+1} (Known) -> Click en '{best_btn.inner_text()}'")
                                clicks += 1
                                self.browser.sleep(0.3)
                            except: pass
            else:
                # Use Gemini
                response = self.solver.model.generate_content(prompt)
                result = response.text.strip()
                print(f"[DEBUG] Gemini responde:\n{result}")
                
                # 4. Parsear y Clickar
                lines = result.split("\n")
                clicks = 0
                
                for line in lines:
                    match = re.search(r'(\d+)\.\s*(.+)', line)
                    if match:
                        idx = int(match.group(1)) - 1
                        answer = match.group(2).strip().upper().replace("´", "'").replace("`", "'")
                        
                        if 0 <= idx < len(rows_data):
                            row = rows_data[idx]
                            
                            # Buscar la opción coincidente
                            best_btn = None
                            for opt in row['options']:
                                # Normalizar también el texto del botón para comparación
                                opt_text = opt['text'].upper().replace("´", "'").replace("`", "'").strip()
                                if opt_text == answer or opt_text in answer or answer in opt_text:
                                    best_btn = opt['element']
                                    break
                            
                            if best_btn:
                                try:
                                    best_btn.click()
                                    print(f"[INFO] P {idx+1} -> Click en '{best_btn.inner_text()}'")
                                    clicks += 1
                                    self.browser.sleep(0.3)
                                except:
                                    print(f"[WARNING] Falló click en {idx+1}")
            
            if clicks > 0:
                self.browser.sleep(0.5)
                self._click_check_button()
                
                # Try to learn if mistake happened
                self.browser.sleep(1.0) # Wait for modal animation
                self.learn_from_mistake(question_text, full_context_sig)
                
                self._click_ok_modal()
                print(f"[SUCCESS] Pregunta (Inline Choice) respondida")
                self.browser.sleep(self.delay)
                return True
                
            return False

        except Exception as e:
            print(f"[ERROR] Error en inline choice: {e}")
            return False
