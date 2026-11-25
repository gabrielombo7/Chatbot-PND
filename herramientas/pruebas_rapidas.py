"""
pruebas_rapidas.py — Pruebas que no necesitan llave ni red: el ciclo del modelo con un modelo simulado y
el buscador con casos conocidos.
=========================================================================================================
Se corre después de tocar buscador.py, motor.py o los datos:

    python herramientas/pruebas_rapidas.py

Dice «TODO OK» o cuáles fallaron. Lo que NO prueba es el modelo real: para eso, con una llave de prueba,
`ANTHROPIC_API_KEY=... python herramientas/clasificar_proyectos.py` corre 63 proyectos con el flujo real.
"""
import json
import os
import sys

os.environ.setdefault("ANTHROPIC_API_KEY", "sin-llave")      # motor.py no la usa al importarse
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import buscador as B  # noqa: E402
import motor  # noqa: E402

class Bl:
    def __init__(self, tipo, **kw): self.type = tipo; self.__dict__.update(kw)
def texto(t): return Bl("text", text=t)
def uso(i, nombre, **inp): return Bl("tool_use", id=f"t{i}", name=nombre, input=inp)
class R:
    def __init__(self, stop, *bloques): self.stop_reason = stop; self.content = list(bloques)
class Cli:
    def __init__(self, *guion):
        self.guion = list(guion); self.pedidos = []; self.messages = self
    def create(self, **kw):
        kw = dict(kw, messages=list(kw['messages'])); self.pedidos.append(kw); return self.guion.pop(0)
def hist(*pares): return [{"role": r, "content": c} for r, c in pares]
ok = True
def verifica(nombre, cond, detalle=""):
    global ok
    ok &= bool(cond); print(("OK  " if cond else "FALLA"), nombre, ("— " + str(detalle)[:300]) if (detalle and not cond) else "")

# A. búsqueda con resultados: una llamada, herramienta obligatoria, texto desde los datos
c = Cli(R("tool_use", uso(1, "buscar_estrategias", terminos=["estadio", "escenarios deportivos", "deporte"])))
t, ll, terms = motor.responder(c, hist(("user", "Instalación de iluminación en estadio de fútbol")))
verifica("A. una llamada al modelo", len(c.pedidos) == 1, len(c.pedidos))
verifica("A. el modelo está obligado a usar una herramienta", c.pedidos[0]["tool_choice"] == {"type": "any"}, c.pedidos[0].get("tool_choice"))
verifica("A. existe la herramienta contestar", "contestar" in [x["name"] for x in c.pedidos[0]["tools"]])
verifica("A. texto con 4.4.9 y su nombre", "4.4.9 · Infraestructura y financiación territorial para el deporte" in t, t[:200])

# B. «contestar» con un código: se rechaza y se obliga a buscar
c = Cli(R("tool_use", uso(1, "contestar", texto="Podría corresponder a la 4.5.4 Servicios públicos con calidad.")),
        R("tool_use", uso(2, "buscar_estrategias", terminos=["acueducto", "Agua potable", "Servicios públicos"])))
t, ll, terms = motor.responder(c, hist(("user", "Acueducto para mi vereda")))
verifica("B. la segunda llamada obliga a buscar", len(c.pedidos) == 2 and c.pedidos[1]["tool_choice"] == {"type": "tool", "name": "buscar_estrategias"}, [p.get("tool_choice") for p in c.pedidos])
verifica("B. el rechazo llega al modelo como error", c.pedidos[1]["messages"][-1]["content"][0].get("is_error") is True)
verifica("B. la respuesta sale de los datos", "Opción sugerida:" in t and "Podría corresponder" not in t, t[:160])

# C. pregunta aclaratoria: pasa tal cual
c = Cli(R("tool_use", uso(1, "contestar", texto="¿Qué se construye con ese proyecto o a quién sirve?")))
t, ll, terms = motor.responder(c, hist(("user", "AVEM Fase 1")))
verifica("C. la pregunta aclaratoria pasa tal cual", t == "¿Qué se construye con ese proyecto o a quién sirve?" and not ll and len(c.pedidos) == 1, t)

# D. «contestar» con el nombre de una línea
c = Cli(R("tool_use", uso(1, "contestar", texto="Eso va en «Salud en las regiones».")),
        R("tool_use", uso(2, "buscar_estrategias", terminos=["hospital", "Infraestructura hospitalaria", "salud"])))
t, ll, terms = motor.responder(c, hist(("user", "Quiero un hospital")))
verifica("D. nombre ajeno rechazado", "Opción sugerida" in t and "Eso va en" not in t, t[:160])

# E. sin resultados -> vocabulario -> contestar válido
c = Cli(R("tool_use", uso(1, "buscar_estrategias", terminos=["zzqqxx", "wwvvuu"])),
        R("tool_use", uso(2, "listar_vocabulario", fragmento="agua")),
        R("tool_use", uso(3, "contestar", texto="No encontré esas palabras. En el Plan existen, por ejemplo, «Agua potable» y «Calidad del agua».")))
t, ll, terms = motor.responder(c, hist(("user", "zzqqxx wwvvuu")))
verifica("E. tres llamadas y texto del modelo", len(c.pedidos) == 3 and t.startswith("No encontré esas palabras"), (len(c.pedidos), t[:80]))
res1 = json.loads(c.pedidos[1]["messages"][-1]["content"][0]["content"])
verifica("E. al modelo no le llegan las claves de interfaz", not any(k in res1 for k in motor.SOLO_INTERFAZ), list(res1))

