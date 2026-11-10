"""
buscador.py — Búsqueda por coincidencia de palabras sobre la estructura del PND.
================================================================================
Aquí NO hay modelo de lenguaje, ni puntajes aprendidos, ni análisis semántico.
Todo es coincidencia de texto, en tres capas que se pueden explicar en una frase
cada una:

  Capa 1 — literal      : la palabra tal como se escribió (sin tildes ni mayúsculas).
  Capa 2 — raíz          : los primeros caracteres de la palabra, para que
                           "educativa" encuentre "educación" y "educativo".
  Capa 3 — sinónimos     : un diccionario en data/sinonimos.csv que traduce
                           palabras de uso corriente al vocabulario del documento
                           ("colegio" -> "infraestructura educativa").

Se busca en tres campos: palabras clave, nombre de la estrategia y tema. La
descripción es el último recurso: sólo se mira para un término que no apareció en
ningún otro campo.

El orden sale de un score que se explica en una línea: por cada término que coincide,
peso del campo x multiplicador de origen x especificidad del término (un término que
aparece en muchas estrategias vale poco). Lo calcula esta función, no el modelo: el
modelo sólo elige los términos. Los niveles (Top 1 / Top 2 / Top 3) son umbrales sobre
ese score, relativos al mejor. data/reglas.csv restringe grupos de estrategias (p. ej.
el eje 7, sólo para desastres) a las preguntas que mencionen sus palabras disparadoras.

Cada resultado viene con la evidencia: qué término coincidió y en qué campo.
"""

import math
import re
import unicodedata
from collections import Counter
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
ARCHIVO_ESTRUCTURA = DATA / "Estructura_PND_Palabras_claves.xlsx"
ARCHIVO_SINONIMOS = DATA / "sinonimos.csv"
ARCHIVO_REGLAS = DATA / "reglas.csv"

# Peso de cada campo: el orden de preferencia declarado. La descripción pesa poco y
# sólo entra como último recurso, para términos que no están en ningún otro campo.
PESO_CAMPO = {
    "palabras clave": 4,
    "nombre de la estrategia": 4,
    "tema": 3,
    "descripción": 1,
}

# Niveles, como fracción del mejor score. Se ajustan aquí, sin tocar lo demás.
UMBRAL_TOP1 = 0.80       # >= 80 % del mejor (los empates con el mejor siempre entran)
UMBRAL_TOP2 = 0.30       # >= 30 % del mejor; por debajo, Top 3
MAX_CHAT = 5             # Top 1 que se muestran en la respuesta
MAX_TOGGLE = 10          # estrategias en el desplegable «Otras estrategias»

# Palabras demasiado comunes para que una coincidencia signifique algo.
VACIAS = set("""de la el los las un una unos unas y o u a en con por para del al se su sus
lo le les que como mas más este esta estos estas ese esa eso aquel sobre entre sin desde
hasta ante tras durante mediante segun según e ni pero sino aunque si no es son ser estar
hay fue era sean sea haya tambien también cuando donde quien cual cuales cualquier todo
toda todos todas otro otra otros otras mismo misma cada muy mucho poco algo nada alguien
nadie quiero necesito busco saber donde cosa tema parte forma manera caso vez veces
hacer tener poner dar ir voy vamos remito refiero puedo podria podría debo tengo
nacional nacionales pais país colombia colombiano colombiana""".split())


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------
def normalizar(texto) -> str:
    """Minúsculas, sin tildes, sin signos, espacios colapsados."""
    s = str(texto).lower().strip()
    s = "".join(c for c in unicodedata.normalize("NFD", s)
                if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9ñ ]", " ", s)
    return " ".join(s.split())


def raiz(palabra: str) -> str:
    """Primeros caracteres de la palabra, para absorber plurales y género.

    Regla fija y visible:
      - 8 letras o más -> los primeros 6 caracteres
      - 6 o 7 letras   -> los primeros 5 caracteres
      - menos de 6     -> la palabra completa (cortarla produciría ruido)
    """
    n = len(palabra)
    if n >= 8:
        return palabra[:6]
    if n >= 6:
        return palabra[:5]
    return palabra


def palabras_utiles(texto: str) -> list:
    """Palabras de 4+ letras que no están en la lista de palabras vacías."""
    vistas, salida = set(), []
    for w in normalizar(texto).split():
        if len(w) >= 4 and w not in VACIAS and w not in vistas:
            vistas.add(w)
            salida.append(w)
    return salida


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------
_EST = None
_SIN = None

COLUMNAS = ["eje_n", "eje", "tema_n", "tema", "est_n", "est", "desc", "kw", "fuente"]


