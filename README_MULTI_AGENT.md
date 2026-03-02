# Sistema Multi-Agente para Bot-Exam

Sistema de paralelización que permite ejecutar **4 agentes simultáneamente** resolviendo exámenes de manera coordinada.

## 🎯 Características

- **4 AgAgentes en Paralelo:** Múltiples procesos trabajando simultáneamente
- **Coordinación mediante MD:** Archivo `agents_state.md` compartido en tiempo real
- **Bloqueo Exclusivo:** Un solo agente por actividad (file locking con `filelock`)
- **Sistema de Aprobaciones:** Cada actividad requiere 4 aprobaciones completas (10-11 preguntas c/u)
- **Timeout Automático:** 2 minutos de inactividad libera la actividad automáticamente
- **Registro de Eventos:** Todos los cambios se registran en el MD

## 📁 Archivos Nuevos

```
bot-exam/
├── agent_coordinator.py       # Coordinador central del sistema multi-agente
├── run_multi_agent.py          # Script principal para lanzar 4 agentes
├── test_agent_coordinator.py   # Tests de coordinación
├── agents_state.md             # Estado compartido (generado automáticamente)
└── agents_state.json           # Datos estructurados (generado automáticamente)
```

## 🚀 Uso

### Instalación de Dependencias

```bash
pip install -r requirements.txt
```

### Ejecutar Sistema Multi-Agente

```bash
python run_multi_agent.py
```

El script te preguntará si deseas activar el monitor en tiempo real del estado.

### Ejecutar Tests

```bash
python test_agent_coordinator.py
```

## 📊 Progreso de Actividades

Cada actividad muestra su progreso en el formato **X/4 aprobaciones**:

- **0/4:** Sin iniciar o recién descubierta
- **1/4:** Primera aprobación completa (10-11 preguntas resueltas correctamente)
- **2/4:** Segunda aprobación completa
- **3/4:** Tercera aprobación completa
- **4/4:** Actividad completada al 100% ✅

## 🔒 Sistema de Bloqueo

El sistema garantiza que **solo un agente** trabaje en una actividad a la vez:

1. **Claim:** Agente reclama actividad disponible
2. **Heartbeat:** Actualiza timestamp cada pregunta resuelta (evita timeout)
3. **Approval:** Registra aprobación completa al terminar las 10-11 preguntas
4. **Release:** Libera actividad al completar 4/4 o por error

Si un agente no envía heartbeat por **2 minutos**, la actividad se libera automáticamente.

## 📝 Archivo agents_state.md

Ejemplo de contenido:

```markdown
# Estado de Actividades Multi-Agente
*Última actualización: 2026-02-08 13:15:42*

---

## Actividad: Module 1 - Practice 1
- **Estado:** En Progreso
- **Agente:** Agent-2
- **Progreso:** 2/4 aprobaciones
- **Preguntas Actuales:** 7/11
- **Última Actualización:** 2026-02-08T13:15:40
- **Evento:** Agent-2 completó aprobación 2/4

## Actividad: Module 2 - Quiz 1
- **Estado:** Completada 100%
- **Agente:** -
- **Progreso:** 4/4 aprobaciones
- **Última Actualización:** 2026-02-08T13:10:15
- **Evento:** Agent-1 completó la actividad al 100% (4/4 aprobaciones)

## Actividad: Module 3 - Listening 1
- **Estado:** Disponible (Timeout)
- **Agente:** [Liberado]
- **Progreso:** 1/4 aprobaciones
- **Última Actualización:** 2026-02-08T13:12:00
- **Evento:** TIMEOUT - Agent-3 no respondió por 120+ segundos
```

## ⚙️ Configuración

En `config.json`:

```json
{
  "multi_agent": {
    "enabled": true,
    "num_agents": 4,
    "state_file": "agents_state.md",
    "activity_timeout_seconds": 120
  }
}
```

## 🧪 Tests Incluidos

1. **Test de Claim Básico:** Verificar bloqueo exclusivo
2. **Test de Aprobaciones:** Tracking de 4 aprobaciones
3. **Test de Heartbeat:** Actualizaciones periódicas
4. **Test de Timeout:** Liberación automática después de 2 min
5. **Test Concurrente:** 10 threads intentando reclamar simultáneamente

## 🔧 Arquitectura

```
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│   Agent-1   │  │   Agent-2   │  │   Agent-3   │  │   Agent-4   │
│  (Proceso)  │  │  (Proceso)  │  │  (Proceso)  │  │  (Proceso)  │
└──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘
       │                │                │                │
       │                │                │                │
       └────────────────┴────────────────┴────────────────┘
                             │
                             ▼
                  ┌──────────────────────┐
                  │  agent_coordinator   │
                  │   (File Locking)     │
                  └──────────────────────┘
                             │
                ┌────────────┴────────────┐
                │                         │
                ▼                         ▼
      agents_state.json         agents_state.md
      (Datos estructurados)     (Visualización)
```

## 💡 Ventajas del Sistema

- ✅ **4x más rápido:** Cuatro actividades en paralelo
- ✅ **Coordinación automática:** Sin intervención manual
- ✅ **Visibilidad en tiempo real:** Monitor del archivo MD
- ✅ **Tolerante a fallos:** Timeout automático y registro de eventos
- ✅ **Sin colisiones:** File locking garantiza exclusividad

## 🐛 Troubleshooting

### Problema: "filelock no instalado"

**Solución:**
```bash
pip install filelock
```

### Problema: Agente se queda en "En Progreso" indefinidamente

**Solución:** El timeout liberará automáticamente la actividad después de 2 minutos. También puedes editar manualmente `agents_state.json` y cambiar el estado a `"Disponible"`.

### Problema: Múltiples agentes reclaman la misma actividad

**Solución:** Esto no debería ocurrir con filelock instalado. Verifica que `filelock` esté correctamente instalado.

## 📜 Licencia

Mismo licencia que el proyecto bot-exam original.