# F. ficha por código
c = Cli(R("tool_use", uso(1, "detalle_estrategia", codigo="2.1.3")))
t, ll, terms = motor.responder(c, hist(("user", "Cuéntame de la 2.1.3")))
verifica("F. ficha desde los datos", t.startswith("**2.1.3 · Acceso, permanencia") and "Palabras clave:" in t, t[:120])

# G. un código mostrado antes se puede volver a mencionar
c = Cli(R("tool_use", uso(1, "contestar", texto="Sobre la 4.5.4 que viste: ¿es para zona rural o urbana?")))
t, ll, terms = motor.responder(c, hist(("user", "acueducto"), ("assistant", "**Opción sugerida: 4.5.4 · Servicios públicos con calidad, continuidad y asequibilidad**"), ("user", "¿cuál es la mejor?")))
verifica("G. código ya mostrado se permite", t.startswith("Sobre la 4.5.4"), t[:100])

# H. detector
verifica("H. detecta código inventado", motor.lineas_ajenas("Va en 9.9.9", set()) == ["9.9.9"])
verifica("H. no confunde decimales ni años", motor.lineas_ajenas("Plan 2026-2030, tasa 3.5 %, versión 1.2", set()) == [])

# I. consulta muy amplia
c = Cli(R("tool_use", uso(1, "buscar_estrategias", terminos=["infraestructura"])))
t, ll, terms = motor.responder(c, hist(("user", "infraestructura")))
verifica("I. pregunta de qué tipo", t.startswith("Esto da muchos resultados. ¿De qué tipo es tu idea?") and t.count("Opción sugerida") <= 3, t[:200])

# J. demasiadas vueltas
c = Cli(*[R("tool_use", uso(i, "buscar_estrategias", terminos=["zzqqxx", "wwvvuu"])) for i in range(1, 8)])
t, ll, terms = motor.responder(c, hist(("user", "zzqqxx")))
verifica("J. tope de vueltas", t == motor.MSG_DEMASIADAS_VUELTAS, t)

# K. la frase del diccionario que escribió la persona se añade aunque el modelo no la use
c = Cli(R("tool_use", uso(1, "buscar_estrategias", terminos=["Conectividad rural", "caminos veredales"])))
t, ll, terms = motor.responder(c, hist(("user", "Quiero hacer una placa huella en mi vereda")))
args = ll[0]["argumentos"]["terminos"]
verifica("K. «placa huella» añadida a los términos", "placa huella" in args, args)
verifica("K. aparece 5.1.7", "5.1.7 ·" in t, t[:160])

# L. respaldo (el modelo devuelve texto con un código en vez de una herramienta): usa las frases y descarta la pregunta
c = Cli(R("end_turn", texto("Va en la 2.1.1.")))
t, ll, terms = motor.responder(c, hist(("user", "Quiero construir un colegio, ¿a qué línea estratégica me remito?")))
cods = [x for x in B.buscar_estrategias(B.terminos_del_texto("Quiero construir un colegio, ¿a qué línea estratégica me remito?"))["niveles"]["cercanas"]]
verifica("L. respaldo busca sólo «colegio» y cae en educación", ll and ll[-1]["argumentos"]["terminos"] == ["colegio"] and all(c.startswith("2.") for c in cods), (ll[-1]["argumentos"] if ll else None, cods))
c = Cli(R("end_turn", texto("Va en la 5.1.7.")))
t, ll, terms = motor.responder(c, hist(("user", "placa huella")))
verifica("L. respaldo con «placa huella» da 5.1.7", "5.1.7 ·" in t, t[:160])

# M. contestar y buscar en la misma respuesta: gana la búsqueda
c = Cli(R("tool_use", uso(1, "contestar", texto="Voy a buscar."), uso(2, "buscar_estrategias", terminos=["estadio", "deporte"])))
t, ll, terms = motor.responder(c, hist(("user", "estadio")))
verifica("M. con contestar + buscar gana la búsqueda", "Opción sugerida" in t and "Voy a buscar" not in t, t[:120])

# N. El buscador con casos conocidos
c = B.buscar_estrategias(["gasoducto", "gas natural"])["niveles"]["cercanas"]
verifica("N. «gas natural» no coincide con «base natural» (palabras cortas)", "5.2.7" in c and "5.4.4" not in c, c)
verifica("N. una frase del diccionario gana sobre sus palabras: «casa de gobierno» no es vivienda",
         "vivienda" not in [e["termino"] for e in B.expandir(["casa de gobierno"])])
verifica("N. «placa huella» está en el diccionario que ve el modelo", "placa huella" in B.sinonimos_vivos() and "placa huella →" in motor.SYSTEM_PROMPT)
verifica("N. el prompt trae el catálogo y la regla de las palabras genéricas",
         "4.5.4 Servicios públicos con calidad" in motor.SYSTEM_PROMPT and "sola palabra" in motor.SYSTEM_PROMPT)
muertos = B.sinonimos_muertos()
print(f"   (aviso, no falla) el diccionario tiene {len(muertos)} filas con algún término que el Plan no tiene escrito; "
      "ver buscador.sinonimos_muertos()")

print("\nTODO OK" if ok else "\nHAY FALLAS")
