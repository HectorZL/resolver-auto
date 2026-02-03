"""
Selectores CSS centralizados para la plataforma de exámenes UTM.
Actualizados basándose en la estructura real del HTML.
"""

SELECTORS = {
    # Login page
    "email_input": "input[name='mail']",
    "password_input": "input[name='password']",
    "login_button": "button[type='submit']",
    
    # Dashboard - Módulos
    "book_header": "h2#libro1",
    "module_container": ".bg-white.rounded-2xl.shadow-sm",
    "module_title": "span.text-yellow-600",
    "module_progress": "span.text-green-800, span.text-yellow-400",
    "activity_tooltip": ".tooltip",
    "activity_button": ".tooltip button",
    "activity_name": ".circle-text h2",
    "progress_fill": ".bfill",
    
    # Popup de actividad
    "popup_container": ".fixed, [role='dialog']",
    "start_button": "button:has-text('Start')",
    "review_button": "button:has-text('Review')",
    "information_button": "button:has-text('Information')",
    "popup_status": "h2:has-text('Incomplete'), h2:has-text('Complete')",
    
    # Página de preguntas - ACTUALIZADOS
    "question_container": ".flex.flex-col.min-h-screen",
    "question_header": "h2.text-xl, h2.text-2xl, h2.font-bold",
    "question_text": "h2.font-bold.text-gray-800",
    "options_container": "[role='radiogroup']",
    "option_card": ".cardCheck",
    "option_button": ".cardCheck button",
    "selected_option": ".cardCheck[aria-checked='true']",
    "check_button": "button:has-text('Check')",
    "skip_button": "button:has-text('Skip')",
    "next_button": "button:has-text('NEXT'), button:has-text('Continue')",
    
    # Modal de confirmación (SweetAlert2)
    "swal_ok_button": "button.swal2-confirm",
    "swal_container": ".swal2-actions",
    
    # Progreso de pregunta
    "progress_indicator": ".bg-green-500",
    "question_counter": ".text-green-600.text-lg",
    
    # Feedback
    "correct_feedback": ".bg-green-500, [class*='green'], [class*='success']",
    "incorrect_feedback": ".bg-red-500, [class*='red'], [class*='error']",
    
    # Navegación
    "close_button": "button.close, [aria-label='close'], button:has-text('×')",
    "back_button": "button:has-text('Back'), a:has-text('Back')",
    "exit_button": "button[title='Exit']",
}

# Colores para detectar estado de actividad
ACTIVITY_COLORS = {
    "completed": "rgb(5, 150, 105)",      # Verde
    "in_progress": "rgb(217, 119, 6)",    # Naranja/Amarillo
    "not_started": "rgb(248, 113, 113)",  # Rojo
}