def cargar_estructura() -> pd.DataFrame:
    """Lee el Excel de estructura. Si el archivo se reemplaza por una versión
    nueva, basta reiniciar la aplicación: no hay nada codificado a mano."""
    global _EST
    if _EST is not None:
        return _EST

    df = pd.read_excel(ARCHIVO_ESTRUCTURA)
    if len(df.columns) < 9:
        raise ValueError(
            f"El archivo de estructura tiene {len(df.columns)} columnas y se esperaban 9. "
            "Revisa que sea el archivo correcto."
        )
    df = df.iloc[:, :9].copy()
    df.columns = COLUMNAS
    df = df[df["est_n"].notna()].reset_index(drop=True)

    df["eje_n"] = pd.to_numeric(df["eje_n"], errors="coerce").astype("Int64")
    for c in ["eje", "tema", "est", "desc", "kw", "fuente", "tema_n", "est_n"]:
        df[c] = df[c].fillna("").astype(str).str.strip()

    df["kw_lista"] = df["kw"].apply(
        lambda s: [p.strip() for p in s.split(";") if p.strip()]
    )

    # Texto normalizado por campo, calculado una sola vez.
    df["_kw"] = df["kw"].map(normalizar)
    df["_est"] = df["est"].map(normalizar)
    df["_tema"] = df["tema"].map(normalizar)
    df["_desc"] = df["desc"].map(normalizar)

    # Conjunto de raíces por campo, para la capa 2.
    for destino, origen in [("_r_kw", "_kw"), ("_r_est", "_est"),
                            ("_r_tema", "_tema"), ("_r_desc", "_desc")]:
        df[destino] = df[origen].apply(lambda t: {raiz(w) for w in t.split() if len(w) >= 4})

    _EST = df
    return _EST


def cargar_sinonimos() -> dict:
    """Diccionario editable: palabra corriente -> términos del documento.

    El archivo tiene dos columnas: 'palabra' y 'terminos_documento' (separados
    por ';'). Cualquiera puede abrirlo y agregar una fila; no hay que tocar código.
    """
    global _SIN
    if _SIN is not None:
        return _SIN
    _SIN = {}
    if ARCHIVO_SINONIMOS.exists():
        s = pd.read_csv(ARCHIVO_SINONIMOS)
        for _, r in s.iterrows():
            clave = normalizar(r["palabra"])
            if not clave:
                continue
            _SIN[clave] = [t.strip() for t in str(r["terminos_documento"]).split(";") if t.strip()]
    return _SIN


def catalogo() -> dict:
    """Resumen de la estructura, para el encabezado y el system prompt."""
    df = cargar_estructura()
    ejes = (df.groupby(["eje_n", "eje"], as_index=False)
              .agg(temas=("tema_n", "nunique"), estrategias=("est_n", "nunique"))
              .sort_values("eje_n"))
    return {
        "n_ejes": int(df["eje_n"].nunique()),
        "n_temas": int(df["tema"].nunique()),
        "n_estrategias": int(len(df)),
        "ejes": ejes.to_dict("records"),
        "temas": sorted(df["tema"].unique().tolist()),
    }


# ---------------------------------------------------------------------------
# Expansión de los términos de búsqueda
# ---------------------------------------------------------------------------
def expandir(terminos) -> list:
    """Agrega los sinónimos del diccionario a la lista de términos.

    Devuelve una lista de diccionarios {termino, origen}, donde origen es
    'escrito' (lo que pidió quien consulta) o 'diccionario: <palabra>'.
    """
    if isinstance(terminos, str):
        terminos = [terminos]
    sin = cargar_sinonimos()
    salida, vistos = [], set()

    def agregar(t, origen):
        n = normalizar(t)
        if n and n not in vistos:
            vistos.add(n)
            salida.append({"termino": n, "origen": origen})

    for t in terminos:
        agregar(t, "escrito")
        # El diccionario se consulta tanto por la frase completa como por
        # cada palabra suelta de la frase.
        for clave in [normalizar(t)] + palabras_utiles(t):
            for equivalente in sin.get(clave, []):
                agregar(equivalente, f"diccionario: {clave}")
    return salida


# ---------------------------------------------------------------------------
# Coincidencia de un término contra una estrategia
# ---------------------------------------------------------------------------
_CAMPOS = [
    ("palabras clave", "_kw", "_r_kw"),
    ("nombre de la estrategia", "_est", "_r_est"),
    ("tema", "_tema", "_r_tema"),
]
_CAMPO_DESC = ("descripción", "_desc", "_r_desc")   # sólo como último recurso


