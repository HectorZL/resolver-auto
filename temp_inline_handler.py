    def _solve_inline_choice(self, question_text: str) -> bool:
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
                ]
                
                if len(option_buttons) >= 2:
                    # Es una tarjeta de pregunta válida
                    # Extraer el texto de la pregunta (todo el texto del card menos los botones)
                    full_text = card.inner_text()
                    for btn in option_buttons:
                        full_text = full_text.replace(btn.inner_text(), "___") # Reemplazar botón por placeholder
                    
                    question_part = full_text.strip().replace("\n", " ")
                    
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
            # 3. Consultar a Gemini
            response = self.solver.model.generate_content(prompt)
            result = response.text.strip()
            print(f"[DEBUG] Gemini responde:\n{result}")
            
            # 4. Parsear y Clickar
            import re
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
                            opt_text = opt['text'].upper()
                            if opt_text == answer or opt_text in answer or answer in opt_text:
                                best_btn = opt['element']
                                break
                        
                        if best_btn:
                            try:
                                print(f"[INFO] P {idx+1} -> Click en '{best_btn.inner_text()}'")
                                best_btn.click()
                                clicks += 1
                                self.browser.sleep(0.2)
                            except:
                                print(f"[WARNING] Falló click en {idx+1}")
            
            if clicks > 0:
                self.browser.sleep(0.5)
                self._click_check_button()
                self._click_ok_modal()
                self.questions_answered += 1
                return True
                
            return False

        except Exception as e:
            print(f"[ERROR] Error en inline choice: {e}")
            import traceback
            traceback.print_exc()
            return False
