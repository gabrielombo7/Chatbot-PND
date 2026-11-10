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

El orden de los resultados también es una regla, no un puntaje:
  1) cuántos de los términos buscados aparecen en la estrategia;
  2) en qué campo aparecen (palabras clave y nombre pesan más que la descripción).

Cada resultado viene con la evidencia: qué término coincidió y en qué campo.
"""

import re
import unicodedata
from pathlib import Path

import pandas as pd

DATA = Path(__file__).parent / "data"
ARCHIVO_ESTRUCTURA = DATA / "Estructura_PND_Palabras_claves.xlsx"
ARCHIVO_SINONIMOS = DATA / "sinonimos.csv"

# Peso de cada campo. No es un puntaje estadístico: es el orden de preferencia
# declarado. Si una palabra aparece en las palabras clave, vale más que si
# aparece sólo en el cuerpo de la descripción.
PESO_CAMPO = {
    "palabras clave": 4,
    "nombre de la estrategia": 4,
    "tema": 3,
    "descripción": 1,
}

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
    ("descripción", "_desc", "_r_desc"),
]


def _coincide(termino: str, fila, usar_raiz: bool):
    """¿Aparece el término en esta estrategia? Devuelve (campo, tipo) o None.

    Recorre los campos en orden de peso y devuelve la primera coincidencia,
    de modo que se reporta el campo más relevante donde apareció.
    """
    palabras = [w for w in termino.split() if len(w) >= 3]
    if not palabras:
        return None

    # Capa 1: literal. Si el término es una frase, debe aparecer completa.
    for nombre, campo, _ in _CAMPOS:
        if termino in fila[campo]:
            return nombre, "literal"

    if not usar_raiz:
        return None

    # Capa 2: raíz. Todas las palabras del término deben estar por su raíz.
    objetivo = {raiz(w) for w in palabras if len(w) >= 4}
    if not objetivo:
        return None
    for nombre, _, campo_raices in _CAMPOS:
        if objetivo <= fila[campo_raices]:
            return nombre, "raíz"
    return None


# ---------------------------------------------------------------------------
# Búsqueda principal (esta es la herramienta que llama el modelo)
# ---------------------------------------------------------------------------
def buscar_estrategias(terminos, max_resultados: int = 8, usar_raiz: bool = True) -> dict:
    """Busca estrategias del PND que contengan los términos dados.

    No interpreta la intención ni redacta nada: devuelve las estrategias donde
    los términos aparecen, con la evidencia de dónde apareció cada uno.
    """
    df = cargar_estructura()
    expandidos = expandir(terminos)
    if not expandidos:
        return {"terminos_buscados": [], "n_resultados": 0, "resultados": [],
                "mensaje": "No se recibió ningún término de búsqueda."}

    resultados = []
    for _, fila in df.iterrows():
        evidencia, peso = [], 0
        for e in expandidos:
            hallazgo = _coincide(e["termino"], fila, usar_raiz)
            if hallazgo:
                campo, tipo = hallazgo
                evidencia.append({"termino": e["termino"], "origen": e["origen"],
                                  "campo": campo, "tipo": tipo})
                # Las palabras que escribió la persona pesan el doble que las
                # que agregó el diccionario de sinónimos.
                factor = 2 if e["origen"] == "escrito" else 1
                peso += PESO_CAMPO[campo] * factor
        if evidencia:
            resultados.append({
                "codigo": fila["est_n"],
                "estrategia": fila["est"],
                "eje": f"{fila['eje_n']}. {fila['eje']}",
                "tema": f"{fila['tema_n']} {fila['tema']}".strip(),
                "palabras_clave": fila["kw_lista"],
                "tiene_descripcion": bool(fila["desc"]),
                "n_terminos_coincidentes": len({ev["termino"] for ev in evidencia}),
                "peso_campos": peso,
                "coincidencias": evidencia,
            })

    # Regla de orden: más términos distintos primero; a igual número de
    # términos, primero donde coincidieron en campos de mayor peso.
    resultados.sort(key=lambda r: (-r["n_terminos_coincidentes"], -r["peso_campos"], r["codigo"]))

    recortados = resultados[:max_resultados]
    return {
        "terminos_buscados": [e["termino"] for e in expandidos],
        "terminos_del_diccionario": [e["termino"] for e in expandidos if e["origen"] != "escrito"],
        "n_resultados": len(resultados),
        "n_mostrados": len(recortados),
        "resultados": recortados,
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
