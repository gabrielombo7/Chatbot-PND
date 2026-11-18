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

Se busca en tres campos: palabras clave, nombre de la línea estratégica y nombre del tema. La
línea estratégica no tiene descripción; las descripciones de eje y tema sólo se muestran.

El orden sale de un score que se explica en una línea: por cada término que coincide,
peso del campo x multiplicador de origen x especificidad del término (un término que
aparece en muchas líneas estratégicas vale poco; uno muy raro no pasa de cierto tope). Lo calcula esta función, no el modelo: el
modelo sólo elige los términos. Los niveles (Más cercanas / Relacionadas) son umbrales sobre
ese score, relativos al mejor (Más cercanas: desde el 85 % y como máximo 3); lo que queda por debajo no se muestra. «En la descripción»
es una categoría aparte, sin puntaje: líneas estratégicas cuyo tema menciona el término en su descripción. data/reglas.csv restringe grupos de líneas estratégicas (p. ej.
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


def firma_archivos() -> tuple:
    """Fecha de modificación del código y de los datos de los que depende la aplicación.

    app.py la compara con la que tenía este módulo al cargarse: si cambió algo en disco
    (un despliegue nuevo), recarga los módulos y vacía la caché, en vez de seguir con
    versiones viejas en memoria. Sin esto, Streamlit Cloud puede quedarse con un módulo
    viejo y fallar con «module 'buscador' has no attribute …» hasta reiniciar la app a mano.
    """
    carpeta = Path(__file__).parent
    rutas = [carpeta / n for n in ("arbol.py", "buscador.py", "motor.py")] + sorted(DATA.glob("*"))
    return tuple((r.name, r.stat().st_mtime_ns) for r in rutas if r.exists())


_FIRMA = firma_archivos()

# Peso de cada campo: el orden de preferencia declarado.
PESO_CAMPO = {
    "palabras clave": 4,
    "nombre de la línea estratégica": 4,
    "tema": 3,
}

# Si un término coincide en más de un campo de la misma línea, cada campo adicional suma
# esta fracción de su peso (confirma que la línea trata de eso, sin duplicar el puntaje).
OTROS_CAMPOS = 0.5

# Un término que aparece en menos estrategias que esto cuenta como si apareciera en
# tantas: evita que una sola palabra rara (p. ej. un homónimo) domine el resultado.
MIN_ESTRATEGIAS_ESPECIFICIDAD = 3

# Niveles, como fracción del mejor score. Se ajustan aquí, sin tocar lo demás.
UMBRAL_CERCANAS = 0.85       # «Más cercanas»: >= 85 % del mejor...
MAX_CERCANAS = 3             # ...y como máximo 3 (las que sobran pasan a «Relacionadas»)
UMBRAL_RELACIONADAS = 0.30   # «Relacionadas»: >= 30 % del mejor; por debajo no se muestra
MAX_RELACIONADAS = 10        # tope de «Relacionadas» (lo que sobra no se muestra)
MAX_SUGERENCIAS = 6          # opciones que se ofrecen para concretar una consulta amplia

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

    Regla fija y visible (la misma en arbol.py):
      - 8 letras o más -> los primeros 7 caracteres
      - 6 o 7 letras   -> los primeros 5 caracteres
      - menos de 6     -> la palabra completa (cortarla produciría ruido)
    Con 7 caracteres «integración» ya no coincide con «integridad» (antes, con 6, sí).
    """
    n = len(palabra)
    if n >= 8:
        return palabra[:7]
    if n >= 6:
        return palabra[:5]
    return palabra


# Palabras de un enunciado que no dicen qué es el proyecto: los verbos de trámite y la propia
# pregunta («¿a qué línea estratégica me remito?»). Sólo se descartan al armar términos a partir
# del texto de la persona sin modelo (terminos_del_texto).
GENERICAS = set("""construir construccion construcciones hacer hago ubicar ubico ubica ubicarse linea lineas
estrategica estrategicas estrategia estrategias proyecto proyectos programa programas iniciativa
iniciativas mejoramiento ampliacion rehabilitacion adecuacion mantenimiento optimizacion estudios
disenos interventoria municipio municipios departamento fase etapa obras obra""".split())


def frases_del_diccionario(texto: str) -> list:
    """Palabras del diccionario de sinónimos formadas por 2 o más palabras («placa huella»)
    que aparecen completas en el texto. Una frase así se pierde si se parte en palabras
    sueltas; las de una sola palabra se dejan al criterio del modelo (p. ej. «casa» en
    «casa de gobierno» no es vivienda)."""
    t = " " + normalizar(texto) + " "
    return [k for k in cargar_sinonimos() if " " in k and f" {k} " in t]


def terminos_del_texto(texto: str) -> list:
    """Términos de búsqueda a partir del texto de la persona, sin modelo: las frases del
    diccionario que aparezcan y sus palabras útiles (sin verbos de trámite ni la pregunta)."""
    frases = frases_del_diccionario(texto)
    usadas = {w for f in frases for w in f.split()}
    return frases + [w for w in palabras_utiles(texto) if w not in GENERICAS and w not in usadas]


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

HOJA_EJES, HOJA_TEMAS, HOJA_ESTRATEGIAS = "VF_Ejes", "VF_Temas", "VF_Estructura"
COL_EJES = ["Número del eje", "Nombre del eje", "Descripción del eje"]
COL_TEMAS = ["Número del tema", "Número del eje", "Nombre del tema",
             "Descripción del tema", "Palabras clave del tema"]
COL_ESTRATEGIAS = ["Número de la estrategia", "Número del tema", "Nombre de la estrategia",
                   "Palabras clave (4 a 10)"]

_TABLAS = None


def _lista(texto) -> list:
    return [p.strip() for p in str(texto).split(";") if p.strip()]


def _clave_codigo(codigo: str) -> tuple:
    return tuple(int(p) if p.isdigit() else 0 for p in str(codigo).split("."))


def _hoja(nombre: str, obligatorias: list) -> pd.DataFrame:
    try:
        t = pd.read_excel(ARCHIVO_ESTRUCTURA, sheet_name=nombre, dtype=str)
    except ValueError:
        raise ValueError(
            f"El archivo de estructura no tiene la hoja «{nombre}». Debe ser la versión "
            f"final, con las hojas {HOJA_EJES}, {HOJA_TEMAS} y {HOJA_ESTRATEGIAS}.")
    t.columns = [str(c).strip() for c in t.columns]
    faltan = [c for c in obligatorias if c not in t.columns]
    if faltan:
        raise ValueError(f"La hoja «{nombre}» no tiene las columnas: {', '.join(faltan)}.")
    t = t.fillna("").apply(lambda col: col.astype(str).str.strip())
    return t[t[obligatorias[0]] != ""].reset_index(drop=True)


def _validar_estructura(ejes, temas, est) -> None:
    """Integridad de eje -> tema -> estrategia. Junta todos los problemas en un solo
    mensaje, para corregir el Excel de una vez."""
    p = []
    for nombre, tabla, col in ((HOJA_EJES, ejes, "Número del eje"),
                               (HOJA_TEMAS, temas, "Número del tema"),
                               (HOJA_ESTRATEGIAS, est, "Número de la estrategia")):
        rep = sorted(tabla[col][tabla[col].duplicated()].unique())
        if rep:
            p.append(f"{nombre}: códigos repetidos {rep}")
    nombres_eje = dict(zip(ejes["Número del eje"], ejes["Nombre del eje"]))
    nombres_tema = dict(zip(temas["Número del tema"], temas["Nombre del tema"]))

    for _, r in temas.iterrows():
        t, e = r["Número del tema"], r["Número del eje"]
        if e not in nombres_eje:
            p.append(f"Tema {t}: el eje «{e}» no existe en {HOJA_EJES}")
        elif not t.startswith(e + "."):
            p.append(f"Tema {t}: su código no empieza por el del eje {e}")
        if not r["Descripción del tema"]:
            p.append(f"Tema {t}: falta la descripción")
    for _, r in ejes.iterrows():
        if not r["Descripción del eje"]:
            p.append(f"Eje {r['Número del eje']}: falta la descripción")

    cuenta = est["Número del tema"].value_counts()
    for _, e in est.iterrows():
        c, t = e["Número de la estrategia"], e["Número del tema"]
        if t not in nombres_tema:
            p.append(f"Estrategia {c}: el tema «{t}» no existe en {HOJA_TEMAS}")
            continue
        if not c.startswith(t + "."):
            p.append(f"Estrategia {c}: su código no empieza por el del tema {t}")
        kw = _lista(e["Palabras clave (4 a 10)"])
        if not 1 <= len(kw) <= 10:
            p.append(f"Estrategia {c}: tiene {len(kw)} palabras clave (deben ser de 1 a 10)")
        if len({normalizar(k) for k in kw}) < len(kw):
            p.append(f"Estrategia {c}: palabras clave repetidas")
    for col_n, col_nombre, nombres in (("Número del eje", "Nombre del eje", nombres_eje),
                                       ("Número del tema", "Nombre del tema", nombres_tema)):
        if col_n in est.columns and col_nombre in est.columns:
            mal = est[[col_n, col_nombre]].drop_duplicates()
            for n_, nom in zip(mal[col_n], mal[col_nombre]):
                if nombres.get(n_) not in (None, nom):
                    p.append(f"{HOJA_ESTRATEGIAS}: el nombre de «{n_}» difiere del de la otra hoja")
    if "Número de estrategias" in temas.columns:
        for t, n_ in zip(temas["Número del tema"], temas["Número de estrategias"]):
            if n_.isdigit() and int(n_) != int(cuenta.get(t, 0)):
                p.append(f"Tema {t}: dice {n_} estrategias y hay {int(cuenta.get(t, 0))}")
    if p:
        raise ValueError(f"La estructura tiene {len(p)} problema(s):\n- " + "\n- ".join(p[:15])
                         + ("\n- …" if len(p) > 15 else ""))


def cargar_estructura() -> pd.DataFrame:
    """Lee el libro de estructura (hojas VF_Ejes, VF_Temas y VF_Estructura) y devuelve
    una fila por estrategia, con su eje y su tema ya unidos, lista para buscar y para el
    árbol. La estrategia sólo tiene palabras clave: no tiene descripción. Las tres
    tablas originales (para el tablero y los indicadores) salen de cargar_tablas().

    Si el archivo se reemplaza por una versión nueva, basta reiniciar la aplicación: no
    hay nada codificado a mano, y si algo no cuadra se avisa al arrancar."""
    global _EST, _TABLAS
    if _EST is not None:
        return _EST

    ejes = _hoja(HOJA_EJES, COL_EJES)
    temas = _hoja(HOJA_TEMAS, COL_TEMAS)
    est = _hoja(HOJA_ESTRATEGIAS, COL_ESTRATEGIAS)
    _validar_estructura(ejes, temas, est)

    e_nom = dict(zip(ejes["Número del eje"], ejes["Nombre del eje"]))
    e_des = dict(zip(ejes["Número del eje"], ejes["Descripción del eje"]))
    t_fila = {r["Número del tema"]: r for _, r in temas.iterrows()}
    ant = est["Código anterior"] if "Código anterior" in est.columns else [""] * len(est)

    filas = []
    for (_, r), anterior in zip(est.iterrows(), ant):
        t = t_fila[r["Número del tema"]]
        e = t["Número del eje"]
        filas.append({
            "eje_n": int(e), "eje": e_nom[e], "eje_desc": e_des[e],
            "tema_n": t["Número del tema"], "tema": t["Nombre del tema"],
            "tema_desc": t["Descripción del tema"], "tema_kw_lista": _lista(t["Palabras clave del tema"]),
            "est_n": r["Número de la estrategia"], "est": r["Nombre de la estrategia"],
            "kw": r["Palabras clave (4 a 10)"], "kw_lista": _lista(r["Palabras clave (4 a 10)"]),
            "codigo_anterior": anterior,
        })
    df = pd.DataFrame(filas)
    df["eje_n"] = df["eje_n"].astype("Int64")
    df = df.sort_values("est_n", key=lambda s: s.map(_clave_codigo)).reset_index(drop=True)

    # Texto normalizado por campo, calculado una sola vez.
    df["_kw"] = df["kw"].map(normalizar)
    df["_est"] = df["est"].map(normalizar)
    df["_tema"] = df["tema"].map(normalizar)
    df["_tema_desc"] = df["tema_desc"].map(normalizar)

    # Conjunto de raíces por campo, para la capa 2.
    for destino, origen in [("_r_kw", "_kw"), ("_r_est", "_est"), ("_r_tema", "_tema"),
                            ("_r_tema_desc", "_tema_desc")]:
        df[destino] = df[origen].apply(lambda t: {raiz(w) for w in t.split() if len(w) >= 4})

    _TABLAS = {
        "ejes": pd.DataFrame({"eje_id": ejes["Número del eje"], "nombre": ejes["Nombre del eje"],
                              "descripcion": ejes["Descripción del eje"],
                              "temas_clave": ejes["Temas clave"] if "Temas clave" in ejes.columns else ""}),
        "temas": pd.DataFrame({"tema_id": temas["Número del tema"], "eje_id": temas["Número del eje"],
                               "nombre": temas["Nombre del tema"], "descripcion": temas["Descripción del tema"],
                               "palabras_clave": temas["Palabras clave del tema"].map(_lista)}),
        "estrategias": pd.DataFrame({"estrategia_id": df["est_n"], "tema_id": df["tema_n"],
                                     "eje_id": df["eje_n"].astype(str), "nombre": df["est"],
                                     "palabras_clave": df["kw_lista"],
                                     "codigo_anterior": df["codigo_anterior"]}),
    }
    _EST = df
    return _EST


def cargar_tablas() -> dict:
    """Las tres tablas normalizadas (ejes, temas, estrategias), con llaves por código,
    para el tablero y los indicadores. Los indicadores se enlazan por estrategia_id."""
    cargar_estructura()
    return _TABLAS


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
    ("nombre de la línea estratégica", "_est", "_r_est"),
    ("tema", "_tema", "_r_tema"),
]


# Descripción del tema: categoría aparte («En la descripción»), sin puntaje. La del eje no
# cuenta: marcaría todas las estrategias del eje (sólo se muestra, tras el botón «i»).
_CAMPOS_DESC = [
    ("descripción del tema", "_tema_desc", "_r_tema_desc"),
]


def _coincide_campos(termino: str, fila, usar_raiz: bool, campos=_CAMPOS) -> list:
    """Todos los campos donde aparece el término: [(campo, tipo)], del más pesado al menos.
    Un campo cuenta si contiene el término tal cual (literal; una frase, completa) o, si no,
    si están todas sus palabras por la raíz."""
    palabras = [w for w in termino.split() if len(w) >= 3]
    if not palabras:
        return []
    objetivo = {raiz(w) for w in palabras if len(w) >= 4} if usar_raiz else set()
    salida = []
    for nombre, campo, campo_raices in campos:
        if termino in fila[campo]:
            salida.append((nombre, "literal"))
        elif objetivo and objetivo <= fila[campo_raices]:
            salida.append((nombre, "raíz"))
    return salida


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
_REGLAS = None


def cargar_reglas() -> list:
    """data/reglas.csv: grupos de estrategias que sólo se sugieren si la pregunta
    menciona alguna palabra disparadora; si no, no se muestran.

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
                f"data/reglas.csv: no encontré líneas estratégicas para «{r['aplica_a']}». "
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


def _sugerencias(estrategias, buscados) -> list:
    """Palabras clave del PND (tal cual) que concretan un término amplio: las que lo
    contienen y dicen algo más («Infraestructura hospitalaria» para «infraestructura»),
    de la más frecuente a la menos. Si hay pocas, se completa con los temas."""
    cuenta, original = Counter(), {}
    for r in estrategias:
        for k in r["palabras_clave"]:
            kn = normalizar(k)
            if any(t in kn and t != kn for t in buscados):
                cuenta[kn] += 1
                original.setdefault(kn, k)
    salida = [original[k] for k in sorted(cuenta, key=lambda k: (-cuenta[k], k))][:MAX_SUGERENCIAS]
    if len(salida) < 3:
        for r in estrategias:
            tema = r["tema"].split(" ", 1)[-1]
            if tema not in salida and len(salida) < MAX_SUGERENCIAS:
                salida.append(tema)
    return salida


def _ev(e, h):
    return {"termino": e["termino"], "origen": e["origen"], "campo": h[0], "tipo": h[1]}


def buscar_estrategias(terminos, usar_raiz: bool = True) -> dict:
    """Busca estrategias del PND que contengan los términos dados.

    No interpreta la intención ni redacta nada. Devuelve:
      resultados    las «más cercanas» (hasta MAX_CERCANAS), con evidencia, junto con
                    n_cercanas (cuántas llegan al umbral), muy_amplia y sugerencias.
      niveles       códigos por categoría (cercanas, relacionadas, descripcion): sólo árbol.
      coincidencias qué término coincidió en qué campo, por código: sólo árbol.
      avisos_reglas notas de las reglas que actuaron: sólo interfaz.
    """
    df = cargar_estructura()
    expandidos = expandir(terminos)
    if not expandidos:
        return {"terminos_buscados": [], "n_resultados": 0, "resultados": [],
                "mensaje": "No se recibió ningún término de búsqueda."}

    # 1) Evidencia en palabras clave, nombre y tema: un término puede coincidir en varios
    #    campos de la misma línea (p. ej. «salud» en una palabra clave y en el nombre).
    filas = {}                                   # índice de la fila -> (fila, evidencia)
    for idx, fila in df.iterrows():
        for e in expandidos:
            for h in _coincide_campos(e["termino"], fila, usar_raiz):
                filas.setdefault(idx, (fila, []))[1].append(_ev(e, h))

    # 2) Especificidad: un término que aparece en muchas estrategias dice poco.
    #    vale ln(total / estrategias donde aparece), contando como mínimo
    #    MIN_ESTRATEGIAS_ESPECIFICIDAD: 3 de 122 -> 3.7; 26 de 122 -> 1.5.
    n_total = len(df)
    n_por_termino = Counter(t for _, evs in filas.values() for t in {ev["termino"] for ev in evs})
    especificidad = {t: math.log(n_total / max(n, MIN_ESTRATEGIAS_ESPECIFICIDAD))
                     for t, n in n_por_termino.items()}

    # 3) Score = suma, por cada término que coincide, de
    #    (peso del campo + la mitad del peso de cada otro campo donde también coincide)
    #    x multiplicador del origen x especificidad.
    resultados = []
    for fila, evidencia in filas.values():
        por_termino = {}
        for ev in evidencia:
            por_termino.setdefault(ev["termino"], []).append(ev)
        score = 0.0
        for t, evs in por_termino.items():
            pesos = sorted((PESO_CAMPO[ev["campo"]] for ev in evs), reverse=True)
            peso = pesos[0] + OTROS_CAMPOS * sum(pesos[1:])
            score += peso * (2 if evs[0]["origen"] == "escrito" else 1) * especificidad[t]
        resultados.append({
            "codigo": fila["est_n"],
            "estrategia": fila["est"],
            "eje": f"{fila['eje_n']}. {fila['eje']}",
            "tema": f"{fila['tema_n']} {fila['tema']}".strip(),
            "palabras_clave": fila["kw_lista"],
            "n_terminos_coincidentes": len({ev["termino"] for ev in evidencia}),
            "score": round(score, 3),
            "coincidencias": evidencia,
        })
    # Desempate: más términos distintos coincidentes y, al final, el código (orden estable).
    resultados.sort(key=lambda r: (-r["score"], -r["n_terminos_coincidentes"], r["codigo"]))

    # 4) Reglas: lo restringido (p. ej. eje 7 sin hablar de desastres) no se muestra.
    #    Si TODO lo que coincidió es restringido, se muestra igual: no hay otra cosa.
    restringidas, avisos = _restringidas(df, expandidos)
    if resultados and all(r["codigo"] in restringidas for r in resultados):
        restringidas, avisos = set(), []
    mejor = max((r["score"] for r in resultados if r["codigo"] not in restringidas), default=0)

    # 5) Niveles, como fracción del mejor score. Lo que queda por debajo no se muestra.
    for r in resultados:
        frac = r["score"] / mejor if mejor else 1.0
        r["pct_del_mejor"] = round(100 * frac)
        if r["codigo"] in restringidas:
            r["nivel"] = "omitida"
        else:
            r["nivel"] = ("cercanas" if frac >= UMBRAL_CERCANAS
                          else "relacionadas" if frac >= UMBRAL_RELACIONADAS else "omitida")
    cercanas_todas = [r for r in resultados if r["nivel"] == "cercanas"]
    cercanas = cercanas_todas[:MAX_CERCANAS]
    sobran = cercanas_todas[MAX_CERCANAS:]    # muy cercanas, pero fuera del tope: van al árbol
    for r in sobran:
        r["nivel"] = "relacionadas"
    cod_sobran = {r["codigo"] for r in sobran}
    candidatas = [r for r in resultados
                  if r["nivel"] == "relacionadas" and r["codigo"] not in cod_sobran]
    relacionadas = sobran + _cortar_sin_partir_empates(candidatas, MAX_RELACIONADAS)
    en_rel = {r["codigo"] for r in relacionadas}
    for r in candidatas:
        if r["codigo"] not in en_rel:
            r["nivel"] = "omitida"
    en_chat = cercanas

    # 6) En la descripción: estrategias sin coincidencia propia cuyo tema menciona
    #    el término en su descripción. No tiene puntaje. Busca sólo con los términos que
    #    llegan de la persona o del modelo: los sinónimos del diccionario (p. ej. el genérico
    #    «infraestructura» de «polideportivo») la inundarían.
    marcadas = {r["codigo"] for r in cercanas + relacionadas}
    escritos = [e for e in expandidos if e["origen"] == "escrito"]
    descripcion = []                      # [(código, evidencia)]
    for _, fila in df.iterrows():
        if fila["est_n"] in marcadas or fila["est_n"] in restringidas:
            continue
        evs = [_ev(e, h) for e in escritos
               if (h := _coincide(e["termino"], fila, usar_raiz, campos=_CAMPOS_DESC))]
        if evs:
            descripcion.append((fila["est_n"], evs))

    # Qué palabra disparó qué sinónimos, para mostrarlo tal cual en la interfaz.
    aplicados = {}
    for e in expandidos:
        if e["origen"].startswith("diccionario: "):
            aplicados.setdefault(e["origen"][len("diccionario: "):], []).append(e["termino"])

    # Consulta muy amplia (p. ej. una sola palabra como «infraestructura»): se avisa y se
    # ofrecen, tal cual están en el PND, las palabras clave que la concretan.
    n_marcadas = len(cercanas) + len(relacionadas) + len(descripcion)
    # La consulta no distingue —hay que concretarla— si 3 o más líneas llegan al umbral y son de
    # temas distintos (p. ej. «infraestructura»: defensa, salud, cultura). Si son del mismo tema
    # (p. ej. un acueducto: 4.5.4, 4.5.6, 4.5.7), se muestran sin preguntar.
    temas_cercanas = {r["codigo"].rsplit(".", 1)[0] for r in cercanas_todas}
    muy_amplia = len(cercanas_todas) >= MAX_CERCANAS and len(temas_cercanas) >= 2
    sugerencias = []
    if muy_amplia:
        coincidieron = sorted({ev["termino"] for r in cercanas + relacionadas
                               for ev in r["coincidencias"] if ev["campo"] == "palabras clave"})
        sugerencias = _sugerencias(cercanas + relacionadas, coincidieron)

    # Aviso sólo si la regla movió algo: una restringida que, sin la regla, habría
    # llegado a Más cercanas o Relacionadas.
    movidas = {r["codigo"] for r in resultados
               if r["codigo"] in restringidas and mejor and r["score"] >= UMBRAL_RELACIONADAS * mejor}

    coincidencias = {r["codigo"]: [{"termino": ev["termino"], "campo": ev["campo"]}
                                   for ev in r["coincidencias"]] for r in cercanas + relacionadas}
    for cod, evs in descripcion:
        coincidencias[cod] = [{"termino": ev["termino"], "campo": ev["campo"]} for ev in evs]
    por_codigo = {fila["est_n"]: fila for _, fila in df.iterrows()}

    salida = {
        "terminos_buscados": [e["termino"] for e in expandidos],
        "terminos_del_diccionario": [e["termino"] for e in expandidos if e["origen"] != "escrito"],
        "sinonimos_aplicados": [{"palabra": k, "terminos": v} for k, v in aplicados.items()],
        "n_resultados": n_marcadas,
        "n_cercanas": len(cercanas_todas),
        "n_en_descripcion": len(descripcion),
        "n_omitidas": sum(1 for r in resultados if r["nivel"] == "omitida"
                          and r["codigo"] not in restringidas),
        "muy_amplia": muy_amplia,
        "sugerencias": sugerencias,
        "resultados": en_chat,
        "niveles": {"cercanas": [r["codigo"] for r in cercanas],
                    "relacionadas": [r["codigo"] for r in relacionadas],
                    "descripcion": [c for c, _ in descripcion]},
        "coincidencias": coincidencias,
        "avisos_reglas": [nota for cods, nota in avisos if cods & movidas and nota],
        "mensaje": "",
    }
    if not n_marcadas:
        salida["mensaje"] = "Ninguna línea estratégica contiene esos términos."
    elif not cercanas:
        salida["mensaje"] = ("Ninguna línea estratégica coincide en sus palabras clave, su nombre ni su "
                             "tema; estas mencionan el término en la descripción de su tema.")
        salida["en_descripcion"] = [
            {"codigo": c, "estrategia": por_codigo[c]["est"],
             "tema": f"{por_codigo[c]['tema_n']} {por_codigo[c]['tema']}",
             "palabras_clave": por_codigo[c]["kw_lista"]}
            for c, _ in descripcion[:MAX_CERCANAS]]
    return salida


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
        "palabras_clave": r["kw_lista"],
        "descripcion_del_tema": r["tema_desc"],
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
