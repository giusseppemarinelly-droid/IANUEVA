"""Interfaz web para el agente ReAct.

Muestra el ciclo Thought -> Action -> Observation a medida que ocurre, que es
justamente lo que hace visible el patron: se ve al modelo razonar, pedir un dato,
recibirlo del entorno y volver a razonar sobre el.

Usa el mismo motor que la consola (agente.ejecutar_react_pasos), no una copia.

Uso: streamlit run app.py
"""

import time

import requests
import streamlit as st

from acciones import ACCIONES
from agente import MAX_CICLOS, MODELO, URL_OLLAMA, ejecutar_react_pasos
from datos import CAMPOS, PERIODOS, VENTAS_2026

# Etiqueta corta para el boton, pregunta completa para el agente: con la pregunta
# entera como etiqueta, cinco columnas quedan ilegibles.
EJEMPLOS = [
    ("Crecimiento marzo→junio", "Cuanto crecieron las ventas de marzo a junio?"),
    ("Promedio 1er trimestre", "Cual fue el promedio de unidades vendidas en el primer trimestre?"),
    ("Total del semestre", "Cuales fueron las ventas totales del semestre?"),
    ("Mes con más devoluciones", "En que mes hubo mas devoluciones y cuantas fueron?"),
    ("Peor mes en ventas", "Que mes tuvo el peor desempeno en ventas?"),
]

st.set_page_config(page_title="Agente ReAct — Informes de ventas",
                   page_icon="🧠", layout="wide")


def ollama_disponible():
    try:
        requests.get(URL_OLLAMA.replace("/api/generate", "/api/version"), timeout=3)
        return True
    except requests.RequestException:
        return False


# --- Barra lateral: el "entorno" y la configuracion -------------------------

with st.sidebar:
    st.header("El entorno")
    st.caption("El modelo no ve estos datos. Solo llega a ellos ejecutando acciones.")
    # Encabezados abreviados: en el ancho de la barra lateral, "Devoluciones"
    # completo empuja la columna fuera de la vista.
    ABREVIATURAS = {"ventas": "Ventas", "unidades": "Unid.", "devoluciones": "Devol."}
    st.dataframe(
        {"Mes": [p.capitalize()[:3] for p in PERIODOS],
         **{ABREVIATURAS[c]: [VENTAS_2026[p][c] for p in PERIODOS] for c in CAMPOS}},
        hide_index=True,
        width="stretch",
    )

    st.header("Herramientas")
    st.code("\n".join(list(ACCIONES) + ["finalizar"]), language=None)

    st.header("Configuracion")
    st.write(f"**Modelo:** `{MODELO}` (local, vía Ollama)")
    st.write(f"**Límite de ciclos:** {MAX_CICLOS}")
    st.write("**Temperatura:** 0")

    if ollama_disponible():
        st.success("Ollama conectado")
    else:
        st.error("Ollama no responde en localhost:11434")


# --- Cabecera ---------------------------------------------------------------

st.title("🧠 Agente ReAct — Informes de ventas")
st.markdown(
    "Implementación del patrón **ReAct** (*Yao et al., 2022*) sobre un modelo "
    "open-source corriendo **100% local**. El agente no responde de una sola vez: "
    "alterna **Thought** (razona), **Action** (ejecuta una herramienta real) y "
    "**Observation** (recibe el resultado del entorno) hasta poder concluir."
)

st.divider()

# --- Entrada ----------------------------------------------------------------

if "pregunta" not in st.session_state:
    st.session_state.pregunta = EJEMPLOS[0][1]

st.subheader("Preguntá algo sobre las ventas de 2026")
st.caption("Elegí un ejemplo o escribí tu propia pregunta.")

columnas = st.columns(len(EJEMPLOS))
for columna, (etiqueta, texto) in zip(columnas, EJEMPLOS):
    with columna:
        if st.button(etiqueta, width="stretch"):
            st.session_state.pregunta = texto

pregunta = st.text_input("Pregunta", key="pregunta", label_visibility="collapsed")
lanzar = st.button("Ejecutar agente", type="primary")

# --- Ejecucion --------------------------------------------------------------

if lanzar and pregunta.strip():
    if not ollama_disponible():
        st.error("No puedo conectarme a Ollama. Verificá que el servicio esté corriendo.")
        st.stop()

    st.divider()
    st.subheader("Razonamiento paso a paso")

    inicio = time.time()
    contenedor = st.container()
    respuesta = None
    ciclos = 0

    with st.spinner(f"El modelo corre en CPU: cada ciclo tarda unos segundos…"):
        try:
            for paso in ejecutar_react_pasos(pregunta):
                ciclos = paso.get("ciclo", ciclos)

                if paso["tipo"] == "ciclo":
                    with contenedor:
                        etiqueta = f"Ciclo {paso['ciclo']}"
                        if paso["accion"]:
                            etiqueta += f" — {paso['accion']}"
                        icono = "⚠️" if paso["es_error"] else "✅"

                        with st.expander(f"{icono}  {etiqueta}", expanded=True):
                            if paso["thought"]:
                                st.markdown(f"🤔 **Thought**  \n_{paso['thought']}_")

                            if paso["accion"] is None:
                                st.markdown("⚙️ **Action**")
                                st.warning("El modelo no generó una Action con formato válido.")
                            else:
                                argumentos = ", ".join(paso["argumentos"])
                                st.markdown("⚙️ **Action**")
                                st.code(f"{paso['accion']}[{argumentos}]", language=None)

                            st.markdown("👁️ **Observation**  \n_(la genera el entorno, no el modelo)_")
                            if paso["es_error"]:
                                st.warning(paso["observacion"])
                            else:
                                st.info(paso["observacion"])

                elif paso["tipo"] == "final":
                    respuesta = paso["respuesta"]
                    with contenedor:
                        with st.expander(f"🏁  Ciclo {paso['ciclo']} — finalizar", expanded=True):
                            if paso["thought"]:
                                st.markdown(f"🤔 **Thought**  \n_{paso['thought']}_")
                            st.markdown("⚙️ **Action**")
                            st.code("finalizar[...]", language=None)

                else:
                    with contenedor:
                        st.error(f"Se alcanzó el límite de {paso['ciclos']} ciclos "
                                 "sin respuesta final.")

        except requests.RequestException as error:
            st.error(f"Error hablando con Ollama: {error}")
            st.stop()

    segundos = time.time() - inicio

    st.divider()
    if respuesta:
        st.subheader("Respuesta")
        st.success(respuesta)

    izquierda, derecha = st.columns(2)
    izquierda.metric("Ciclos usados", ciclos)
    derecha.metric("Tiempo total", f"{segundos:.0f} s")
