# CLAUDE.md — IA con patrón ReAct (IANUEVA)

Contexto operativo para retomar este proyecto desde cualquier sesión o herramienta sin
tener que re-explicar nada. Actualizar la sección «Estado actual» tras cada avance
significativo, sin esperar a que se pida.

## Objetivo

Construir una IA propia que implemente el patrón ReAct (Thought → Action → Observation)
para generar informes complejos y resolver tareas paso a paso. Proyecto académico.

## Restricción clave

- Nada de APIs externas de pago (OpenAI, Anthropic, etc.) ni dependencias de servicios de
  terceros en tiempo de ejecución.
- El modelo corre 100% local: LLM open-source vía **Ollama**, descargado una vez y usado
  offline. Esto es lo que permite hablar de "IA propia" sin violar la restricción de
  "sin APIs externas": no hay API key ni llamada a un servicio de terceros.

## Patrón ReAct (referencia)

Paper: "ReAct: Synergizing Reasoning and Acting in Language Models" (Yao et al., 2022,
Princeton/Google). Loop de texto intercalado Thought/Action/Observation, donde la
Observation la genera el entorno (no el modelo), hasta llegar a una respuesta final.
Adaptación acá: mismo patrón, pero con un modelo chico local en vez de PaLM-540B.

## Arquitectura

1. **Modelo/cerebro**: Ollama + `qwen2.5:3b` corriendo local en `http://localhost:11434`.
2. **Motor de control ReAct** (Python): arma el prompt con few-shot examples del dominio,
   llama a la API local, parsea Thought/Action/Observation, ejecuta la Action invocando
   una función Python real, reinyecta el resultado como Observation, repite hasta
   respuesta final.
3. **Acciones del dominio** (informes): funciones Python concretas invocables por el
   modelo, sobre datos mock (ver `Documentacion.md` para el detalle y la justificación).

## Entorno

- Windows + WSL2 (Ubuntu). Carpeta del proyecto en `/mnt/c/users/gmarinelly/documents/IANUEVA`
  (filesystem de Windows montado en WSL — más lento que un path nativo de Linux para
  operaciones con muchos archivos chicos, pero suficiente para este proyecto).
- CPU: 12 cores, sin GPU. RAM total ~9.6GB.
- Python: venv en `venv/` (activar con `source venv/bin/activate`).
- Ollama corriendo como servicio local, modelo `qwen2.5:3b` descargado.

## Estado actual

**Última actualización: 5 de agosto de 2026**

| Fase | Descripción | Estado |
|---|---|---|
| 0 | Instalar Ollama + descargar `qwen2.5:3b`, probar en modo interactivo | ✅ Hecho |
| 1 | Crear carpeta de proyecto, venv, instalar `requests` | ✅ Hecho |
| 2 | Confirmar conexión Python → Ollama vía API REST local | ✅ Hecho (`test_ollama.py`) |
| 3 | Definir acciones del dominio de informes (datos mock) | ✅ Hecho (`datos.py`, `acciones.py`) |
| 4 | Prompt template con few-shot | ✅ Hecho (`prompt.py`, 5 ejemplos) |
| 5 | Parser de la respuesta del modelo | ✅ Hecho (`agente.py`) |
| 6 | Loop de control (motor ReAct) | ✅ Hecho (`agente.py`) |
| 7 | Prueba end-to-end | ✅ Hecho (5/5 preguntas correctas, `regresion.py`) |
| 8 | Ampliar batería de pruebas y casos límite | ⬜ Pendiente |
| 9 | Redacción del informe académico | ⬜ Pendiente |

**Siguiente paso concreto:** ampliar la batería de preguntas de `regresion.py` (sobre
todo casos límite: preguntas sin datos, ambiguas, fuera de dominio) y empezar a redactar
el informe apoyándose en la sección 9 de `Documentacion.md`.

## Archivos

| Archivo | Rol |
|---|---|
| `datos.py` | Datos mock (ventas 2026, 6 meses × 3 campos). Hace de "entorno". |
| `acciones.py` | Las 6 herramientas invocables + validación y mensajes de error. |
| `prompt.py` | Plantilla de instrucciones + 5 few-shot examples + armado del prompt. |
| `agente.py` | Parser + bucle ReAct. `ejecutar_react_pasos()` (generador) es el motor; `ejecutar_react()` es la capa de consola. |
| `app.py` | Interfaz web Streamlit. Consume el mismo generador que la consola. |
| `regresion.py` | Corre un set de preguntas y verifica que la cifra clave sea correcta. |
| `test_ollama.py` | Prueba mínima de conectividad Python → Ollama. |

## Uso

```bash
source venv/bin/activate

python agente.py "Cuanto crecieron las ventas de marzo a junio?"   # consola
streamlit run app.py                                                # interfaz web
python regresion.py                                                 # batería
```

## Decisiones de diseño que conviene no romper

- **`stop` en `Observation:`** (y sus variantes con acento) al llamar a Ollama. Es lo que
  impide que el modelo se invente el resultado de sus propias acciones. Sin esto no hay
  patrón ReAct, hay un monólogo.
- **Los errores se devuelven como Observation, no como excepción.** Así el modelo los lee
  y se corrige solo en el ciclo siguiente. Los mensajes de error son parte del diseño del
  prompt, no un detalle: cada uno le muestra el gesto correcto.
- **`temperature: 0`** da reproducibilidad (importante para la entrega), pero provoca que
  una acción fallida se repita idéntica para siempre. De ahí el detector de repetición y
  la escalada tras 3 errores seguidos en `agente.py`.
- **Una acción por ciclo, sin anidar.** El resultado de una acción solo entra por la
  Observation del ciclo siguiente.
- **Si el modelo falla al razonar, primero mirar el conjunto de herramientas.** Los dos
  errores de razonamiento del proyecto (respuestas incorrectas dichas con seguridad) se
  arreglaron agregando una herramienta —`listar_datos` y `mes_extremo`—, no ajustando el
  prompt. El modelo no hace barridos de máximo/mínimo de forma confiable: hay que dárselo
  resuelto.
- **Un solo motor, dos presentaciones.** `ejecutar_react_pasos()` es un generador que cede
  un dict por ciclo; la consola y Streamlit lo consumen igual. No duplicar el bucle: si se
  duplica, las dos versiones divergen y la web deja de demostrar lo que el informe afirma.
- **Verificar siempre con `regresion.py` completo, nunca con una ejecución suelta.**
  `temperature: 0` da salida estable para un prompt idéntico, pero cambiar el prompt
  reordena el comportamiento en preguntas que no se estaban tocando. Medir de a una lleva
  a confundir suerte con diseño (pasó: 5/5 aparente que en la batería era 2/5).

## Convención de mantenimiento de docs

- `CLAUDE.md` (este archivo) → contexto operativo rápido, sección «Estado actual», y
  cualquier cambio de arquitectura o convención.
- `Documentacion.md` → paso a paso detallado, decisiones tomadas con su justificación, y
  bitácora cronológica.

Ninguna fase se considera cerrada hasta que ambos documentos reflejan el código real.
