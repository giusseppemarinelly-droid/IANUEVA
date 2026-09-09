# Documentación — IA con patrón ReAct (IANUEVA)

Documento de contexto profundo para redactar la documentación formal de la entrega
académica. Incluye justificación de decisiones y bitácora cronológica. Se actualiza tras
cada avance significativo.

## 1. Motivación y objetivo

El trabajo consiste en construir una IA propia que implemente el patrón **ReAct**
(Thought → Action → Observation) para generar informes complejos, resolviendo tareas
paso a paso en vez de responder todo de una sola vez.

## 2. El patrón ReAct

Paper de referencia: **"ReAct: Synergizing Reasoning and Acting in Language Models"**
(Yao et al., 2022, Princeton/Google). La idea central es que el modelo genera texto
intercalando tres tipos de pasos:

- **Thought**: razonamiento interno del modelo sobre qué hacer a continuación.
- **Action**: una acción/herramienta concreta que el modelo decide invocar.
- **Observation**: el resultado real de ejecutar esa acción — **no lo genera el modelo**,
  lo devuelve el entorno (en este caso, una función Python).

Este ciclo se repite hasta que el modelo decide que tiene información suficiente y da
una respuesta final. En el paper original se usaba few-shot prompting sobre un LLM
gigante ya entrenado (PaLM-540B). Acá se adapta la misma idea, pero con un modelo mucho
más chico corriendo en CPU local.

## 3. Restricción de diseño y su justificación

El enunciado del trabajo prohíbe usar APIs externas de pago (OpenAI, Anthropic, etc.) y
depender de servicios de terceros en tiempo de ejecución. La solución elegida es correr
un LLM open-source **100% local vía Ollama**: el modelo se descarga una sola vez y todas
las inferencias posteriores ocurren en la máquina del usuario, sin red ni API key. Esto
permite decir con propiedad que la IA es "propia" en el sentido de que corre y se
controla enteramente en el entorno del usuario, aunque los pesos del modelo base no
hayan sido entrenados por el usuario (entrenar un modelo de lenguaje desde cero está
fuera de alcance para una entrega académica en una máquina de 12 cores sin GPU).

## 4. Elección del modelo: `qwen2.5:3b`

Elegido por buen balance velocidad/calidad corriendo por CPU, y porque sigue bien
instrucciones de formato estructurado (clave para poder parsear Thought/Action/
Observation de forma confiable). Tiempo de respuesta observado en modo interactivo:
~7 segundos por respuesta en CPU — aceptable para el caso de uso.

## 5. Arquitectura del sistema

Tres componentes:

1. **Modelo/cerebro** — Ollama + `qwen2.5:3b` corriendo local, expuesto vía API REST en
   `http://localhost:11434/api/generate`.
2. **Motor de control ReAct** (Python) — loop que:
   - arma el prompt con few-shot examples del dominio de informes,
   - llama al modelo vía la API local,
   - parsea la respuesta cruda para extraer Thought/Action/Observation,
   - ejecuta la Action invocando la función Python real correspondiente,
   - reinyecta el resultado como Observation en el siguiente prompt,
   - repite hasta que el modelo devuelve una respuesta final.
3. **Acciones/herramientas del dominio** — funciones Python concretas que el modelo puede
   invocar, pensadas para generación de informes. En definición (ver sección 7).

## 6. Entorno de trabajo

- Windows con WSL2 (Ubuntu).
- Carpeta del proyecto: `/mnt/c/users/gmarinelly/documents/IANUEVA` (filesystem de
  Windows montado en WSL — implica algo más de latencia en operaciones con muchos
  archivos chicos, como `pip install`, pero no es un problema para este proyecto).
- CPU: 12 cores. RAM: 9.6GB total, ~6.2GB disponible. Todo corre por CPU, sin GPU.
- Python: entorno virtual en `venv/`, necesario por el bloqueo PEP 668 de Debian/Ubuntu
  moderno que impide `pip install` a nivel de sistema.

## 7. Dominio elegido y acciones implementadas

