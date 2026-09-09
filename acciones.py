"""Acciones (herramientas) que el modelo puede invocar.

Cada accion recibe una lista de argumentos en texto (tal como los escribio el
modelo) y devuelve un string: ese string es la Observation que se le reinyecta.

Los errores no lanzan excepcion, se devuelven como texto. Asi el modelo puede
leer el error en la Observation y corregirse en el siguiente ciclo, que es
justamente lo que hace util al patron ReAct frente a una sola pasada.
"""

from datos import VENTAS_2026, PERIODOS, CAMPOS


# Operaciones que acepta calcular. Se exporta para que el motor pueda detectar
# cuando el modelo las confunde con acciones y darle una correccion util.
OPERACIONES = {"suma", "resta", "promedio", "maximo", "minimo", "porcentaje"}

# Un modelo chico tiende a inventar nombres de operacion razonables pero fuera
# del vocabulario esperado ("diferencia" en vez de "resta"). Aceptarlos evita
# ciclos perdidos sin relajar la validacion de verdad.
SINONIMOS = {
    "diferencia": "resta",
    "restar": "resta",
    "total": "suma",
    "sumar": "suma",
    "media": "promedio",
    "mayor": "maximo",
    "max": "maximo",
    "menor": "minimo",
    "min": "minimo",
}


def obtener_dato(args):
    """obtener_dato[periodo, campo] -> valor del campo en ese periodo."""
    if len(args) != 2:
        return f"Error: obtener_dato espera 2 argumentos (periodo, campo), recibio {len(args)}."

    periodo, campo = args[0].lower(), args[1].lower()

    if periodo not in VENTAS_2026:
        return f"Error: no hay datos de '{periodo}'. Periodos disponibles: {', '.join(PERIODOS)}."
    if campo not in CAMPOS:
        return f"Error: el campo '{campo}' no existe. Campos disponibles: {', '.join(CAMPOS)}."

    return str(VENTAS_2026[periodo][campo])


def listar_datos(args):
    """listar_datos[campo] -> el valor del campo en todos los periodos.

    Sin esta accion, una pregunta del tipo "en que mes hubo mas X" obliga al
    modelo a gastar un ciclo por mes, y en la practica abandona antes de
    recorrerlos todos y responde con datos incompletos.
    """
    if len(args) != 1:
        return f"Error: listar_datos espera 1 argumento (campo), recibio {len(args)}."

    campo = args[0].lower()
    if campo not in CAMPOS:
        return f"Error: el campo '{campo}' no existe. Campos disponibles: {', '.join(CAMPOS)}."

    partes = [f"{periodo}: {VENTAS_2026[periodo][campo]}" for periodo in PERIODOS]
    return f"{campo} por mes -> " + "; ".join(partes) + "."


def mes_extremo(args):
    """mes_extremo[campo, maximo|minimo] -> el mes con el valor mas alto o mas bajo.

    Existe porque el modelo no hace de forma confiable el barrido de maximo o
    minimo sobre una lista: tiende a comparar dos meses sueltos y generalizar la
    conclusion a los seis. calcular[minimo, ...] no alcanza, porque devuelve el
    valor pero no el mes, y para recuperar el mes hay que escanear igual.
    """
    if len(args) != 2:
        return (f"Error: mes_extremo espera 2 argumentos (campo, maximo o minimo), "
                f"recibio {len(args)}.")

    campo = args[0].lower()
    tipo = SINONIMOS.get(args[1].lower(), args[1].lower())

    if campo not in CAMPOS:
        return f"Error: el campo '{campo}' no existe. Campos disponibles: {', '.join(CAMPOS)}."
    if tipo not in ("maximo", "minimo"):
        return f"Error: el segundo argumento debe ser maximo o minimo, no '{args[1]}'."

    pares = [(periodo, VENTAS_2026[periodo][campo]) for periodo in PERIODOS]
    seleccion = max if tipo == "maximo" else min
    periodo, valor = seleccion(pares, key=lambda par: par[1])

    return f"El {tipo} de {campo} del semestre es {valor}, en {periodo}."