def _coincide(termino: str, fila, usar_raiz: bool, campos=_CAMPOS):
    """¿Aparece el término en esta estrategia? Devuelve (campo, tipo) o None.

    Recorre los campos en orden de peso y devuelve la primera coincidencia,
    de modo que se reporta el campo más relevante donde apareció.
    """
    palabras = [w for w in termino.split() if len(w) >= 3]
    if not palabras:
        return None

    # Capa 1: literal. Si el término es una frase, debe aparecer completa.
    for nombre, campo, _ in campos:
        if termino in fila[campo]:
            return nombre, "literal"

    if not usar_raiz:
        return None

    # Capa 2: raíz. Todas las palabras del término deben estar por su raíz.
    objetivo = {raiz(w) for w in palabras if len(w) >= 4}
    if not objetivo:
        return None
    for nombre, _, campo_raices in campos:
        if objetivo <= fila[campo_raices]:
            return nombre, "raíz"
    return None


# ---------------------------------------------------------------------------
# Búsqueda principal (esta es la herramienta que llama el modelo)
# ---------------------------------------------------------------------------
def _extracto(desc: str, n: int = 280) -> str:
    """Comienzo de la descripción, cortado en un punto si se puede. Es texto
    literal del documento: de aquí sale lo que el modelo resume."""
    d = " ".join(str(desc).split())
    if len(d) <= n:
        return d
    corte = d.rfind(". ", 0, n)
    return d[:corte + 1] if corte > n // 2 else d[:n].rstrip() + "…"


_REGLAS = None


def cargar_reglas() -> list:
    """data/reglas.csv: grupos de estrategias que sólo se sugieren (Top 1 o Top 2) si
    la pregunta menciona alguna palabra disparadora; si no, quedan en Top 3.

    Columnas: 'aplica_a' ('eje 7', 'tema 7.1' o un código como '7.1.3'),
    'palabras_disparadoras' (separadas por ';') y 'nota' (la frase que se muestra
    cuando la regla actúa). Se edita en Excel, sin tocar código.
    """
    global _REGLAS
    if _REGLAS is not None:
        return _REGLAS
    _REGLAS = []
    if ARCHIVO_REGLAS.exists():
        tabla = pd.read_csv(ARCHIVO_REGLAS, encoding="utf-8-sig").fillna("")
        for _, f in tabla.iterrows():
            gatillos = [normalizar(g) for g in str(f["palabras_disparadoras"]).split(";")
                        if normalizar(g)]
            if str(f["aplica_a"]).strip() and gatillos:
                _REGLAS.append({"aplica_a": str(f["aplica_a"]).strip(),
                                "gatillos": gatillos, "nota": str(f["nota"]).strip()})
    return _REGLAS


def validar_reglas() -> None:
    """Falla al arrancar, con un mensaje claro, si reglas.csv apunta a algo que no
    existe o quedó mal armado (p. ej. una nota con comas sin comillas)."""
    df = cargar_estructura()
    for r in cargar_reglas():
        if not _codigos_de(df, r["aplica_a"]):
            raise ValueError(
                f"data/reglas.csv: no encontré estrategias para «{r['aplica_a']}». "
                "Usa 'eje 7', 'tema 7.1' o un código como '7.1.3'. Si una nota lleva "
                "comas, debe ir entre comillas.")


def _codigos_de(df, aplica_a: str) -> set:
    a = aplica_a.strip().lower()
    if a.startswith("eje"):
        return set(df[df["eje_n"].astype(str) == a[3:].strip()]["est_n"])
    if a.startswith("tema"):
        return set(df[df["tema_n"] == a[4:].strip()]["est_n"])
    return set(df[df["est_n"] == aplica_a.strip()]["est_n"])


def _menciona(gatillos, expandidos) -> bool:
    """¿Alguna palabra disparadora está entre los términos que llegaron a la búsqueda
    (no cuentan los que agregó el diccionario)? Se compara por raíz: «incendios»
    dispara «incendio»."""
    raices = {raiz(w) for e in expandidos if e["origen"] == "escrito"
              for w in e["termino"].split() if len(w) >= 4}
    for g in gatillos:
        rs = [raiz(w) for w in g.split() if len(w) >= 4]
        if rs and all(r in raices for r in rs):
            return True
    return False


def _restringidas(df, expandidos):
    """Códigos cuya regla no se cumple en esta búsqueda, y la nota de cada regla."""
    codigos, avisos = set(), []
    for regla in cargar_reglas():
        if not _menciona(regla["gatillos"], expandidos):
            afectados = _codigos_de(df, regla["aplica_a"])
            codigos |= afectados
            avisos.append((afectados, regla["nota"]))
    return codigos, avisos