**Dominio:** informes de ventas mensuales del año 2026, seis meses (enero a junio) y tres
campos (`ventas`, `unidades`, `devoluciones`).

**Datos mock, no base de datos real.** Para el objetivo del trabajo — demostrar el patrón
ReAct — una base de datos real no aporta nada y añade una dependencia externa que
complica la reproducibilidad de la entrega. Los datos viven en `datos.py` como un
diccionario. Lo importante conceptualmente es que el modelo **no los ve**: solo accede a
ellos a través de las acciones, que es exactamente el rol del "entorno" en ReAct.

**Acciones implementadas** (formato `nombre[arg1, arg2]`, tomado del paper original,
donde las acciones se escribían como `search[entidad]`):

| Acción | Qué hace |
|---|---|
| `obtener_dato[periodo, campo]` | Valor de un campo en un mes. |
| `listar_datos[campo]` | Valor de un campo en los seis meses, de una sola vez. |
| `mes_extremo[campo, maximo\|minimo]` | El mes con el valor más alto o más bajo, y ese valor. |
| `calcular[operacion, n1, n2, ...]` | suma, resta, promedio, maximo, minimo, porcentaje. |
| `comparar_periodo[a, b, campo]` | Variación absoluta y porcentual entre dos meses. |
| `finalizar[texto]` | Entrega la respuesta final y corta el bucle. |

`finalizar` no está en el registro `ACCIONES`: el motor la trata como caso especial,
porque no produce una Observation sino que termina el bucle.

## 8. Desarrollo del motor: fallos encontrados y correcciones

Esta es la parte más instructiva del trabajo. El agente **no funcionó al primer intento**;
llegó a resolver las preguntas correctamente después de siete correcciones. Se documentan
todas porque muestran la diferencia real entre el patrón sobre un modelo gigante (el del
paper) y sobre un modelo de 3B corriendo en CPU.

### 8.1 Fallos de implementación (bugs propios)

**a) El parser unía dos acciones en una sola.** Cuando el modelo generaba
`Action: obtener_dato[marzo, ventas], obtener_dato[junio, ventas]` en una línea, el parser
cerraba en el **último** `]` y leía cuatro argumentos. Corrección: cerrar en el **primer**
`]` para las acciones normales (sus argumentos nunca llevan corchetes) y en el último solo
para `finalizar`, cuyo texto libre sí puede contenerlos.

**b) El stop token no cubría los acentos.** Se paraba la generación en `Observation:`,
pero el modelo, escribiendo en español, a veces producía `Observación:` — y entonces se
inventaba el resultado de su propia acción, que es precisamente lo que el patrón debe
impedir. Corrección: incluir `Observacion:` y `Observación:` entre los stop tokens.

### 8.2 Límites del modelo chico (correcciones de diseño)

**c) Bucle determinista.** Con `temperature: 0`, si una acción falla, el modelo regenera
exactamente la misma en el ciclo siguiente, para siempre. La temperatura 0 se mantiene
porque da reproducibilidad, que para una entrega académica vale más que la variedad.
Corrección: detectar la acción repetida y **añadir un aviso al texto de la Observation** —
cambiar el prompt es lo único que puede sacarlo del bucle.

**d) Inventaba nombres de operación.** Escribía `calcular[diferencia, ...]` cuando la
operación válida era `resta`. Corrección: tabla de sinónimos (`diferencia`→`resta`,
`media`→`promedio`, etc.). Es una concesión razonable: el modelo entendió bien la
intención, falló solo el vocabulario.

**e) Confundía operaciones con acciones.** Escribía `maximo[devoluciones]` como si
`maximo` fuera una herramienta, cuando es una operación de `calcular`. Corrección: cuando
la acción desconocida coincide con una operación válida, el error se lo explica y le
muestra la forma correcta, en vez de limitarse a decir "no existe".

**f) Pasaba referencias en vez de números.** Escribía `calcular[maximo, *devoluciones]` o
`calcular[porcentaje, (35800/197300)*100]`, intentando referenciar datos o delegar
aritmética. Corrección: mensaje de error que le muestra el gesto correcto — copiar los
valores literales de la Observation anterior.

