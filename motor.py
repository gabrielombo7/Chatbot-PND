"""
motor.py — Ciclo de conversación del orientador (independiente de la interfaz).
===============================================================================
El modelo cumple una sola función: traducir lo que escribe la persona al vocabulario
del Plan y elegir los términos de búsqueda (o pedir un dato que falta). Para eso ve el
catálogo oficial —códigos, nombres y palabras clave—, pero NO redacta los resultados:

  * Las líneas estratégicas de la respuesta las escribe este módulo desde el libro de
    estructura (código, nombre y palabras clave tal cual), a partir de lo que devolvió
    buscador.py. El modelo no interviene en ese texto.
  * Si el modelo contesta sin buscar y nombra un código o una línea que ninguna
    herramienta devolvió, su texto se descarta y se busca con las palabras de la persona.

Así, aunque el modelo conozca el catálogo, no puede presentar como resultado una línea
que la búsqueda no encontró.
"""

import json
import re

import buscador as B

MODELO = "claude-haiku-4-5"
MAX_TOKENS = 1200
MAX_VUELTAS = 6          # tope de iteraciones del ciclo de herramientas
MAX_TURNOS_HISTORIAL = 8  # cuántos mensajes previos se reenvían al modelo
# Claves del resultado de la búsqueda que sólo usa la interfaz (el modelo no las ve).
SOLO_INTERFAZ = ("niveles", "coincidencias", "avisos_reglas", "n_omitidas")
MAX_PALABRAS_CLAVE = 4    # palabras clave que se muestran por opción en la respuesta

CAT = B.catalogo()

