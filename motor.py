"""
motor.py — Ciclo de conversación del orientador (independiente de la interfaz).
===============================================================================
El modelo cumple una sola función: traducir la pregunta a términos de búsqueda
y redactar el resultado. No conoce el contenido del PND y no puede responder sin
llamar la herramienta: las estrategias, los códigos y las coincidencias salen
todas de buscador.py.

Si la búsqueda no devuelve nada, el asistente lo dice. No tiene de dónde
inventar una estrategia, porque nunca recibió la lista completa.
"""

import json

import buscador as B

MODELO = "claude-haiku-4-5"
MAX_TOKENS = 1200
MAX_VUELTAS = 6          # tope de iteraciones del ciclo de herramientas
MAX_TURNOS_HISTORIAL = 8  # cuántos mensajes previos se reenvían al modelo
# Claves del resultado de la búsqueda que sólo usa la interfaz (el modelo no las ve).
SOLO_INTERFAZ = ("otras", "niveles", "coincidencias")

CAT = B.catalogo()

TOOLS = [
    {
        "name": "buscar_estrategias",
        "description": (
            "Busca estrategias del PND que contengan ciertos términos. Es una "
            "búsqueda de texto: encuentra la estrategia sólo si el término aparece "
            "escrito en sus palabras clave, en su nombre, en su tema o en su "
            "descripción.\n\n"
            "Pasa varios términos: primero las palabras que usó la persona y "
            "además los términos con que el PND nombraría eso mismo. Ejemplos:\n"
            "- 'quiero construir un colegio' -> ['colegio', 'infraestructura "
            "educativa', 'establecimientos educativos', 'educacion']\n"
            "- 'becas de estudio' -> ['becas', 'financiacion estudiantil', "
            "'educacion superior', 'permanencia']\n"
            "- 'arreglar una carretera' -> ['carretera', 'via', 'corredores', "
            "'transporte', 'infraestructura']\n\n"
            "Usa términos cortos (una o dos palabras). Omite verbos y palabras "
            "vacías como 'quiero', 'necesito', 'hacer'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "terminos": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Entre 2 y 8 términos de búsqueda.",
                },
            },
            "required": ["terminos"],
        },
    },
    {
        "name": "listar_vocabulario",
        "description": (
            "Devuelve palabras clave que existen en el PND y contienen un "
            "fragmento de texto. Úsala SOLO cuando buscar_estrategias no devolvió "
            "resultados, para mostrarle a la persona qué vocabulario sí existe en "
            "el documento en vez de quedarte sin respuesta."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fragmento": {
                    "type": "string",
                    "description": "Fragmento de palabra, por ejemplo 'educa' o 'agua'.",
                },
            },
            "required": ["fragmento"],
        },
    },
    {
        "name": "detalle_estrategia",
        "description": (
            "Ficha completa de una estrategia por su código, por ejemplo '2.1.3'. "
            "Úsala cuando la persona pregunte por una estrategia puntual o pida "
            "ampliar una que ya apareció."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "codigo": {"type": "string", "description": "Código, ej. '4.5.6'."},
            },
            "required": ["codigo"],
        },
    },
]

DISPATCH = {
    "buscar_estrategias": B.buscar_estrategias,
    "listar_vocabulario": B.listar_vocabulario,
    "detalle_estrategia": B.detalle_estrategia,
}

_lista_ejes = "\n".join(
    f"  {e['eje_n']}. {e['eje']} ({e['estrategias']} estrategias)" for e in CAT["ejes"]
)