**g) Anidaba acciones.** Escribía `calcular[suma, listar_datos[ventas]]`, esperando que el
resultado de una acción alimentara a otra en el mismo ciclo. Esto contradice el patrón,
que es secuencial por diseño. Corrección: detectarlo, explicárselo, y — lo que realmente
lo resolvió — **añadir un few-shot example con exactamente ese caso** (Ejemplo 5). Para un
modelo chico, una demostración pesa bastante más que una instrucción.

### 8.3 Un fallo de razonamiento, no de formato

Ante "¿en qué mes hubo más devoluciones?", el agente consultó enero, febrero y marzo, se
cansó y respondió "febrero, con 7". La respuesta correcta era **abril, con 9**: nunca miró
los tres meses restantes. Es el fallo más grave de todos, porque el formato era válido y
la respuesta era segura de sí misma pero falsa.

La causa no era el modelo sino el **diseño de las herramientas**: con solo
`obtener_dato`, una pregunta que abarca los seis meses cuesta seis ciclos, y el modelo
abandona antes. Corrección: añadir `listar_datos[campo]`, que devuelve los seis meses en
una sola Observation, más una regla explícita en el prompt de no responder ese tipo de
pregunta habiendo mirado solo algunos meses.

**Conclusión de diseño:** en ReAct, el conjunto de herramientas no es un detalle de
implementación — determina qué preguntas el agente puede responder bien. Una herramienta
que ahorra ciclos puede corregir un error de razonamiento sin tocar el modelo.

### 8.4 Una corrida exitosa no es una prueba

Durante el desarrollo se fue verificando cada corrección ejecutando la pregunta afectada
una sola vez. Al automatizar la batería completa (`regresion.py`) y volver a correrla,
**el resultado bajó de 5/5 a 2/5**. Las mismas preguntas que habían salido bien fallaron.

Esto merece destacarse porque es un error metodológico fácil de cometer y difícil de ver:

- `temperature: 0` **no garantiza reproducibilidad entre corridas**. Da una salida estable
  para un prompt idéntico, pero cualquier cambio en el prompt —agregar un ejemplo,
  reformular un mensaje de error— reordena el comportamiento en preguntas que ni siquiera
  se estaban tocando.
- Verificar una corrección con una sola ejecución confunde suerte con diseño. Dos de los
  "éxitos" registrados durante el desarrollo (el mes con más devoluciones y el peor mes en
  ventas) resultaron no ser reproducibles: el agente había llegado a la respuesta correcta
  por un camino que no estaba garantizado.

De ahí que la batería automatizada no sea un accesorio del trabajo sino parte del método:
sin ella, las conclusiones sobre qué corrección funcionó habrían sido falsas.

### 8.5 Segundo fallo de razonamiento: comparar de a pares

Ante "¿qué mes tuvo el peor desempeño en ventas?", el agente pidió `listar_datos[ventas]`
y recibió los seis valores correctamente. Pero en vez de recorrerlos, llamó a
`comparar_periodo[enero, junio]` —solo dos meses— y concluyó que enero era el peor,
ignorando la lista completa que ya tenía en el historial. Mismo patrón con las
devoluciones: respondió "junio, 5" cuando el máximo era abril con 9.

Es el mismo tipo de fallo de la sección 8.3, y confirma que no era un caso aislado: el
modelo **no ejecuta de forma confiable un barrido de máximo o mínimo sobre una lista**, y
en su lugar toma un atajo (una comparación de a pares) y generaliza la conclusión.

`calcular[minimo, ...]` no resolvía el problema, porque devuelve el valor pero no el mes,
y para recuperar el mes hay que escanear la lista igual. Corrección: una acción dedicada,
`mes_extremo[campo, maximo|minimo]`, que devuelve las dos cosas juntas, más una regla
explícita en el prompt de no comparar de a pares para responder este tipo de pregunta.