def _cortar_sin_partir_empates(lista, n):
    """Las primeras n; si el corte parte un grupo empatado, el grupo entero queda
    fuera: dos estrategias con el mismo score nunca reciben trato distinto."""
    if len(lista) <= n:
        return lista
    if n <= 0:
        return []
    if lista[n - 1]["score"] != lista[n]["score"]:
        return lista[:n]
    empate = lista[n]["score"]
    return [r for r in lista[:n] if r["score"] != empate]


def _ev(e, h):
    return {"termino": e["termino"], "origen": e["origen"], "campo": h[0], "tipo": h[1]}


def buscar_estrategias(terminos, usar_raiz: bool = True) -> dict:
    """Busca estrategias del PND que contengan los términos dados.

    No interpreta la intención ni redacta nada. Devuelve:
      resultados    las Top 1 (hasta MAX_CHAT), con evidencia: lo único que ve el modelo.
      otras         las siguientes (hasta MAX_TOGGLE), con evidencia: sólo interfaz.
      niveles       códigos de TODAS las que coincidieron, por nivel: sólo árbol.
      coincidencias qué término coincidió en qué campo, por código: sólo árbol.
      avisos_reglas notas de las reglas que actuaron: sólo interfaz.
    """
    df = cargar_estructura()
    expandidos = expandir(terminos)
    if not expandidos:
        return {"terminos_buscados": [], "n_resultados": 0, "resultados": [],
                "mensaje": "No se recibió ningún término de búsqueda."}

    # 1) Evidencia en palabras clave, nombre y tema.
    filas = {}                                   # índice de la fila -> (fila, evidencia)
    for idx, fila in df.iterrows():
        for e in expandidos:
            h = _coincide(e["termino"], fila, usar_raiz)
            if h:
                filas.setdefault(idx, (fila, []))[1].append(_ev(e, h))

    # 1b) Último recurso: un término que no apareció en ningún campo anterior se
    #     busca en las descripciones.
    encontrados = {ev["termino"] for _, evs in filas.values() for ev in evs}
    for e in expandidos:
        if e["termino"] in encontrados:
            continue
        for idx, fila in df.iterrows():
            h = _coincide(e["termino"], fila, usar_raiz, campos=[_CAMPO_DESC])
            if h:
                filas.setdefault(idx, (fila, []))[1].append(_ev(e, h))

    # 2) Especificidad: un término que aparece en muchas estrategias dice poco.
    #    vale ln(total / estrategias donde aparece): 1 de 123 -> 4.8; 26 de 123 -> 1.6.
    n_total = len(df)
    n_por_termino = Counter(ev["termino"] for _, evs in filas.values() for ev in evs)
    especificidad = {t: math.log(n_total / n) for t, n in n_por_termino.items()}

    # 3) Score = suma, por cada término que coincide, de
    #    peso del campo x multiplicador del origen x especificidad.
    resultados = []
    for fila, evidencia in filas.values():
        score = sum(PESO_CAMPO[ev["campo"]] * (2 if ev["origen"] == "escrito" else 1)
                    * especificidad[ev["termino"]] for ev in evidencia)
        resultados.append({
            "codigo": fila["est_n"],
            "estrategia": fila["est"],
            "eje": f"{fila['eje_n']}. {fila['eje']}",
            "tema": f"{fila['tema_n']} {fila['tema']}".strip(),
            "palabras_clave": fila["kw_lista"],
            "tiene_descripcion": bool(fila["desc"]),
            "extracto": _extracto(fila["desc"]),
            "n_terminos_coincidentes": len({ev["termino"] for ev in evidencia}),
            "score": round(score, 3),
            "coincidencias": evidencia,
        })
    # Mismo score = mismo trato; el código sólo ordena de forma estable.
    resultados.sort(key=lambda r: (-r["score"], r["codigo"]))

    # 4) Reglas: lo restringido (p. ej. eje 7 sin hablar de desastres) queda en Top 3.
    #    Si TODO lo que coincidió es restringido, se muestra igual: no hay otra cosa.
    restringidas, avisos = _restringidas(df, expandidos)
    if all(r["codigo"] in restringidas for r in resultados):
        restringidas, avisos = set(), []
    mejor = max((r["score"] for r in resultados if r["codigo"] not in restringidas), default=0)

    # 5) Niveles, como fracción del mejor score.
    for r in resultados:
        frac = r["score"] / mejor if mejor else 1.0
        r["pct_del_mejor"] = round(100 * frac)
        if r["codigo"] in restringidas:
            r["nivel"] = "top3"
        else:
            r["nivel"] = ("top1" if frac >= UMBRAL_TOP1
                          else "top2" if frac >= UMBRAL_TOP2 else "top3")
    top1 = [r for r in resultados if r["nivel"] == "top1"]
    candidatas = [r for r in resultados if r["nivel"] == "top2"]

    en_chat = top1[:MAX_CHAT]
    sobran = top1[MAX_CHAT:]              # igual de cercanas, pero no caben en el chat
    top2 = _cortar_sin_partir_empates(candidatas, MAX_TOGGLE - len(sobran))
    en_top2 = {r["codigo"] for r in top2}
    for r in candidatas:
        if r["codigo"] not in en_top2:
            r["nivel"] = "top3"

    # Qué palabra disparó qué sinónimos, para mostrarlo tal cual en la interfaz.
    aplicados = {}
    for e in expandidos:
        if e["origen"].startswith("diccionario: "):
            aplicados.setdefault(e["origen"][len("diccionario: "):], []).append(e["termino"])

    def codigos(nivel):
        return [r["codigo"] for r in resultados if r["nivel"] == nivel]

    # Aviso sólo si la regla movió algo: una restringida que, sin la regla, habría
    # llegado a Top 1 o Top 2.
    movidas = {r["codigo"] for r in resultados
               if r["codigo"] in restringidas and mejor and r["score"] >= UMBRAL_TOP2 * mejor}
    return {
        "terminos_buscados": [e["termino"] for e in expandidos],
        "terminos_del_diccionario": [e["termino"] for e in expandidos if e["origen"] != "escrito"],
        "sinonimos_aplicados": [{"palabra": k, "terminos": v} for k, v in aplicados.items()],
        "n_resultados": len(resultados),
        "n_top1": len(top1),
        "resultados": en_chat,
        "otras": (sobran + top2)[:MAX_TOGGLE],
        "niveles": {"top1": codigos("top1"), "top2": codigos("top2"), "top3": codigos("top3")},
        "coincidencias": {r["codigo"]: [{"termino": ev["termino"], "campo": ev["campo"]}
                                        for ev in r["coincidencias"]] for r in resultados},
        "avisos_reglas": [nota for cods, nota in avisos if cods & movidas and nota],
        "mensaje": ("Ninguna estrategia contiene esos términos."
                    if not resultados else ""),
    }


