from playwright.sync_api import Page

def update_pages_js(page: Page, container, data, goodreads_total_pages: int):
    """
    Función auxiliar para actualizar las páginas manipulando el DOM directamente con JS.
    Aísla la lógica compleja de interacción con el formulario de Goodreads.
    """
    try:
        # Calcular página objetivo en Python (más seguro/limpio que en JS)
        final_page = data.pagina_actual
        if goodreads_total_pages > 0 and data.total_paginas > 0:
            proporcion = data.pagina_actual / data.total_paginas
            final_page = int(proporcion * goodreads_total_pages)
            final_page = min(final_page, goodreads_total_pages)
            print(f"INFO: Calculando página: {data.pagina_actual}/{data.total_paginas} -> {final_page} (Total GR: {goodreads_total_pages})")
            
        # Script JS de acción con logging detallado
        result = page.evaluate("""
            ([container, pageValue]) => {
                console.log('DEBUG: Iniciando update_pages_js con pageValue:', pageValue);
                
                const pageInput = container.querySelector('input[name="user_status[page]"]');
                console.log('DEBUG: pageInput encontrado?', !!pageInput);
                
                const percentInput = container.querySelector('input[name="user_status[percent]"]');
                console.log('DEBUG: percentInput encontrado?', !!percentInput);
                
                const submitBtn = container.querySelector('button.gr-form--compact__submitButton');
                console.log('DEBUG: submitBtn encontrado?', !!submitBtn);
                
                // MODO HEADLESS: Manipular DOM directamente (el toggle click no funciona)
                // En headless, el JS de Goodreads no se ejecuta, así que cambiamos el DOM manualmente
                console.log('DEBUG: 🔄 Manipulando DOM directamente para modo páginas...');
                
                // 1. Buscar ambos divs de progreso (páginas y porcentaje)
                const progressDivs = container.querySelectorAll('.wtrNewUserStatusProgress');
                let pageDiv = null;
                let percentDiv = null;
                
                for (let div of progressDivs) {
                    const hasPageInput = div.querySelector('input[name="user_status[page]"]');
                    const hasPercentInput = div.querySelector('input[name="user_status[percent]"]');
                    
                    if (hasPageInput) {
                        pageDiv = div;
                    } else if (hasPercentInput) {
                        percentDiv = div;
                    }
                }
                
                console.log('DEBUG: pageDiv encontrado?', !!pageDiv);
                console.log('DEBUG: percentDiv encontrado?', !!percentDiv);
                
                // 2. FORZAR modo páginas: mostrar div de páginas y ocultar div de porcentaje
                if (pageDiv) {
                    pageDiv.style.display = 'block';
                    pageDiv.style.visibility = 'visible';
                    pageDiv.style.opacity = '1';
                    console.log('DEBUG: ✅ Div de PÁGINAS forzado a VISIBLE');
                }
                
                if (percentDiv) {
                    percentDiv.style.display = 'none';
                    console.log('DEBUG: ✅ Div de PORCENTAJE forzado a OCULTO');
                }
                
                // 3. Habilitar el input de páginas
                if (pageInput) {
                    pageInput.disabled = false;
                    pageInput.removeAttribute('disabled');
                    console.log('DEBUG: ✅ pageInput habilitado (disabled=false)');
                }
                
                // 4. CRÍTICO: Deshabilitar el input de PORCENTAJE para que NO se envíe al servidor!
                // Cuando un input está disabled, el navegador NO lo incluye en el form submit
                if (percentInput) {
                    percentInput.disabled = true;
                    percentInput.setAttribute('disabled', 'disabled');
                    console.log('DEBUG: ✅ percentInput DESHABILITADO (no se enviará al servidor)');
                }
                
                // 5. Validar que el input de páginas esté habilitado
                if (pageInput && pageInput.disabled) {
                    console.error('ERROR: pageInput SIGUE deshabilitado después de manipulación!');
                    return { success: false, error: 'No se pudo habilitar el input de páginas' };
                }
                
                console.log('DEBUG: ✅ DOM manipulado correctamente - modo páginas activado');
                
                // Llenar valor
                if (pageInput) {
                    pageInput.value = pageValue;
                    console.log('DEBUG: ✅ Valor asignado al input de páginas:', pageInput.value);
                    // Disparar eventos para que Frameworks reactivos detecten el cambio
                    pageInput.dispatchEvent(new Event('change', { bubbles: true }));
                    pageInput.dispatchEvent(new Event('input', { bubbles: true }));
                } else {
                    return { success: false, error: 'Input de página no encontrado' };
                }
                
                // Submit
                if (submitBtn) {
                    console.log('DEBUG: Haciendo click en submit button');
                    submitBtn.click();
                    return { success: true };
                } else {
                    return { success: false, error: 'Botón submit no encontrado' };
                }
            }
        """, [container, str(final_page)])
        
        if result.get('success'):
            print(f"SUCCESS: Progreso actualizado a página {final_page}")
            page.wait_for_timeout(2000)
        else:
            print(f"ERROR: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"ERROR actualizando páginas (JS): {str(e)}")

def prepare_form_js(page: Page, container):
    """
    Prepara el formulario: lo hace visible y extrae info inicial (total paginas).
    Retorna un diccionario con {success: bool, totalPages: int, error: str}
    """
    js_script = """
    (container) => {
        console.log('DEBUG prepare_form: Iniciando...');
        
        const formContainer = container.querySelector('.wtrFloatingBox.wtrNewUserStatus');
        console.log('DEBUG prepare_form: formContainer encontrado?', !!formContainer);
        
        if (!formContainer) return { success: false, error: "Contenedor de formulario no encontrado" };
        
        // 1. Forzar visibilidad del formulario
        formContainer.style.display = 'block';
        formContainer.style.visibility = 'visible';
        formContainer.style.opacity = '1';
        console.log('DEBUG prepare_form: Formulario forzado a visible');
        
        // 2. Buscar input de páginas para validar
        const pageInput = container.querySelector('input[name="user_status[page]"]');
        console.log('DEBUG prepare_form: pageInput encontrado?', !!pageInput);
        
        if (!pageInput) return { success: false, error: "Input de página no encontrado" };
        
        // 3. Extraer total de páginas de Goodreads - BUSCAR EN EL DIV CORRECTO
        let totalPages = 0;
        
        // Buscar específicamente en el div que contiene el input de páginas
        const progressDivs = container.querySelectorAll('.wtrNewUserStatusProgress');
        for (let div of progressDivs) {
            const hasPageInput = div.querySelector('input[name="user_status[page]"]');
            if (hasPageInput) {
                // FORZAR VISIBILIDAD del div para poder leer su texto
                div.style.display = 'block';
                div.style.visibility = 'visible';
                
                // Usar textContent que funciona incluso en elementos ocultos
                const divText = div.textContent || "";
                console.log('DEBUG prepare_form: Texto del div con páginas:', divText);
                
                // Regex corregida (sin doble escape - estamos en JS, no Python string)
                const match = divText.match(/of\s+(\d+)/);
                if (match) {
                    totalPages = parseInt(match[1]);
                    console.log('DEBUG prepare_form: ✅ Total páginas extraído:', totalPages);
                    break;
                }
            }
        }
        
        if (totalPages === 0) {
            console.log('WARNING prepare_form: No se pudo extraer total de páginas, usando fallback...');
            // Fallback: buscar en todo el HTML del container (incluyendo elementos ocultos)
            const html = container.innerHTML || "";
            const match = html.match(/of\s+(\d+)\./);
            if (match) {
                totalPages = parseInt(match[1]);
                console.log('DEBUG prepare_form: Total páginas (fallback HTML):', totalPages);
            }
        }
        
        return { success: true, totalPages: totalPages };
    }
    """
    result = page.evaluate(js_script, container)
    print(f"DEBUG prepare_form_js result: {result}")
    return result