### 8.6 Mecanismos de contención

Además de las correcciones puntuales, el motor incluye dos salvaguardas:

- **Detector de repetición**: si la acción es idéntica a la del ciclo anterior, se le
  avisa en la Observation.
- **Escalada tras 3 errores seguidos**: se le pide cerrar con `finalizar[...]` usando lo
  que ya tiene, prohibiendo explícitamente inventar cifras o usar marcadores. Cuenta
  también los ciclos sin Action válida, porque el modelo tiende a alternar entre error y
  salida sin formato, y esa alternancia por sí sola nunca dispararía el aviso.

Ambos existen para que el peor resultado posible sea una respuesta parcial honesta, y no
diez ciclos agotados sin nada.

## 9. Resultados

Batería de regresión (`regresion.py`), que verifica que la cifra clave aparezca en la
respuesta final:

La evolución del resultado a lo largo del desarrollo, midiendo siempre con la batería
completa y no con ejecuciones sueltas:

| Momento | Resultado |
|---|---|
| Primera versión del motor | 0/5 — bucle infinito en la primera pregunta |
| Tras las correcciones 8.1 y 8.2 | 2/5 |
| Tras añadir `mes_extremo` (8.5) | 5/5 |

Detalle de la corrida final:

| Pregunta | Tiempo | Resultado |
|---|---|---|
| Crecimiento de ventas marzo→junio | 53s | 35800 / 18,14% ✅ |
| Promedio de unidades del 1er trimestre | 36s | 127,67 ✅ |
| Ventas totales del semestre | 26s | 1.121.100 ✅ |
| Mes con más devoluciones | 25s | abril, 9 ✅ |
| Peor mes en ventas | 27s | febrero, 138.500 ✅ |

