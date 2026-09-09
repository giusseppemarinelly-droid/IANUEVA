"""Datos mock del dominio: ventas mensuales 2026.

Para fines academicos no hace falta una base de datos real. Este modulo cumple el
papel del "entorno" en el patron ReAct: es la fuente de verdad que devuelve las
Observations, y el modelo solo puede acceder a el a traves de las acciones.
"""

VENTAS_2026 = {
    "enero":   {"ventas": 152000, "unidades": 120, "devoluciones": 4},
    "febrero": {"ventas": 138500, "unidades": 108, "devoluciones": 7},
    "marzo":   {"ventas": 197300, "unidades": 155, "devoluciones": 3},
    "abril":   {"ventas": 210800, "unidades": 168, "devoluciones": 9},
    "mayo":    {"ventas": 189400, "unidades": 149, "devoluciones": 6},
    "junio":   {"ventas": 233100, "unidades": 181, "devoluciones": 5},
}

PERIODOS = list(VENTAS_2026.keys())
CAMPOS = ["ventas", "unidades", "devoluciones"]
