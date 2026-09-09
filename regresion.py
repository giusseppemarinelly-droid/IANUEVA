"""Regresion: corre un set de preguntas y compara contra el valor esperado.

No valida el texto completo de la respuesta (el modelo lo redacta distinto cada
vez), sino que el numero clave aparezca. Es la forma practica de comprobar que
el agente no alucino la cifra.
"""

import time

from agente import ejecutar_react

CASOS = [
    ("Cuanto crecieron las ventas de marzo a junio?", ["35800", "18.14"]),
    ("Cual fue el promedio de unidades vendidas en el primer trimestre?", ["127.67"]),
    ("Cuales fueron las ventas totales del semestre?", ["1121100"]),
    ("En que mes hubo mas devoluciones y cuantas fueron?", ["abril", "9"]),
    # Solo se exige el mes: la pregunta es "que mes", y el modelo a veces incluye
    # la cifra y a veces no. Exigirla convertia una respuesta correcta en falla.
    ("Que mes tuvo el peor desempeno en ventas?", ["febrero"]),
]


def main():
    aprobados = 0

    for pregunta, esperados in CASOS:
        inicio = time.time()
        respuesta = ejecutar_react(pregunta, verboso=False)
        segundos = time.time() - inicio

        if respuesta is None:
            print(f"[SIN RESPUESTA] ({segundos:.0f}s) {pregunta}")
            continue

        faltantes = [e for e in esperados if e.lower() not in respuesta.lower()]
        if faltantes:
            print(f"[FALLA] ({segundos:.0f}s) {pregunta}")
            print(f"        faltan {faltantes} en: {respuesta}")
        else:
            aprobados += 1
            print(f"[OK] ({segundos:.0f}s) {pregunta}")
            print(f"     {respuesta}")

    print(f"\n{aprobados}/{len(CASOS)} casos aprobados.")


if __name__ == "__main__":
    main()