def listar_vocabulario(fragmento: str = "", limite: int = 40) -> dict:
    """Devuelve palabras clave del documento que contienen un fragmento.

    Sirve para cuando la búsqueda no encuentra nada: en vez de inventar, el
    asistente puede mostrar qué vocabulario sí existe en el documento.
    """
    df = cargar_estructura()
    frag = normalizar(fragmento)
    conteo = {}
    for _, fila in df.iterrows():
        for p in fila["kw_lista"]:
            if not frag or frag in normalizar(p):
                conteo.setdefault(p, []).append(fila["est_n"])
    items = sorted(conteo.items(), key=lambda kv: (-len(kv[1]), kv[0]))[:limite]
    return {"fragmento": fragmento, "n": len(conteo),
            "palabras_clave": [{"palabra": k, "estrategias": v} for k, v in items]}


def detalle_estrategia(codigo: str) -> dict:
    """Ficha completa de una estrategia por su código (ej. '2.1.3')."""
    df = cargar_estructura()
    f = df[df["est_n"].str.strip() == str(codigo).strip()]
    if f.empty:
        return {"error": f"No existe la estrategia '{codigo}'."}
    r = f.iloc[0]
    return {
        "codigo": r["est_n"], "estrategia": r["est"],
        "eje": f"{r['eje_n']}. {r['eje']}", "tema": f"{r['tema_n']} {r['tema']}".strip(),
        "descripcion": r["desc"] or "(esta estrategia no tiene descripción en el archivo)",
        "palabras_clave": r["kw_lista"], "fuente": r["fuente"],
    }


if __name__ == "__main__":
    import json
    for pregunta in ["quiero construir un colegio", "becas de estudio",
                     "agua potable en zona rural", "quiero sembrar papa"]:
        print("=" * 70)
        print("PREGUNTA:", pregunta)
        r = buscar_estrategias(palabras_utiles(pregunta))
        print("  términos:", r["terminos_buscados"])
        for x in r["resultados"][:4]:
            ev = "; ".join(f"{c['termino']} en {c['campo']} ({c['tipo']})"
                           for c in x["coincidencias"])
            print(f"  {x['codigo']}  {x['estrategia'][:58]}")
            print(f"        {ev}")
        if not r["resultados"]:
            print("  ", r["mensaje"])
