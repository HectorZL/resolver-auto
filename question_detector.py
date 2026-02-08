
from selectors import SELECTORS
import re

class QuestionDetector:
    """Detects the type of question on the current page."""
    
    def __init__(self, browser):
        """
        Initialize with a browser controller instance.
        
        Args:
            browser: BrowserController instance
        """
        self.browser = browser

    def get_question_text(self) -> str:
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
    
    def detect_question_type(self) -> str:
        """Detecta el tipo de pregunta en la página."""
        try:
            # Verificar si hay cardCheck (opción múltiple tradicional, con o sin audio)
            # NOTA: Las preguntas de listening también usan cardCheck, así que no necesitamos
            # un tipo separado. El solver de multiple_choice detectará y procesará el audio.
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

            # Verificar si hay drag & drop con botones "Waiting answer..." (o zonas ya llenas pero con el mismo estilo)
            waiting_btns = self.browser.page.query_selector_all("button:has-text('Waiting answer')")
            opt_btns = self.browser.page.query_selector_all("button.opt-1") # Clase común en estas zonas
            
            if len(waiting_btns) > 0 or (len(opt_btns) >= 3 and self.browser.page.query_selector("img")):
                h2_text = self.get_question_text().lower()
                is_text_match = (
                    ("match the sentence" in h2_text and "option" in h2_text) or
                    ("complete the questions" in h2_text and "verbs" in h2_text) or
                    ("choose the best option" in h2_text) or
                    ("survey" in h2_text)
                )
                if is_text_match and not self.browser.page.query_selector("img[alt='Descripción de la imagen']"):
                    return "text_match"
                
                # Si hay muchas imágenes y botones "opt-1", es draging
                if "drag" in h2_text or "match" in h2_text or len(opt_btns) > 4:
                    return "image_drag_match"
                
                return "image_drag_match"
            
            # Verificar inline choice (cards con botones de opciones) - SOLO si no hay "Waiting answer"
            if "choose the best option" in self.get_question_text().lower():
                return "inline_choice"
            
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
