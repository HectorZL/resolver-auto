"""
Módulo para resolver preguntas usando la API de Gemini.
"""

import google.generativeai as genai
import base64
import re
from pathlib import Path


class GeminiSolver:
    """Resuelve preguntas de exámenes usando Gemini API."""
    
    def __init__(self, api_key: str):
        """Inicializa el solver con la API key de Gemini."""
        genai.configure(api_key=api_key)
        # Usar Gemini 3 Flash - el modelo más reciente
        self.model = genai.GenerativeModel('gemini-3-flash-preview')
        print("[INFO] Gemini API configurada con modelo gemini-3-flash-preview")
    
    def analyze_question_with_image(self, screenshot_bytes: bytes, question_text: str = None) -> dict:
        """
        Analiza una pregunta a partir de un screenshot.
        
        Args:
            screenshot_bytes: Bytes del screenshot
            question_text: Texto de la pregunta (opcional, se extrae de la imagen)
            
        Returns:
            dict con 'answer_text' y 'answer_index'
        """
        prompt = """Analiza esta imagen de un examen de inglés y responde:

1. Lee la pregunta que aparece en la imagen
2. Lee todas las opciones disponibles
3. Determina cuál es la respuesta CORRECTA

IMPORTANTE: 
- Si es una pregunta de DEFINICIÓN (What is the definition of X?), busca la definición correcta del término.
- Si es una pregunta de COMPLETAR ORACIONES, elige la palabra que tiene más sentido gramatical y semántico.
- Si es una pregunta de VOCABULARIO, busca el significado correcto.

Responde en el siguiente formato EXACTO:
PREGUNTA: [texto de la pregunta]
OPCIONES: [lista de opciones separadas por |]
RESPUESTA: [texto exacto de la opción correcta]
EXPLICACIÓN: [breve explicación de por qué es correcta]
"""
        
        if question_text:
            prompt += f"\n\nContexto adicional - Pregunta detectada: {question_text}"
        
        try:
            # Crear imagen para Gemini
            image_part = {
                "mime_type": "image/png",
                "data": base64.b64encode(screenshot_bytes).decode()
            }
            
            response = self.model.generate_content([prompt, image_part])
            result_text = response.text
            
            print(f"[DEBUG] Respuesta de Gemini:\n{result_text}")
            
            # Parsear respuesta
            return self._parse_response(result_text)
            
        except Exception as e:
            print(f"[ERROR] Error al analizar con Gemini: {e}")
            return {"answer_text": None, "answer_index": -1, "error": str(e)}
    
    def analyze_question_text_only(self, question: str, options: list) -> dict:
        """
        Analiza una pregunta usando solo texto (sin imagen).
        
        Args:
            question: Texto de la pregunta
            options: Lista de opciones
            
        Returns:
            dict con 'answer_text' y 'answer_index'
        """
        options_text = "\n".join([f"{i+1}. {opt}" for i, opt in enumerate(options)])
        
        prompt = f"""Eres un experto en inglés. Analiza esta pregunta de un examen y selecciona la respuesta correcta.

PREGUNTA: {question}

OPCIONES:
{options_text}

INSTRUCCIONES:
- Si es una pregunta de DEFINICIÓN, busca la definición correcta del término.
- Si es una pregunta de COMPLETAR ORACIONES, elige la palabra que tiene más sentido.
- Si es una pregunta de VOCABULARIO, busca el significado correcto.

Responde en el siguiente formato EXACTO:
RESPUESTA: [número de la opción correcta (1, 2, 3, o 4)]
TEXTO: [texto exacto de la opción]
EXPLICACIÓN: [breve explicación]
"""
        
        try:
            response = self.model.generate_content(prompt)
            result_text = response.text
            
            print(f"[DEBUG] Respuesta de Gemini:\n{result_text}")
            
            # Parsear respuesta
            answer_match = re.search(r'RESPUESTA:\s*(\d+)', result_text)
            text_match = re.search(r'TEXTO:\s*(.+)', result_text)
            
            answer_index = int(answer_match.group(1)) - 1 if answer_match else -1
            answer_text = text_match.group(1).strip() if text_match else options[answer_index] if answer_index >= 0 else None
            
            return {
                "answer_text": answer_text,
                "answer_index": answer_index,
                "raw_response": result_text
            }
            
        except Exception as e:
            print(f"[ERROR] Error al analizar con Gemini: {e}")
            return {"answer_text": None, "answer_index": -1, "error": str(e)}
    
    def _parse_response(self, response_text: str) -> dict:
        """Parsea la respuesta de Gemini."""
        result = {
            "answer_text": None,
            "answer_index": -1,
            "question": None,
            "options": [],
            "explanation": None,
            "raw_response": response_text
        }
        
        # Extraer respuesta
        answer_match = re.search(r'RESPUESTA:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if answer_match:
            result["answer_text"] = answer_match.group(1).strip()
        
        # Extraer pregunta
        question_match = re.search(r'PREGUNTA:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if question_match:
            result["question"] = question_match.group(1).strip()
        
        # Extraer opciones
        options_match = re.search(r'OPCIONES:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if options_match:
            result["options"] = [opt.strip() for opt in options_match.group(1).split('|')]
        
        # Extraer explicación
        explanation_match = re.search(r'EXPLICACIÓN:\s*(.+?)(?:\n|$)', response_text, re.IGNORECASE)
        if explanation_match:
            result["explanation"] = explanation_match.group(1).strip()
        
        return result
    
    def analyze_unknown_question(self, screenshot_bytes: bytes, html_content: str, question_text: str = None) -> dict:
        """
        Analiza una pregunta desconocida usando screenshot + código HTML.
        
        Args:
            screenshot_bytes: Bytes del screenshot de la página
            html_content: HTML del área de la pregunta
            question_text: Texto de la pregunta (opcional)
        
        Returns:
            dict con instrucciones de cómo resolver la pregunta
        """
        prompt = """Eres un experto en automatización web y exámenes de inglés. 
Analiza la imagen del examen Y el código HTML para entender el tipo de pregunta y cómo resolverla.

ANALIZA:
1. La imagen muestra la pregunta visualmente
2. El HTML te muestra los elementos interactivos disponibles

IDENTIFICA:
- Tipo de pregunta (drag & drop, ordenar, emparejar, audio, video, etc.)
- Elementos interactivos (botones, inputs, áreas arrastrables, etc.)
- Selectores CSS útiles para interactuar con los elementos

RESPONDE en el siguiente formato EXACTO:

TIPO_PREGUNTA: [tipo identificado]
DESCRIPCION: [cómo funciona esta pregunta]
RESPUESTA_CORRECTA: [la respuesta correcta si puedes determinarla]
ESTRATEGIA: [pasos específicos para resolver la pregunta]
SELECTORES: [selectores CSS o texto para encontrar elementos, separados por |]
ACCIONES: [lista de acciones: CLICK, DRAG, TYPE, SELECT - separadas por |]

Si hay opciones o respuestas visibles, incluye cuál es la correcta.
"""
        
        # Agregar contexto de HTML (limitado para no exceder tokens)
        html_truncated = html_content[:5000] if len(html_content) > 5000 else html_content
        prompt += f"\n\nCÓDIGO HTML DE LA PÁGINA:\n```html\n{html_truncated}\n```"
        
        if question_text:
            prompt += f"\n\nTEXTO DE LA PREGUNTA DETECTADO: {question_text}"
        
        try:
            # Crear imagen para Gemini
            image_part = {
                "mime_type": "image/png",
                "data": base64.b64encode(screenshot_bytes).decode()
            }
            
            response = self.model.generate_content([prompt, image_part])
            result_text = response.text
            
            print(f"[DEBUG] Respuesta de Gemini (análisis desconocido):\n{result_text}")
            
            # Parsear la respuesta estructurada
            result = {
                "question_type": None,
                "description": None,
                "answer": None,
                "strategy": None,
                "selectors": [],
                "actions": [],
                "raw_response": result_text
            }
            
            # Extraer campos
            type_match = re.search(r'TIPO_PREGUNTA:\s*(.+?)(?:\n|$)', result_text, re.IGNORECASE)
            if type_match:
                result["question_type"] = type_match.group(1).strip()
            
            desc_match = re.search(r'DESCRIPCION:\s*(.+?)(?:\n|$)', result_text, re.IGNORECASE)
            if desc_match:
                result["description"] = desc_match.group(1).strip()
            
            answer_match = re.search(r'RESPUESTA_CORRECTA:\s*(.+?)(?:\n|$)', result_text, re.IGNORECASE)
            if answer_match:
                result["answer"] = answer_match.group(1).strip()
            
            strategy_match = re.search(r'ESTRATEGIA:\s*(.+?)(?:\n|$)', result_text, re.IGNORECASE)
            if strategy_match:
                result["strategy"] = strategy_match.group(1).strip()
            
            selectors_match = re.search(r'SELECTORES:\s*(.+?)(?:\n|$)', result_text, re.IGNORECASE)
            if selectors_match:
                result["selectors"] = [s.strip() for s in selectors_match.group(1).split('|')]
            
            actions_match = re.search(r'ACCIONES:\s*(.+?)(?:\n|$)', result_text, re.IGNORECASE)
            if actions_match:
                result["actions"] = [a.strip() for a in actions_match.group(1).split('|')]
            
            return result
            
        except Exception as e:
            print(f"[ERROR] Error al analizar pregunta desconocida con Gemini: {e}")
            return {"question_type": None, "answer": None, "error": str(e)}


def test_gemini(api_key: str):
    """Test rápido de la API de Gemini."""
    solver = GeminiSolver(api_key)
    
    # Test con pregunta de texto
    result = solver.analyze_question_text_only(
        question="What is the definition of BAT?",
        options=[
            "The member of a team that is in charge of all the other players while playing the sport.",
            "The things that are needed to be able to play a sport.",
            "A thin long object that is held and used to hit another object, often a ball.",
            "A game in which a club is used to hit a small ball into a hole in the ground."
        ]
    )
    
    print(f"\n[TEST] Resultado: {result}")
    return result


if __name__ == "__main__":
    import json
    with open("config.json", "r") as f:
        config = json.load(f)
    
    test_gemini(config["gemini_api_key"])