def calcular(args):
    """calcular[operacion, num1, num2, ...] -> resultado de la operacion."""
    if len(args) < 2:
        return "Error: calcular espera una operacion y al menos un numero."

    operacion = SINONIMOS.get(args[0].lower(), args[0].lower())
    try:
        numeros = [float(a) for a in args[1:]]
    except ValueError:
        # El modelo tiende a pasar el nombre del campo o una expresion en vez de
        # los numeros ("*devoluciones", "(a/b)*100"). El mensaje le muestra el
        # gesto correcto: copiar los valores literales de la Observation previa.
        return ("Error: los argumentos deben ser numeros literales, no nombres de campos, "
                "variables ni expresiones. Copia los numeros de la Observation anterior, "
                "por ejemplo calcular[maximo, 4, 7, 3, 9, 6, 5].")

    if operacion == "suma":
        resultado = sum(numeros)
    elif operacion == "resta":
        resultado = numeros[0] - sum(numeros[1:])
    elif operacion == "promedio":
        resultado = sum(numeros) / len(numeros)
    elif operacion == "maximo":
        resultado = max(numeros)
    elif operacion == "minimo":
        resultado = min(numeros)
    elif operacion == "porcentaje":
        if len(numeros) != 2:
            return "Error: porcentaje espera 2 numeros (parte, total)."
        if numeros[1] == 0:
            return "Error: el total no puede ser 0."
        resultado = numeros[0] / numeros[1] * 100
    else:
        return ("Error: operacion no reconocida. Operaciones validas: "
                "suma, resta, promedio, maximo, minimo, porcentaje.")

    return _formatear_numero(resultado)


def comparar_periodo(args):
    """comparar_periodo[periodo_a, periodo_b, campo] -> variacion absoluta y porcentual."""
    if len(args) != 3:
        return (f"Error: comparar_periodo espera 3 argumentos "
                f"(periodo_a, periodo_b, campo), recibio {len(args)}.")

    periodo_a, periodo_b, campo = args[0].lower(), args[1].lower(), args[2].lower()

    for periodo in (periodo_a, periodo_b):
        if periodo not in VENTAS_2026:
            return f"Error: no hay datos de '{periodo}'. Periodos disponibles: {', '.join(PERIODOS)}."
    if campo not in CAMPOS:
        return f"Error: el campo '{campo}' no existe. Campos disponibles: {', '.join(CAMPOS)}."

    valor_a = VENTAS_2026[periodo_a][campo]
    valor_b = VENTAS_2026[periodo_b][campo]
    diferencia = valor_b - valor_a

    if valor_a == 0:
        return f"{campo} paso de 0 a {valor_b}; la variacion porcentual no esta definida."

    porcentaje = diferencia / valor_a * 100
    signo = "aumento" if diferencia > 0 else "disminuyo" if diferencia < 0 else "no vario"

    return (f"{campo} en {periodo_a}: {valor_a}; en {periodo_b}: {valor_b}. "
            f"{signo.capitalize()} {_formatear_numero(abs(diferencia))} "
            f"({_formatear_numero(abs(porcentaje))}%).")


def _formatear_numero(valor):
    """Evita imprimir 152000.0 cuando el resultado es entero."""
    if valor == int(valor):
        return str(int(valor))
    return f"{valor:.2f}"


# Registro de acciones disponibles para el motor ReAct.
# 'finalizar' no esta aca: el motor la trata como caso especial porque no
# produce una Observation, sino que corta el bucle.
ACCIONES = {
    "obtener_dato": obtener_dato,
    "listar_datos": listar_datos,
    "mes_extremo": mes_extremo,
    "calcular": calcular,
    "comparar_periodo": comparar_periodo,
}