SYSTEM_PROMPT = f"""Orientas a servidores públicos y equipos sectoriales sobre en qué \
parte del Plan Nacional de Desarrollo 2026-2030 se ubicaría una idea, un proyecto o un \
programa. Tu alcance es exactamente ese: ubicar en la estructura eje → tema → estrategia.

ESTRUCTURA DISPONIBLE ({CAT['n_estrategias']} estrategias, {CAT['n_temas']} temas, {CAT['n_ejes']} ejes):
{_lista_ejes}

CÓMO TRABAJAS
1. No tienes el contenido del PND en memoria. Para cada pregunta sobre ubicación llamas \
buscar_estrategias. Sin llamarla no tienes nada que responder.
2. Al armar los términos, incluye las palabras de la persona Y los términos con que el \
documento nombraría eso. La herramienta es literal y busca sólo en las palabras clave, el \
nombre y el tema de cada estrategia (no en la descripción): "colegio" no aparece en las \
palabras clave del PND, pero "infraestructura educativa" sí.
3. Si la búsqueda no devuelve resultados, prueba una vez más con términos más generales. \
Si sigue vacía, llama listar_vocabulario y muestra qué vocabulario existe. Nunca \
completes el vacío con una estrategia inventada.

REGLAS ESTRICTAS
- Sólo mencionas estrategias que vinieron en el resultado de una herramienta, con el \
código y el nombre exactos que te devolvió. No inventas códigos ni nombres, no corriges \
nombres, no agregas estrategias "parecidas" de tu conocimiento general.
- Siempre dices DÓNDE coincidió cada opción: en las palabras clave, en el nombre de la \
estrategia o en el tema. Esa es la justificación de la sugerencia y la persona necesita \
verla para juzgarla.
- Presentas todas las opciones que vienen en 'resultados': son las más cercanas, casi \
siempre una y varias sólo si empatan o están muy parejas. No las ordenes ni elijas entre \
las que empatan. Las demás la persona las ve aparte, en «Otras estrategias»: no las \
menciones. Si 'n_cercanas' es mayor que las que vienen, agrega una línea: «Hay N \
estrategias igual de cercanas; el resto está en «Otras estrategias».» Escribes "podría \
corresponder a", no "corresponde a". No menciones puntajes ni porcentajes.
- La interfaz ya muestra arriba los términos buscados y los sinónimos aplicados: no los \
repitas.
- La línea «La estrategia se centra en…» resume SOLO el campo 'extracto' de esa opción, \
sin agregar nada que no esté ahí. Si el extracto viene vacío, escribe en su lugar «Esta \
estrategia no tiene descripción en el documento; sólo hay palabras clave.» No la completes \
con conocimiento general.
- Describes lo que dice el documento. No evalúas si la idea es buena, no recomiendas \
inversiones ni montos, no afirmas que algo "se debe" radicar en un lugar.
- Si la pregunta no es sobre ubicar algo en el PND, lo dices en una frase y no respondes \
con conocimiento general.
- La estructura del PND todavía está en elaboración. Si viene al caso, lo señalas.

FORMATO
Muy breve, tres líneas por opción, sin encabezados ni tablas:
«Opción sugerida: <código> · <nombre exacto de la estrategia>»
«Coincidencia directa: <término> en <campo>» (los más relevantes, separados por coma)
«La estrategia se centra en …» (según la regla del extracto)
No incluyas el eje ni el tema."""


def responder(client, historial):
    """Claude decide los términos -> se ejecuta la búsqueda -> Claude redacta.

    Devuelve (texto, llamadas, terminos):
      llamadas: detalle de cada llamada a herramienta, para la interfaz
      terminos: términos buscados, para resaltarlos en el árbol
    Los niveles y las coincidencias para el árbol salen de marcas_arbol(llamadas).
    """
    llamadas, terminos = [], set()

    mensajes = [m for m in historial if isinstance(m.get("content"), str)]
    mensajes = [{"role": m["role"], "content": m["content"]}
                for m in mensajes[-MAX_TURNOS_HISTORIAL:]]

    for _ in range(MAX_VUELTAS):
        resp = client.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS, system=SYSTEM_PROMPT,
            tools=TOOLS, messages=mensajes,
        )

        if resp.stop_reason != "tool_use":
            texto = "".join(b.text for b in resp.content if b.type == "text")
            return texto, llamadas, sorted(terminos)

        mensajes.append({"role": "assistant", "content": resp.content})
        resultados = []
        for bloque in resp.content:
            if bloque.type != "tool_use":
                continue
            func = DISPATCH.get(bloque.name)
            try:
                salida = func(**bloque.input) if func else {"error": "Herramienta desconocida."}
            except Exception as e:
                salida = {"error": f"Fallo al ejecutar {bloque.name}: {e}"}

            llamadas.append({"herramienta": bloque.name, "argumentos": bloque.input,
                             "resultado": salida})
            para_modelo = salida
            if isinstance(salida, dict):
                terminos.update(t for t in salida.get("terminos_buscados", []) if len(t) > 2)
                # Lo demás es para la interfaz; el modelo sólo ve las más cercanas.
                para_modelo = {k: v for k, v in salida.items() if k not in SOLO_INTERFAZ}

            resultados.append({"type": "tool_result", "tool_use_id": bloque.id,
                               "content": json.dumps(para_modelo, ensure_ascii=False)})
        mensajes.append({"role": "user", "content": resultados})

    return ("La consulta dio demasiadas vueltas y se detuvo. Intenta con una pregunta "
            "más concreta.", llamadas, sorted(terminos))


def marcas_arbol(llamadas):
    """Une lo que dejaron las búsquedas para el árbol.

    Devuelve (niveles, coincidencias): niveles = {'cercanas': [...], 'otras': [...],
    'relacionadas': [...]} con códigos de mejor a peor; coincidencias = {código:
    [{termino, campo}]}. Si un código sale en varias búsquedas, gana el mejor nivel.
    """
    orden = ("cercanas", "otras", "relacionadas")
    nivel, coincidencias = {}, {}
    for ll in llamadas:
        s = ll["resultado"]
        if not isinstance(s, dict):
            continue
        for i, clave in enumerate(orden):
            for cod in (s.get("niveles") or {}).get(clave, []):
                if cod not in nivel or i < orden.index(nivel[cod]):
                    nivel[cod] = clave
        for cod, evs in (s.get("coincidencias") or {}).items():
            coincidencias.setdefault(cod, evs)
        if s.get("codigo") and s["codigo"] not in nivel:   # ficha pedida por código
            nivel[s["codigo"]] = "cercanas"
    niveles = {k: [c for c, n in nivel.items() if n == k] for k in orden}
    return niveles, coincidencias
