# Helper method for Login
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
                self.browser.sleep(3)
                
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