El resultado 5/5 se confirmó en dos corridas independientes. Entre una y otra, las cifras
fueron idénticas pero la redacción cambió levemente ("crecieron 35800 del mes de marzo a
junio" vs. "crecieron 35800 desde marzo hasta junio"): `temperature: 0` en Ollama no es
determinista bit a bit. Es la razón por la que `regresion.py` valida que aparezca la cifra
clave y no que el texto coincida exactamente.

Las cinco cifras fueron verificadas a mano contra `datos.py`. Rendimiento: entre 16 y 53
segundos por pregunta en CPU, según cuántos ciclos necesite (~7 s por ciclo más el costo
de reprocesar un prompt que crece con el historial).

Se observa que el agente resuelve en 2 ciclos las preguntas que tienen una herramienta
directa (`comparar_periodo`, `mes_extremo`) y necesita 3 o más cuando debe encadenar
(listar → calcular → finalizar), que es el comportamiento esperado del patrón.

## 10. Interfaz web (Streamlit)

Además de la consola, el agente se puede ejecutar desde una interfaz web local
(`app.py`, se levanta con `streamlit run app.py`). No es sólo cosmética: el patrón ReAct
es difícil de explicar en abstracto y muy fácil de mostrar, y la interfaz hace visible
justo lo que lo define — cada ciclo aparece a medida que ocurre, con el **Thought**, la
**Action** ejecutada y la **Observation** etiquetada explícitamente como *"la genera el
entorno, no el modelo"*.

Decisiones de esa parte:

- **Un solo motor, dos presentaciones.** Se refactorizó `agente.py` para exponer
  `ejecutar_react_pasos()`, un generador que cede un diccionario por ciclo. La consola y
  la web lo consumen igual. Duplicar el bucle habría hecho que las dos versiones
  divergieran, y entonces la demo dejaría de probar lo que afirma el informe.
- **Los errores se muestran, no se ocultan.** Los ciclos fallidos aparecen en ámbar. En
  una demostración académica, ver al agente equivocarse y corregirse solo en el ciclo
  siguiente vale más que una secuencia impecable: es la evidencia de que la Observation
  realimenta el razonamiento.
- **Telemetría desactivada.** Streamlit envía estadísticas de uso a un servidor externo
  por defecto. Como el trabajo se define por no depender de servicios de terceros en
  tiempo de ejecución, se desactiva explícitamente en `.streamlit/config.toml`, junto con
  la escucha limitada a `localhost`. Es una contradicción fácil de pasar por alto: la
  restricción del enunciado aplica a todo el stack, no sólo al modelo.

La barra lateral muestra la tabla de datos con la aclaración de que el modelo no la ve
—sólo llega a ella ejecutando acciones—, la lista de herramientas disponibles, la
configuración (modelo, límite de ciclos, temperatura) y el estado de conexión con Ollama.

## 11. Limitaciones conocidas y trabajo futuro

- El agente depende bastante de los few-shot examples: las preguntas cuya forma se parece
  a un ejemplo se resuelven en menos ciclos y con menos errores.
- No se probaron todavía casos límite: preguntas sin datos disponibles, ambiguas o fuera
  del dominio. Es el siguiente paso de la batería de pruebas.
- Los mensajes de error del entorno cumplen un doble rol (validación e instrucción al
  modelo), lo que los vuelve parte del prompt de facto. Es efectivo, pero acopla la
  redacción de los errores al comportamiento del agente.
- Posible extensión: medir cuántos ciclos ahorra cada few-shot example, como ablación.

## 12. Bitácora

**2026-08-05**
- Instalado `zstd` (requisito de Ollama) y Ollama vía script oficial.
- Descargado el modelo `qwen2.5:3b`.
- Probado en modo interactivo (`ollama run qwen2.5:3b`): resolvió una suma simple y
  generó correctamente el formato Thought/Action al pedírselo explícitamente.
- Creada la carpeta del proyecto en `/mnt/c/users/gmarinelly/documents/IANUEVA`.
- Creado el entorno virtual (`venv/`) e instalado `requests`.
- Verificado que el servicio de Ollama responde (`curl localhost:11434/api/version`).
- Confirmada la conexión Python → Ollama con `test_ollama.py`: un `POST` a
  `/api/generate` con el modelo `qwen2.5:3b` devuelve la respuesta esperada del modelo.
- Creados `CLAUDE.md` y `Documentacion.md` como documentos maestros del proyecto.
- Definido el dominio (ventas mensuales 2026, datos mock) y escrito `datos.py`.
- Implementadas las acciones en `acciones.py` y el prompt few-shot en `prompt.py`.
- Implementado el motor ReAct completo (parser + bucle) en `agente.py`.
- Primera ejecución end-to-end: **falló**, quedó en bucle repitiendo una acción inválida
  hasta agotar los ciclos. Siguieron seis iteraciones más de corrección, documentadas una
  por una en la sección 8.
- Sistema funcionando: las cinco preguntas de la batería se responden con la cifra
  correcta, verificada a mano contra `datos.py`.
- Escrito `regresion.py` para automatizar la verificación.
- Primera corrida de la batería automatizada: **2/5**, no 5/5 como sugerían las
  ejecuciones sueltas del desarrollo. Dos "éxitos" previos no eran reproducibles
  (ver sección 8.4).
- Diagnosticado el fallo con una traza verbosa: el agente pedía la lista completa y
  después la ignoraba, comparando dos meses de a pares (sección 8.5).
- Añadida la acción `mes_extremo[campo, maximo|minimo]` y reescrito el Ejemplo 4 del
  few-shot para usarla. Batería: **5/5**, confirmado en dos corridas independientes.
- Refactorizado el motor a generador (`ejecutar_react_pasos`) y construida la interfaz web
  con Streamlit (`app.py`). Verificada end-to-end en el navegador: 2 ciclos, respuesta
  correcta, 21 s. Telemetría de Streamlit desactivada por la restricción del enunciado.
- Añadido `requirements.txt` con las dos dependencias directas fijadas por versión.
- **Siguiente paso:** ampliar la batería con casos límite (preguntas sin datos, ambiguas,
  fuera de dominio) y empezar la redacción del informe sobre la sección 8, que es el
  material más valioso del trabajo.
