"""
Controlador del navegador - Intenta CDP, fallback a launch normal con stealth.
"""

import os
import time
import subprocess
import socket
from pathlib import Path
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

# Stealth
try:
    from playwright_stealth import stealth_sync
except ImportError:
    try:
        from playwright_stealth import Stealth
        def stealth_sync(page):
            Stealth().apply_stealth_sync(page)
    except ImportError:
        def stealth_sync(page):
            pass


def is_port_open(port, host='127.0.0.1'):
    """Verifica si un puerto está abierto."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    result = sock.connect_ex((host, port))
    sock.close()
    return result == 0


def kill_edge_processes():
    """Cierra todos los procesos de Edge."""
    print("[INFO] Cerrando todos los procesos de Edge...")
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "msedge.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)  # Esperar que se cierren
        print("[INFO] Procesos de Edge cerrados")
    except Exception as e:
        print(f"[WARNING] No se pudieron cerrar procesos Edge: {e}")


class BrowserController:
    """Controlador con múltiples estrategias de conexión."""
    
    def __init__(self, headless: bool = False):
        self.headless = headless
        self.playwright = None
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.edge_process = None
        
    def start(self) -> Page:
        """Inicia Edge - intenta CDP primero, luego fallback."""
        if self.playwright is None:
             self.playwright = sync_playwright().start()
        
        # Si ya tenemos browser y page activos, verificar si siguen vivos
        if self.browser and self.page:
            try:
                # Simple check taking title or url to see if connection is alive
                self.page.url 
                print("[INFO] Navegador ya activo, reutilizando sesión.")
                return self.page
            except:
                print("[WARNING] Sesión anterior muerta, reiniciando...")
                self.close()
                if self.playwright is None:
                     self.playwright = sync_playwright().start()
        
        # Cerrar todos los Edge existentes
        kill_edge_processes()
        
        # Ruta de Edge
        edge_path = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
        if not os.path.exists(edge_path):
            edge_path = r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"
        
        print(f"[INFO] Usando Edge en: {edge_path}")
        
        debug_port = 9222
        
        # Verificar si ya hay un Edge con debugging
        if is_port_open(debug_port):
            print(f"[INFO] Detectado Edge existente en puerto {debug_port}")
            try:
                self.browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
                contexts = self.browser.contexts
                if contexts:
                    self.context = contexts[0]
                    pages = self.context.pages
                    self.page = pages[0] if pages else self.context.new_page()
                else:
                    self.context = self.browser.new_context()
                    self.page = self.context.new_page()
                print("[SUCCESS] Conectado a Edge existente!")
                return self.page
            except Exception as e:
                print(f"[WARNING] Error conectando a Edge existente: {e}")
        
        # Intentar lanzar Edge con debugging
        print("[INFO] Lanzando Edge con debugging...")
        print("[INFO] Si ya tienes Edge abierto, ciérralo primero.")
        
        try:
            # Lanzar Edge
            cmd = [
                edge_path,
                f"--remote-debugging-port={debug_port}",
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
                "--start-maximized",
            ]
            
            self.edge_process = subprocess.Popen(
                cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Esperar que el puerto esté disponible
            print("[INFO] Esperando que Edge inicie...")
            for i in range(20):  # Hasta 20 segundos
                if is_port_open(debug_port):
                    print(f"[INFO] Puerto {debug_port} abierto!")
                    break
                time.sleep(1)
                if i % 5 == 0:
                    print(f"[INFO] Esperando... ({i}s)")
            
            if is_port_open(debug_port):
                print(f"[INFO] Conectando via CDP...")
                self.browser = self.playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{debug_port}")
                contexts = self.browser.contexts
                if contexts:
                    self.context = contexts[0]
                    pages = self.context.pages
                    self.page = pages[0] if pages else self.context.new_page()
                else:
                    self.context = self.browser.new_context()
                    self.page = self.context.new_page()
                print("[SUCCESS] Conectado via CDP!")
                return self.page
            else:
                raise Exception("Puerto no disponible")
                
        except Exception as e:
            print(f"[WARNING] CDP falló: {e}")
            print("[INFO] Usando método alternativo (launch normal)...")
            
            # Fallback: launch normal con stealth
            browser_args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--disable-web-security",
                "--disable-features=IsolateOrigins,site-per-process",
                "--window-size=1920,1080",
                "--start-maximized",
            ]
            
            self.browser = self.playwright.chromium.launch(
                headless=self.headless,
                executable_path=edge_path,
                args=browser_args
            )
            
            self.context = self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0",
                locale="es-ES",
                timezone_id="America/Guayaquil",
                permissions=["geolocation"],
                geolocation={"latitude": -2.1894, "longitude": -79.8891},
                extra_http_headers={
                    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Upgrade-Insecure-Requests": "1",
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Sec-Fetch-User": "?1"
                },
                ignore_https_errors=True,
            )
            
            self.page = self.context.new_page()
            
            try:
                stealth_sync(self.page)
            except:
                pass
        
        print("[INFO] Navegador Edge listo")
        return self.page
    
    def goto(self, url: str, wait_until: str = "domcontentloaded"):
        """Navega a una URL."""
        print(f"[INFO] Navegando a: {url}")
        self.page.goto(url, wait_until=wait_until, timeout=120000)
        time.sleep(3)
    
    def wait_for_form_ready(self, email_selector: str, timeout: int = 30):
        """Espera a que el formulario esté listo o detecta si ya está logueado."""
        print("[INFO] Verificando estado de login...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                # Verificar si ya está logueado (dashboard visible)
                if "dashboard" in self.page.url.lower():
                    print("[INFO] Ya está logueado (dashboard detectado)")
                    return "logged_in"
                
                # Verificar si el formulario está visible
                if self.page.locator(email_selector).is_visible(timeout=2000):
                    print("[SUCCESS] Formulario de login detectado!")
                    return True
            except:
                pass
            
            time.sleep(1)
            elapsed = int(time.time() - start_time)
            if elapsed % 5 == 0 and elapsed > 0:
                print(f"[INFO] Esperando... ({elapsed}s)")
        
        # Si no encontró formulario, verificar si está en dashboard
        if "dashboard" in self.page.url.lower():
            print("[INFO] Ya está logueado")
            return "logged_in"
        
        print("[ERROR] Timeout esperando")
        return False
    
    def screenshot(self, path: str = None, full_page: bool = False) -> bytes:
        """Toma screenshot con optimizaciones para evitar timeouts de fuentes."""
        try:
            # Reducido timeout a 15s y disabled animations para evitar espera de fuentes
            if path:
                self.page.screenshot(
                    path=path, 
                    full_page=full_page, 
                    timeout=15000,
                    animations="disabled"
                )
            return self.page.screenshot(
                full_page=full_page, 
                timeout=15000,
                animations="disabled"
            )
        except Exception as e:
            print(f"[WARNING] Screenshot timeout o error: {e}")
            # Retornar None para que el solver use solo texto
            return None
    
    def click(self, selector: str, timeout: int = 30000):
        self.page.click(selector, timeout=timeout)
        print(f"[INFO] Click en: {selector}")
    
    def click_text(self, text: str, timeout: int = 30000):
        self.page.get_by_text(text, exact=False).first.click(timeout=timeout)
        print(f"[INFO] Click en texto: {text}")
    
    def fill(self, selector: str, value: str):
        self.page.fill(selector, value)
    
    def get_text(self, selector: str) -> str:
        element = self.page.query_selector(selector)
        return element.inner_text() if element else ""
    
    def get_all_texts(self, selector: str) -> list:
        elements = self.page.query_selector_all(selector)
        return [el.inner_text() for el in elements]
    
    def wait_for_selector(self, selector: str, timeout: int = 30000, state: str = "visible"):
        self.page.wait_for_selector(selector, timeout=timeout, state=state)
    
    def wait_for_load(self, timeout: int = 10000):
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except:
            pass
    
    def is_visible(self, selector: str) -> bool:
        try:
            return self.page.is_visible(selector)
        except:
            return False
    
    def exists(self, selector: str) -> bool:
        return self.page.query_selector(selector) is not None
    
    def get_attribute(self, selector: str, attribute: str) -> str:
        element = self.page.query_selector(selector)
        return element.get_attribute(attribute) if element else ""
    
    def evaluate(self, script: str):
        return self.page.evaluate(script)
    
    def sleep(self, seconds: float):
        time.sleep(seconds)
    
    def get_page_html(self, selector: str = None) -> str:
        """Obtiene el HTML de la página o de un selector específico."""
        try:
            if selector:
                element = self.page.query_selector(selector)
                return element.inner_html() if element else ""
            return self.page.content()
        except Exception as e:
            print(f"[ERROR] Error obteniendo HTML: {e}")
            return ""
    
    def close(self):
        if self.context:
            try:
                self.context.close()
            except:
                pass
        if self.browser:
            try:
                self.browser.close()
            except:
                pass
        if self.playwright:
            self.playwright.stop()
        print("[INFO] Desconectado del navegador")
