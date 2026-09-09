"""Motor de control ReAct: parser + bucle Thought/Action/Observation.

El modelo NO ejecuta nada por si mismo. Solo genera texto. Este modulo es el que
lee ese texto, decide que funcion Python corresponde, la ejecuta de verdad y le
devuelve el resultado al modelo como Observation.
"""

import re
import sys

import requests

from acciones import ACCIONES, OPERACIONES, SINONIMOS
from prompt import construir_prompt

URL_OLLAMA = "http://localhost:11434/api/generate"
MODELO = "qwen2.5:3b"
MAX_CICLOS = 10


def llamar_modelo(prompt):
    """Una pasada de generacion contra Ollama.

    El stop en 'Observation:' es la pieza clave del patron: corta la generacion
    apenas el modelo termina su Action, para que no se invente el resultado. La
    Observation la produce el entorno, no el modelo.
    """
    respuesta = requests.post(
        URL_OLLAMA,
        json={
            "model": MODELO,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                # El modelo a veces escribe la palabra con acento o en espanol;
                # sin estas variantes se inventa su propia Observation.
                "stop": ["Observation:", "Observacion:", "Observación:", "Pregunta:"],
            },
        },
        timeout=180,
    )
    respuesta.raise_for_status()
    return respuesta.json()["response"]


def parsear_thought(texto):
    """Extrae el primer Thought del texto generado (solo para mostrarlo)."""
    match = re.search(r"Thought:\s*(.+)", texto)
    return match.group(1).strip() if match else ""


def parsear_accion(texto):
    """Extrae (nombre, argumentos) de la primera Action del texto generado.

    Devuelve (None, None) si el modelo no escribio una Action con formato valido.
    """
    match = re.search(r"Action:\s*(\w+)\s*\[", texto)
    if not match:
        return None, None

    nombre = match.group(1)
    resto = texto[match.end():]

    # Cortar en el siguiente paso del ciclo por si el modelo genero de mas.
    resto = re.split(r"\n\s*(?:Thought|Action|Observation)\s*:", resto)[0]

    # finalizar recibe texto libre, que puede contener corchetes: se cierra en el
    # ultimo. El resto de las acciones recibe argumentos simples, asi que se
    # cierra en el primero; si no, una linea con dos acciones seguidas
    # ("obtener_dato[a, b], obtener_dato[c, d]") se leeria como una sola.
    cierre = resto.rfind("]") if nombre == "finalizar" else resto.find("]")
    contenido = resto[:cierre] if cierre != -1 else resto

    if nombre == "finalizar":
        return nombre, [contenido.strip()]

    argumentos = [a.strip() for a in contenido.split(",") if a.strip()]
    return nombre, argumentos


def ejecutar_accion(nombre, argumentos):
    """Ejecuta la accion y devuelve el texto de la Observation."""
    # El modelo intenta anidar acciones (calcular[suma, listar_datos[ventas]]).
    # El patron ReAct es secuencial por diseno: una accion por ciclo, y su
    # resultado entra por la Observation del ciclo siguiente.
    if any("[" in argumento for argumento in argumentos):
        return ("Error: no se pueden anidar acciones. Si ya tienes los numeros en una "
                "Observation anterior, copialos literalmente, por ejemplo "
                "calcular[suma, 152000, 138500, 197300].")

    if nombre not in ACCIONES:
        # Caso frecuente: el modelo confunde una operacion de calcular con una
        # accion (escribe maximo[...] en vez de calcular[maximo, ...]). Decirle
        # solo "no existe" lo deja en bucle; corregirlo lo destraba.
        clave = SINONIMOS.get(nombre.lower(), nombre.lower())
        if clave in OPERACIONES:
            return (f"Error: '{nombre}' no es una accion, es una operacion de calcular. "
                    f"Usa calcular[{clave}, num1, num2, ...] con los numeros que ya tienes.")

        disponibles = ", ".join(list(ACCIONES) + ["finalizar"])
        return f"Error: la accion '{nombre}' no existe. Acciones disponibles: {disponibles}."
    return ACCIONES[nombre](argumentos)


