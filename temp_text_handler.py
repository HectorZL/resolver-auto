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
                if not btn and container.tag_name == "BUTTON":
                    btn = container
                
                # Si sigue sin encontrarse, buscar padre botón
                if not btn:
                     btn = container.evaluate_handle("el => el.closest('button')").as_element()

                if btn:
                    text = btn.inner_text().strip()
                    if text and len(text) > 2 and "Waiting" not in text:
                         # Evitar duplicados? No, aquí necesitamos todos los botones físicos aunque tengan mismo texto
                         # Pero en este HTML parece que las opciones son únicas visually en el banco.
                         if not any(o['text'] == text for o in available_options):
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
