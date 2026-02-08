"""
Script de prueba para verificar que los módulos se detectan correctamente
"""
from browser_handler import BrowserHandler
from selectors import SELECTORS

# Iniciar navegador
browser = BrowserHandler(headless=False)
browser.start()

# Navegar al dashboard (asumiendo que ya estás logueado)
browser.navigate("https://aulaslenguas.utm.edu.ec:8443/dashboard")
browser.sleep(3)

# Verificar URL actual
print(f"\n[DEBUG] URL actual: {browser.page.url}")

# Buscar módulos
modules = browser.page.query_selector_all(SELECTORS["module_container"])
print(f"[DEBUG] Encontrados {len(modules)} contenedores de módulos\n")

for idx, module in enumerate(modules):
    title_el = module.query_selector(SELECTORS["module_title"])
    if title_el:
        title = title_el.inner_text()
        print(f"[DEBUG] Módulo {idx}: '{title}'")
        
        # Buscar progreso
        spans = module.query_selector_all("span")
        for span in spans:
            text = span.inner_text()
            if "%" in text and "completed" in text.lower():
                print(f"  → Progreso: {text}")
                break
    print()

print("\n[INFO] Presiona Enter para cerrar...")
input()
browser.close()