def ejecutar_react_pasos(pregunta):
    """Bucle principal como generador: cede un diccionario por cada paso.

    Se implementa asi para que la consola y la interfaz web compartan exactamente
    el mismo motor. Cada paso cedido es {'tipo': 'ciclo'|'final'|'agotado', ...}.
    """
    historial = ""
    accion_anterior = None
    errores_seguidos = 0

    for ciclo in range(1, MAX_CICLOS + 1):
        prompt = construir_prompt(pregunta, historial)
        generado = llamar_modelo(prompt)

        thought = parsear_thought(generado)
        nombre, argumentos = parsear_accion(generado)

        if nombre is None:
            # El modelo se salio del formato: se lo decimos como Observation
            # y le damos otra oportunidad en el proximo ciclo.
            linea_accion = ""
            observacion = ("Error: no se reconocio ninguna Action. Usa el formato "
                           "nombre[arg1, arg2].")
        else:
            if nombre == "finalizar":
                yield {"tipo": "final", "ciclo": ciclo, "thought": thought,
                       "respuesta": argumentos[0]}
                return

            linea_accion = f"Action: {nombre}[{', '.join(argumentos)}]\n"
            observacion = ejecutar_accion(nombre, argumentos)

            # Con temperature 0 el modelo es determinista: si una accion falla, en
            # el ciclo siguiente vuelve a generar exactamente la misma y se queda
            # en bucle. Detectar la repeticion y anadir un aviso a la Observation
            # cambia el prompt, que es lo unico que puede sacarlo de ahi.
            firma = (nombre, tuple(argumentos))
            if firma == accion_anterior:
                observacion += (" Aviso: ya intentaste esta misma accion y no funciono. "
                                "No la repitas: usa otra accion o responde con "
                                "finalizar[...] con los datos que ya tienes.")
            accion_anterior = firma

        # Escalada: si encadena errores, se le corta la exploracion y se le pide
        # cerrar con lo que ya tiene. Cuenta tambien los ciclos sin Action valida,
        # porque el modelo suele alternar entre error y salida sin formato, y esa
        # alternancia por si sola nunca dispararia el aviso.
        errores_seguidos = errores_seguidos + 1 if observacion.startswith("Error:") else 0
        if errores_seguidos >= 3:
            observacion += (" Ultimo aviso: deja de intentar acciones nuevas y responde "
                            "AHORA con finalizar[...] razonando sobre las Observations "
                            "que ya tienes en el historial. No uses marcadores como X ni "
                            "inventes cifras: si falta un dato, dilo explicitamente.")

        historial += f"\nThought: {thought}\n{linea_accion}Observation: {observacion}\n"

        yield {"tipo": "ciclo", "ciclo": ciclo, "thought": thought,
               "accion": nombre, "argumentos": argumentos or [],
               "observacion": observacion,
               "es_error": observacion.startswith("Error:")}

    yield {"tipo": "agotado", "ciclos": MAX_CICLOS}


def ejecutar_react(pregunta, verboso=True):
    """Version de consola. Devuelve la respuesta final o None si se agotan los ciclos."""
    for paso in ejecutar_react_pasos(pregunta):
        if paso["tipo"] == "ciclo":
            if verboso:
                print(f"\n--- Ciclo {paso['ciclo']} ---")
                if paso["thought"]:
                    print(f"Thought: {paso['thought']}")
                if paso["accion"] is None:
                    print("Action: (formato invalido)")
                else:
                    print(f"Action: {paso['accion']}[{', '.join(paso['argumentos'])}]")
                print(f"Observation: {paso['observacion']}")

        elif paso["tipo"] == "final":
            if verboso:
                print(f"\n--- Ciclo {paso['ciclo']} ---")
                if paso["thought"]:
                    print(f"Thought: {paso['thought']}")
                print(f"Action: finalizar[{paso['respuesta']}]")
                print(f"\n=== Respuesta final ===\n{paso['respuesta']}")
            return paso["respuesta"]

        else:
            if verboso:
                print(f"\nSe alcanzo el limite de {paso['ciclos']} ciclos sin respuesta final.")
            return None


if __name__ == "__main__":
    if len(sys.argv) > 1:
        consulta = " ".join(sys.argv[1:])
    else:
        consulta = "Cuanto crecieron las ventas de marzo a junio?"

    print(f"Pregunta: {consulta}")
    ejecutar_react(consulta)