TOOLS = [
    {
        "name": "buscar_estrategias",
        "description": (
            "Busca líneas estratégicas del PND que contengan ciertos términos. Es una "
            "búsqueda de texto: encuentra la línea estratégica sólo si el término aparece "
            "escrito en sus palabras clave, en su nombre o en el nombre de su tema.\n\n"
            "Pasa de 3 a 6 términos: palabras clave o fragmentos de nombre de las líneas "
            "del catálogo donde cabría la idea, tal cual están escritos allí, más las "
            "palabras que usó la persona. Ejemplos:\n"
            "- 'construir un acueducto' -> ['acueducto', 'Agua potable', 'Calidad del agua', "
            "'Servicios públicos']\n"
            "- 'cancha sintética' -> ['cancha', 'Escenarios deportivos', 'Construcción de "
            "escenarios', 'Deporte']\n"
            "- 'becas de estudio' -> ['becas', 'Educación superior', 'Permanencia', "
            "'Graduación']\n\n"
            "Usa términos cortos (una a cuatro palabras). Omite verbos, municipios y "
            "palabras de trámite como 'construcción', 'mejoramiento' o 'estudios y diseños'."
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
            "Ficha completa de una línea estratégica por su código, por ejemplo '2.1.3'. "
            "Úsala cuando la persona pregunte por una línea estratégica puntual o pida "
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


def catalogo_texto() -> str:
    """El catálogo oficial en texto plano, para que el modelo elija términos que existen:
    ejes, temas (con su descripción) y líneas estratégicas (nombre | palabras clave)."""
    df = B.cargar_estructura()
    filas, eje_ant, tema_ant = [], None, None
    for _, r in df.iterrows():
        if r["eje_n"] != eje_ant:
            eje_ant = r["eje_n"]
            filas.append(f"\nEJE {r['eje_n']}. {r['eje']}")
        if r["tema_n"] != tema_ant:
            tema_ant = r["tema_n"]
            filas.append(f"  TEMA {r['tema_n']} {r['tema']}: {r['tema_desc']}")
        filas.append(f"    {r['est_n']} {r['est']} | {'; '.join(r['kw_lista'])}")
    return "\n".join(filas)


SYSTEM_PROMPT = f"""Orientas a servidores públicos y equipos sectoriales sobre en qué \
parte del Plan Nacional de Desarrollo 2026-2030 se ubicaría una idea, un proyecto o un \
programa. Tu alcance es exactamente ese: ubicar en la estructura eje → tema → línea estratégica.

TU TRABAJO
Eres el traductor entre el lenguaje de la persona y el vocabulario del Plan. No redactas los \
resultados: la interfaz muestra las líneas estratégicas que devuelve la herramienta \
buscar_estrategias, con su código, su nombre y sus palabras clave tal como están en el \
documento. Tú sólo eliges los términos de búsqueda y, cuando falta un dato, haces una pregunta.

CATÁLOGO OFICIAL DEL PLAN ({CAT['n_ejes']} ejes, {CAT['n_temas']} temas, {CAT['n_estrategias']} líneas \
estratégicas). Cada línea va como «código nombre | palabras clave». Sirve para elegir términos \
que existen en el documento, nada más.
{catalogo_texto()}

CÓMO TRABAJAS
1. Para cada idea o proyecto llamas buscar_estrategias de inmediato, incluso si la persona \
escribe una sola palabra común (por ejemplo «infraestructura»). El texto puede ser el nombre \
de un proyecto, con municipios, verbos y palabras de trámite («construcción», «mejoramiento», \
«estudios y diseños»): ignóralos y quédate con lo que el proyecto ES: qué se construye o se \
hace, qué servicio presta, a quién sirve.
2. Elige los términos mirando el catálogo: ubica las 1 a 3 líneas donde cabría la idea y pasa \
de 3 a 6 términos tomados tal cual de sus palabras clave o de su nombre, más las palabras que \
usó la persona. Prefiere los términos específicos («Agua potable», «Escenarios deportivos») a \
los genéricos («Infraestructura», «Información»), salvo que la idea misma sea genérica. La \
herramienta es literal: sólo encuentra lo que está escrito en las palabras clave, el nombre o \
el tema de las líneas.
3. Si la pregunta habla de un desastre (terremoto, sismo, incendio, inundación…), incluye esa \
palabra entre los términos.
4. Si la búsqueda no devuelve resultados, prueba una vez más con términos más generales. Si \
sigue vacía, llama listar_vocabulario y di qué vocabulario existe.
5. Si el texto no dice qué es el proyecto (una sigla o un nombre propio, como «AVEM Fase 1»), \
no busques: pide en una frase qué se construye o a quién sirve.

REGLAS ESTRICTAS
- Nunca escribes códigos ni nombres de líneas estratégicas, ni siquiera los del catálogo: sólo \
la interfaz los muestra, y sólo los que devolvió la búsqueda. Si los escribes, tu respuesta se \
descarta.
- No evalúas si la idea es buena, no recomiendas inversiones ni montos, no afirmas que algo \
"se debe" radicar en un lugar.
- Si la pregunta no es sobre ubicar algo en el Plan, lo dices en una frase y no respondes con \
conocimiento general."""

# El mismo texto, en el formato que permite guardarlo en caché: es largo y no cambia.
SYSTEM_BLOQUES = [{"type": "text", "text": SYSTEM_PROMPT,
                   "cache_control": {"type": "ephemeral"}}]

MSG_SIN_RESULTADOS = ("No encontré líneas estratégicas con esas palabras. Cuéntame con otras "
                      "palabras qué se construye o a quién sirve el proyecto.")
MSG_DEMASIADAS_VUELTAS = ("La consulta dio demasiadas vueltas y se detuvo. Intenta con una "
                          "pregunta más concreta.")


# ---------------------------------------------------------------------------
# Texto de la respuesta: lo escribe el código, desde los datos
# ---------------------------------------------------------------------------
_ETIQUETA_CAMPO = {
    "palabras clave": "palabras clave",
    "nombre de la línea estratégica": "el nombre",
    "tema": "el tema",
    "descripción del tema": "la descripción del tema",
}
_ORDEN_CAMPO = {"palabras clave": 0, "nombre de la línea estratégica": 1, "tema": 2,
                "descripción del tema": 3}


def _como_en_el_plan(termino, campo, kw_lista):
    """Si el término coincidió en las palabras clave, devuelve la palabra clave tal como
    está escrita en el documento; si no, el término."""
    if campo != "palabras clave":
        return termino
    t = B.normalizar(termino)
    for k in kw_lista:
        if t and t in B.normalizar(k):
            return k
    raices = {B.raiz(w) for w in t.split() if len(w) >= 4}
    if raices:
        for k in kw_lista:
            if raices <= {B.raiz(w) for w in B.normalizar(k).split() if len(w) >= 4}:
                return k
    return termino


def _evidencia(coincidencias, kw_lista, maximo=3):
    """«X» en palabras clave, «Y» en el nombre…: lo más relevante primero (palabras clave,
    luego nombre y tema; antes lo que escribió la persona que lo que agregó el diccionario)."""
    ordenadas = sorted(coincidencias, key=lambda c: (_ORDEN_CAMPO.get(c["campo"], 9),
                                                     0 if c.get("origen", "escrito") == "escrito" else 1))
    vistas, partes = set(), []
    for c in ordenadas:
        texto = _como_en_el_plan(c["termino"], c["campo"], kw_lista)
        clave = B.normalizar(texto)          # cada término una vez, en su campo más relevante
        if clave in vistas:
            continue
        vistas.add(clave)
        partes.append(f"«{texto}» en {_ETIQUETA_CAMPO.get(c['campo'], c['campo'])}")
        if len(partes) == maximo:
            break
    return ", ".join(partes)


def _bloque(codigo, nombre, kw_lista, evidencia):
    lineas = [f"**Opción sugerida: {codigo} · {nombre}**"]
    if evidencia:
        lineas.append(f"Coincidencia directa: {evidencia}")
    lineas.append("La línea estratégica se centra en: " + ", ".join(kw_lista[:MAX_PALABRAS_CLAVE]))
    return "  \n".join(lineas)


def texto_busqueda(s: dict) -> str:
    """La respuesta para un resultado de buscar_estrategias: sólo líneas que devolvió la
    búsqueda, con su código, nombre y palabras clave tal cual, y dónde coincidió cada una."""
    partes = []
    resultados = s.get("resultados") or []
    if resultados:
        if s.get("muy_amplia"):
            sug = s.get("sugerencias") or []
            cola = (f" Por ahora, {len(resultados)} de las {s['n_cercanas']} más cercanas; el resto "
                    "está en el árbol." if s.get("n_cercanas", 0) > len(resultados)
                    else " Por ahora, estas opciones:")
            partes.append("Esto da muchos resultados. ¿De qué tipo es tu idea?"
                          + (" Por ejemplo: " + ", ".join(sug) + "." if sug else "") + cola)
        for r in resultados:
            partes.append(_bloque(r["codigo"], r["estrategia"], r["palabras_clave"],
                                  _evidencia(r.get("coincidencias") or [], r["palabras_clave"])))
    elif s.get("en_descripcion"):
        partes.append("Ninguna línea estratégica coincide en sus palabras clave ni en su nombre; "
                      "estas mencionan el término en la descripción de su tema:")
        coinc = s.get("coincidencias") or {}
        for e in s["en_descripcion"]:
            ev = _evidencia([dict(c, origen="escrito") for c in coinc.get(e["codigo"], [])],
                            e["palabras_clave"])
            partes.append(_bloque(e["codigo"], e["estrategia"], e["palabras_clave"], ev))
    else:
        partes.append(MSG_SIN_RESULTADOS)
    return "\n\n".join(partes)


def texto_ficha(f: dict) -> str:
    """La ficha de una línea estratégica (detalle_estrategia), tal cual está en el libro."""
    return "  \n".join([
        f"**{f['codigo']} · {f['estrategia']}**",
        f"Eje: {f['eje']}",
        f"Tema: {f['tema']}",
        "Palabras clave: " + ", ".join(f["palabras_clave"]),
        "Descripción del tema: " + str(f.get("descripcion_del_tema", "")),
    ])


# ---------------------------------------------------------------------------
# Candado: el modelo no puede presentar una línea que la búsqueda no devolvió
# ---------------------------------------------------------------------------
_RE_CODIGO = re.compile(r"(?<![\d.])\d\.\d{1,2}\.\d{1,2}(?![\d])")
_NOMBRES = {r["est_n"]: " " + B.normalizar(r["est"]) + " "
            for _, r in B.cargar_estructura().iterrows()}


def lineas_ajenas(texto: str, permitidos) -> list:
    """Códigos de líneas estratégicas (o líneas por su nombre) que aparecen en el texto y
    no están entre los permitidos (los que devolvió alguna herramienta)."""
    malos = {c for c in _RE_CODIGO.findall(texto) if c not in permitidos}
    plano = " " + B.normalizar(texto) + " "
    malos |= {cod for cod, nombre in _NOMBRES.items() if cod not in permitidos and nombre in plano}
    return sorted(malos)


def _ultima_pregunta(historial) -> str:
    for m in reversed(historial):
        if m.get("role") == "user" and isinstance(m.get("content"), str):
            return m["content"]
    return ""


def _cerrar(texto_modelo, llamadas, terminos, vistos, historial):
    """Arma la respuesta final (texto, llamadas, términos). Prioridad: lo que devolvió una
    búsqueda con resultados; una ficha pedida por código; el texto del modelo si no nombra
    líneas ajenas; y, si las nombra, una búsqueda con las palabras de la persona."""
    busquedas = [ll["resultado"] for ll in llamadas
                 if ll["herramienta"] == "buscar_estrategias"
                 and isinstance(ll["resultado"], dict) and ll["resultado"].get("n_resultados")]
    if busquedas:
        return texto_busqueda(busquedas[-1]), llamadas, sorted(terminos)

    fichas = [ll["resultado"] for ll in llamadas if ll["herramienta"] == "detalle_estrategia"
              and isinstance(ll["resultado"], dict) and not ll["resultado"].get("error")]
    if fichas:
        return texto_ficha(fichas[-1]), llamadas, sorted(terminos)

    if texto_modelo.strip() and not lineas_ajenas(texto_modelo, vistos):
        return texto_modelo.strip(), llamadas, sorted(terminos)

    # El modelo no devolvió nada utilizable, o nombró líneas sin buscarlas: se busca con
    # las palabras de la persona y se responde con lo que salga.
    terms = B.palabras_utiles(_ultima_pregunta(historial))
    if not terms:
        return MSG_SIN_RESULTADOS, llamadas, sorted(terminos)
    s = B.buscar_estrategias(terms)
    llamadas.append({"herramienta": "buscar_estrategias", "argumentos": {"terminos": terms},
                     "resultado": s})
    terminos.update(t for t in s.get("terminos_buscados", []) if len(t) > 2)
    return texto_busqueda(s), llamadas, sorted(terminos)


def responder(client, historial):
    """Claude elige los términos -> se ejecuta la búsqueda -> el código redacta la respuesta.

    Devuelve (texto, llamadas, terminos):
      llamadas: detalle de cada llamada a herramienta, para la interfaz
      terminos: términos buscados, para resaltarlos en el árbol
    Los niveles y las coincidencias para el árbol salen de marcas_arbol(llamadas).
    """
    llamadas, terminos = [], set()

    mensajes = [m for m in historial if isinstance(m.get("content"), str)]
    mensajes = [{"role": m["role"], "content": m["content"]}
                for m in mensajes[-MAX_TURNOS_HISTORIAL:]]
    # Códigos que el modelo puede mencionar sin buscar: los que ya se mostraron antes.
    vistos = {c for m in mensajes if m["role"] == "assistant" for c in _RE_CODIGO.findall(m["content"])}

    for _ in range(MAX_VUELTAS):
        resp = client.messages.create(
            model=MODELO, max_tokens=MAX_TOKENS, system=SYSTEM_BLOQUES,
            tools=TOOLS, messages=mensajes,
        )

        if resp.stop_reason != "tool_use":
            texto = "".join(b.text for b in resp.content if b.type == "text")
            return _cerrar(texto, llamadas, terminos, vistos, historial)

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

            contenido = json.dumps(para_modelo, ensure_ascii=False)
            vistos.update(_RE_CODIGO.findall(contenido))
            resultados.append({"type": "tool_result", "tool_use_id": bloque.id,
                               "content": contenido})
        mensajes.append({"role": "user", "content": resultados})

        # Con resultados no hace falta otra vuelta: la respuesta sale de los datos.
        if any(ll["herramienta"] in ("buscar_estrategias", "detalle_estrategia")
               and isinstance(ll["resultado"], dict)
               and (ll["resultado"].get("n_resultados") or ll["resultado"].get("codigo"))
               for ll in llamadas):
            return _cerrar("", llamadas, terminos, vistos, historial)

    return MSG_DEMASIADAS_VUELTAS, llamadas, sorted(terminos)


def marcas_arbol(llamadas):
    """Une lo que dejaron las búsquedas para el árbol.

    Devuelve (niveles, coincidencias): niveles = {'cercanas': [...], 'relacionadas': [...],
    'descripcion': [...]} con códigos de mejor a peor; coincidencias = {código:
    [{termino, campo}]}. Si un código sale en varias búsquedas, gana el mejor nivel.
    """
    orden = ("cercanas", "relacionadas", "descripcion")
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
