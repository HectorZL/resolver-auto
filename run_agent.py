"""
Script para ejecutar el agente de exámenes.
"""

from exam_agent import ExamAgent
import sys

# Patch asyncio to allow nested loops (Playwright Sync + Gemini)
import nest_asyncio
nest_asyncio.apply()


def main():
    """Punto de entrada principal."""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         AGENTE DE IA - RESOLUTOR DE EXÁMENES UTM          ║
    ║                                                           ║
    ║  Este bot navegará automáticamente la plataforma,         ║
    ║  analizará las preguntas con Gemini AI, y seleccionará    ║
    ║  las respuestas correctas.                                ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    try:
        # Verificar configuración
        import json
        with open("config.json", "r") as f:
            config = json.load(f)
        
        if config.get("gemini_api_key") == "TU_API_KEY_AQUI":
            print("[ERROR] ¡Debes configurar tu API key de Gemini en config.json!")
            print("        Obtén tu API key en: https://aistudio.google.com/app/apikey")
            sys.exit(1)
        
        # Iniciar agente
        agent = ExamAgent()
        agent.run()
        
    except FileNotFoundError:
        print("[ERROR] No se encontró config.json")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n[INFO] Agente detenido por el usuario")
    except Exception as e:
        print(f"[ERROR] {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
