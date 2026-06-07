"""
BrowserController - Each instance launches/manages its OWN Edge process via CDP.

Each ``BrowserController`` manages its own Edge browser OS process and its own
Playwright connection with a dedicated debug port.  This is the pre-BrowserManager
architecture restored: one browser per agent, full isolation.

Usage::

    bc = BrowserController(headless=False, agent_id="Agent-1")
    page = bc.start()       # launches/connects browser, creates page
    bc.goto("https://...")
    bc.close()              # closes this instance's browser + playwright
"""

import atexit
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Optional

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# ── Stealth (optional, applied per page) ───────────────────────────────────────

try:
    from playwright_stealth import stealth_sync
except ImportError:
    try:
        from playwright_stealth import Stealth

        def stealth_sync(page):  # type: ignore[misc]
            Stealth().apply_stealth_sync(page)
    except ImportError:

        def stealth_sync(page):  # type: ignore[misc]
            pass

# ── Constants ──────────────────────────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parent

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
)

BASE_CDP_PORT = 9222


# ═══════════════════════════════════════════════════════════════════════════════
# Module-level helpers
# ═══════════════════════════════════════════════════════════════════════════════


def is_port_open(port: int, host: str = "127.0.0.1") -> bool:
    """Return ``True`` if *port* is accepting TCP connections on *host*."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(1)
    try:
        return sock.connect_ex((host, port)) == 0
    finally:
        sock.close()


def kill_edge_processes() -> None:
    """Kill **all** ``msedge.exe`` processes (forceful cleanup at shutdown).

    .. warning::

        **NUCLEAR OPTION.**  This kills **every** running ``msedge.exe`` on the
        machine, including user-launched Edge instances that have nothing to do
        with this script.  Use only at global shutdown when you are certain no
        other Edge windows are important.  There is **no** process-level
        filtering (e.g. by command-line args) in this implementation.
    """
    try:
        subprocess.run(
            ["taskkill", "/F", "/IM", "msedge.exe"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )
        time.sleep(1)
        print("[BrowserController] Procesos Edge terminados.")
    except Exception as exc:
        print(f"[BrowserController] Error al cerrar Edge: {exc}")


def _find_edge() -> str:
    """Return the first valid Microsoft Edge executable path."""
    for path in EDGE_PATHS:
        if os.path.exists(path):
            return path
    raise FileNotFoundError(
        "Microsoft Edge no encontrado. "
        "Verifica la instalación en: " + " o ".join(EDGE_PATHS)
    )


def _ensure_dir(path: Path) -> None:
    """Create the directory (and parents) if it does not exist."""
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(
            f"[BrowserController] No se pudo crear el directorio "
            f"'{path.resolve()}': {exc}"
        ) from exc


# ═══════════════════════════════════════════════════════════════════════════════
# BrowserController
# ═══════════════════════════════════════════════════════════════════════════════


class BrowserController:
    """Controller that launches and manages its own Edge browser process.

    Each instance uses a dedicated debug port (Agent-Solo → 9222,
    Agent-1 → 9223, Agent-2 → 9224, ...) and owns its full Playwright
    lifecycle.  No shared ``BrowserManager``.
    """

    def __init__(self, headless: bool = False, agent_id: Optional[str] = None):
        self.headless = headless
        self.agent_id = agent_id or "Agent-Solo"

        # Each agent gets a unique debug port
        self.debug_port = self._calculate_debug_port()

        # Owned resources (not shared)
        self._playwright: Optional[sync_playwright.Playwright] = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._process: Optional[subprocess.Popen] = None
        self.page: Optional[Page] = None

        atexit.register(self._atexit_cleanup)

    # ── Port calculation ───────────────────────────────────────────────────────

    def _calculate_debug_port(self) -> int:
        """Derive the CDP debug port from the agent id.

        ``Agent-Solo`` → 9222
        ``Agent-1``    → 9223
        ``Agent-2``    → 9224
        ...
        """
        if self.agent_id == "Agent-Solo":
            return BASE_CDP_PORT

        try:
            num = int(self.agent_id.split("-")[-1])
            return BASE_CDP_PORT + num
        except (ValueError, IndexError):
            return BASE_CDP_PORT

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    def start(self) -> Page:
        """Obtain a ``Page`` connected to this instance's Edge browser.

        Behaviour:
        1. Start Playwright if not already running.
        2. If we already hold a live page, health-check (URL + content) and
           reuse it.
        3. If stale, close and re-acquire.
        4. Try CDP: check whether the agent's debug port is open; connect.
        5. If the port is closed, launch Edge with ``--remote-debugging-port``.
        6. If CDP connection fails, fall back to ``playwright.chromium.launch()``.
        """
        # ── 1. Ensure Playwright is started ──
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        # ── 2. Reuse live page if healthy ──
        if self.page is not None:
            try:
                _ = self.page.url  # cheap alive check
                content = self.page.content()
                if content and len(content) > 100:
                    print(f"[{self.agent_id}] Página ya activa, reutilizando.")
                    self._disable_animations()
                    return self.page

                print(f"[{self.agent_id}] Página activa pero vacía, recargando...")
                self.page.goto("about:blank")
                return self.page
            except Exception:
                # Stale page - tear down and re-acquire
                self.close()

        # ── 3. Try CDP (if port is already open) ──
        if is_port_open(self.debug_port):
            print(
                f"[{self.agent_id}] Edge ya disponible en puerto "
                f"{self.debug_port}, conectando..."
            )
            try:
                self._connect_via_cdp()
                self._create_page()
                return self.page
            except Exception as exc:
                print(
                    f"[{self.agent_id}] Error conectando via CDP: {exc}"
                )
                self._cleanup_resources()

        # ── 4. Launch Edge with CDP ──
        print(
            f"[{self.agent_id}] Lanzando Edge en puerto "
            f"{self.debug_port} (headless={self.headless})..."
        )
        try:
            self._launch_edge()
            self._connect_via_cdp()
            self._create_page()
            return self.page
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error lanzando Edge con CDP: {exc}, "
                f"intentando playwright.launch()..."
            )
            # Kill the orphaned Edge OS process before cleaning up Playwright
            # resources; otherwise the process leaks.
            if self._process is not None:
                try:
                    self._process.terminate()
                    self._process.wait(timeout=5)
                except Exception:
                    try:
                        self._process.kill()
                        self._process.wait(timeout=3)
                    except Exception:
                        pass
                self._process = None
            self._cleanup_resources()

        # ── 5. Fallback: playwright.chromium.launch() ──
        try:
            self._launch_playwright()
            self._create_page()
            return self.page
        except Exception as exc:
            self._cleanup_resources()
            raise RuntimeError(
                f"[{self.agent_id}] No se pudo iniciar el navegador: {exc}"
            ) from exc

    def close(self) -> None:
        """Close **this instance's** browser, Playwright connection, and OS process.

        Does **not** affect other ``BrowserController`` instances.
        """
        # Close the Playwright page
        if self.page is not None:
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None

        # Close the browser context
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        # Close the browser (CDP / Playwright connection)
        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        # Stop Playwright
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        # Kill the Edge OS process that *we* launched (not others)
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except Exception:
                try:
                    self._process.kill()
                    self._process.wait(timeout=3)
                except Exception:
                    pass
            self._process = None

        print(f"[{self.agent_id}] Navegador cerrado.")

    # ── Internal: browser launch & connection ──────────────────────────────────

    def _launch_edge(self) -> None:
        """Start the Edge browser process with CDP enabled."""
        edge_path = _find_edge()
        user_data_dir = (
            _PROJECT_ROOT / ".browser_data" / f"browser_data_{self.agent_id}"
        )
        _ensure_dir(user_data_dir)

        cmd = [
            edge_path,
            f"--remote-debugging-port={self.debug_port}",
            f"--user-data-dir={str(user_data_dir)}",
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ]

        if self.headless:
            cmd.append("--headless=new")

        print(
            f"[{self.agent_id}] Lanzando Edge PID -> "
            f"puerto {self.debug_port}"
        )

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        print(f"[{self.agent_id}] Edge PID: {self._process.pid}")

        # Wait until the CDP port is accepting connections
        self._wait_for_port(timeout=30)

    def _wait_for_port(self, timeout: int = 30) -> None:
        """Block until the debug port becomes available or timeout expires."""
        print(
            f"[{self.agent_id}] Esperando que Edge inicie "
            f"(puerto {self.debug_port})..."
        )
        for i in range(timeout):
            if is_port_open(self.debug_port):
                print(f"[{self.agent_id}] Edge disponible tras ~{i + 1}s")
                return
            time.sleep(1)
            if i % 5 == 0 and i > 0:
                print(f"[{self.agent_id}] Esperando... ({i}s)")

        raise TimeoutError(
            f"[{self.agent_id}] Edge no inició en el puerto "
            f"{self.debug_port} tras {timeout} segundos."
        )

    def _connect_via_cdp(self) -> None:
        """Connect Playwright to the running Edge via CDP."""
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        cdp_url = f"http://127.0.0.1:{self.debug_port}"
        print(f"[{self.agent_id}] Conectando a {cdp_url}...")
        self._browser = self._playwright.chromium.connect_over_cdp(cdp_url)
        print(
            f"[{self.agent_id}] Conectado (versión: "
            f"{self._browser.version})"
        )

    def _launch_playwright(self) -> None:
        """Fallback: launch Edge via Playwright's native launcher."""
        if self._playwright is None:
            self._playwright = sync_playwright().start()

        edge_path = _find_edge()
        print(f"[{self.agent_id}] Lanzando Edge via playwright.launch()...")

        launch_args = [
            "--no-first-run",
            "--no-default-browser-check",
            "--start-maximized",
        ]

        self._browser = self._playwright.chromium.launch(
            headless=self.headless,
            executable_path=edge_path,
            args=launch_args,
        )
        print(f"[{self.agent_id}] Edge lanzado vía playwright.")

    def _create_page(self) -> None:
        """Create a page from the current browser with init scripts + stealth."""
        if self._browser is None:
            raise RuntimeError(
                f"[{self.agent_id}] No hay navegador – llama a start() primero"
            )

        # If we connected via CDP, Edge already has a default context.
        # Reusing it prevents opening a second (incognito) window.
        contexts = self._browser.contexts
        if contexts:
            self._context = contexts[0]
            pages = self._context.pages
            self.page = pages[0] if pages else self._context.new_page()
            # Apply viewport to the reused page
            try:
                self.page.set_viewport_size({"width": 1920, "height": 1080})
            except Exception:
                pass
        else:
            # Fallback for playwright.launch() which might not have a default context
            #
            # NB: Only set safe headers here.  Sec-Fetch-*, Upgrade-Insecure-Requests,
            # and Accept-Encoding are FORBIDDEN headers managed by the browser.
            # Overriding them via CDP causes net::ERR_INVALID_ARGUMENT on every
            # resource load, resulting in a completely blank white page.
            self._context = self._browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=USER_AGENT,
                locale="es-ES",
                timezone_id="America/Guayaquil",
                permissions=["geolocation"],
                geolocation={"latitude": -2.1894, "longitude": -79.8891},
                extra_http_headers={
                    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
                },
                ignore_https_errors=True,
            )
            self.page = self._context.new_page()

        # Inject init script to disable animations before any page loads.
        # Guard against null document.head (can happen on about:blank before
        # the real page navigation).
        try:
            self._context.add_init_script(
                """
                (function() {
                    try {
                        if (!document.getElementById('__disable-animations')) {
                            const style = document.createElement('style');
                            style.id = '__disable-animations';
                            style.textContent = [
                                '*, *::before, *::after {',
                                '  animation-duration: 0s !important;',
                                '  animation-delay: 0s !important;',
                                '  transition-duration: 0s !important;',
                                '  transition-delay: 0s !important;',
                                '}'
                            ].join('\\n');
                            if (document.head) {
                                document.head.appendChild(style);
                            }
                        }
                    } catch (e) {
                        console.warn('[BrowserController] init script error:', e.message);
                    }
                })();
            """
            )
        except Exception as e:
            print(f"[{self.agent_id}] No se pudo configurar init script: {e}")

        # Apply stealth to evade detection
        try:
            stealth_sync(self.page)
        except Exception:
            pass

        print(f"[{self.agent_id}] Página lista.")

    def _cleanup_resources(self) -> None:
        """Clean up Playwright connection + browser without touching the OS process
        (the caller decides whether to kill the process)."""
        if self.page is not None:
            try:
                self.page.close()
            except Exception:
                pass
            self.page = None

        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        if self._browser is not None:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    # ── Animations ─────────────────────────────────────────────────────────────

    def _disable_animations(self) -> None:
        """Disable CSS animations on the current page."""
        if self.page is None:
            return
        try:
            self.page.add_style_tag(
                content="""
                    *, *::before, *::after {
                        animation-duration: 0s !important;
                        animation-delay: 0s !important;
                        transition-duration: 0s !important;
                        transition-delay: 0s !important;
                    }
                """
            )
        except Exception:
            pass

    # ── Navigation ─────────────────────────────────────────────────────────────

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        """Navigate the current page to *url*."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado – "
                f"llama a start()"
            )
        print(f"[{self.agent_id}] Navegando a: {url}")
        self.page.goto(url, wait_until=wait_until, timeout=120000)

    # ── Form helpers ───────────────────────────────────────────────────────────

    def wait_for_form_ready(
        self, email_selector: str, timeout: int = 30
    ) -> bool | str:
        """Wait for a login form or detect an existing session.

        Returns:
            * ``True`` -- the form element matching *email_selector* is visible.
            * ``"logged_in"`` (str) -- the page URL contains ``"dashboard"``,
              indicating an active session.
            * ``False`` -- the *timeout* expired without either condition being
              met.

        Raises:
            RuntimeError: If *self.page* is ``None`` (browser not started).
        """
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado – "
                f"llama a start()"
            )

        print(f"[{self.agent_id}] Verificando estado de login...")
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if "dashboard" in self.page.url.lower():
                    print(f"[{self.agent_id}] Ya autenticado (dashboard).")
                    return "logged_in"

                if self.page.locator(email_selector).is_visible(timeout=2000):
                    print(f"[{self.agent_id}] Formulario de login detectado.")
                    return True
            except Exception as exc:
                print(
                    f"[{self.agent_id}] wait_for_form_ready error: {exc}"
                )

            time.sleep(1)
            elapsed = int(time.time() - start_time)
            if elapsed % 5 == 0 and elapsed > 0:
                print(f"[{self.agent_id}] Esperando... ({elapsed}s)")

        if "dashboard" in self.page.url.lower():
            return "logged_in"

        print(f"[{self.agent_id}] Timeout esperando formulario de login.")
        return False

    # ── Screenshot ─────────────────────────────────────────────────────────────

    def screenshot(
        self, path: str = None, full_page: bool = False
    ) -> Optional[bytes]:
        """Take a screenshot of the current page."""
        if self.page is None:
            return None
        try:
            return self.page.screenshot(
                path=path,
                full_page=full_page,
                timeout=15000,
                animations="disabled",
            )
        except Exception as e:
            print(f"[{self.agent_id}] Screenshot error: {e}")
            return None

    # ── Interaction helpers ────────────────────────────────────────────────────

    def click(self, selector: str, timeout: int = 30000) -> None:
        """Click an element matching *selector*."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado"
            )
        self.page.click(selector, timeout=timeout)

    def click_text(self, text: str, timeout: int = 30000) -> None:
        """Click the first element containing *text*."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado"
            )
        self.page.get_by_text(text, exact=False).first.click(timeout=timeout)

    def fill(self, selector: str, value: str) -> None:
        """Fill an input field."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado"
            )
        self.page.fill(selector, value)

    # ── Text extraction ────────────────────────────────────────────────────────

    def get_text(self, selector: str) -> str:
        """Return the inner text of the first matching element."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            element = self.page.query_selector(selector)
            return element.inner_text() if element else ""
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error getting text for "
                f"'{selector}': {exc}"
            )
            return ""

    def get_all_texts(self, selector: str) -> list:
        """Return inner texts of all matching elements."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            elements = self.page.query_selector_all(selector)
            return [el.inner_text() for el in elements]
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error getting all texts for "
                f"'{selector}': {exc}"
            )
            return []

    # ── Waiting ────────────────────────────────────────────────────────────────

    def wait_for_selector(
        self, selector: str, timeout: int = 30000, state: str = "visible"
    ) -> None:
        """Wait for an element matching *selector* to appear."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado"
            )
        self.page.wait_for_selector(selector, timeout=timeout, state=state)

    def wait_for_load(self, timeout: int = 10000) -> None:
        """Wait for the page to reach network idle."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            self.page.wait_for_load_state("networkidle", timeout=timeout)
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error waiting for load state: {exc}"
            )

    # ── State checks ───────────────────────────────────────────────────────────

    def is_visible(self, selector: str) -> bool:
        """Return ``True`` if the element is visible."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            return self.page.is_visible(selector)
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error checking visibility for "
                f"'{selector}': {exc}"
            )
            return False

    def exists(self, selector: str) -> bool:
        """Return ``True`` if the element exists in the DOM."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            return self.page.query_selector(selector) is not None
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error checking existence for "
                f"'{selector}': {exc}"
            )
            return False

    def get_attribute(self, selector: str, attribute: str) -> str:
        """Return an attribute value from the first matching element."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            element = self.page.query_selector(selector)
            return element.get_attribute(attribute) if element else ""
        except Exception as exc:
            print(
                f"[{self.agent_id}] Error getting attribute '{attribute}' for "
                f"'{selector}': {exc}"
            )
            return ""

    # ── JavaScript execution ───────────────────────────────────────────────────

    def evaluate(self, script: str):
        """Execute JavaScript in the page context."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] BrowserController no iniciado"
            )
        return self.page.evaluate(script)

    def sleep(self, seconds: float) -> None:
        """Blocking sleep (for implicit waits)."""
        time.sleep(seconds)

    # ── HTML extraction ────────────────────────────────────────────────────────

    def get_page_html(self, selector: str = None) -> str:
        """Return the inner HTML of *selector* or the full page."""
        if self.page is None:
            raise RuntimeError(
                f"[{self.agent_id}] Browser page is not initialized"
            )
        try:
            if selector:
                element = self.page.query_selector(selector)
                return element.inner_html() if element else ""
            return self.page.content()
        except Exception as e:
            print(f"[{self.agent_id}] Error obteniendo HTML: {e}")
            return ""

    # ── Cleanup ────────────────────────────────────────────────────────────────

    def _atexit_cleanup(self) -> None:
        """Release resources if the process exits without an explicit ``close()``."""
        if (
            self.page is None
            and self._context is None
            and self._browser is None
            and self._playwright is None
            and self._process is None
        ):
            return
        self.close()
