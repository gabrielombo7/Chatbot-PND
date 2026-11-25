"""
proyectos.py — Proyectos y megaproyectos regionales (Anexo 4 de las Bases del PND 2026-2030).
==============================================================================================
Consulta directa sobre data/Proyectos_Megaproyectos_Regionales.xlsx, el anexo digitalizado con
herramientas/digitalizar_anexo4.py. No usa el modelo de lenguaje ni la búsqueda por palabras:
sólo filtra por departamento (o región) y por sector.

El libro trae las columnas del PDF tal cual y dos columnas para filtrar, ya normalizadas:
«Departamento o región (filtro)» y «Sector (filtro)», con varios valores separados por «; ».
Un proyecto de varios departamentos o sectores sale en cada uno.

Algunos proyectos tienen además una clasificación de prueba en las líneas estratégicas del Plan,
hecha de dos maneras (el score del orientador y Claude), en data/Clasificacion_proyectos.xlsx
(herramientas/clasificar_proyectos.py). `clasificacion()` la devuelve por número de proyecto.
"""

import unicodedata
from pathlib import Path

import pandas as pd

ARCHIVO = Path(__file__).parent / "data" / "Proyectos_Megaproyectos_Regionales.xlsx"
HOJA = "Proyectos"
ARCHIVO_CLASIFICACION = Path(__file__).parent / "data" / "Clasificacion_proyectos.xlsx"
HOJA_CLASIFICACION = "Clasificación"
COL_N = "N.°"

COL_NOMBRE = "Nombre del proyecto"
COL_MUNICIPIO = "Municipio"
COL_DEPARTAMENTO = "Departamento o encuentro regional (PDF)"
COL_SECTOR = "Sector (PDF)"
COL_TERRITORIO = "Departamento o región (filtro)"
COL_SECTOR_FILTRO = "Sector (filtro)"
COL_REPETIDO = "Repetido en el PDF"
NECESARIAS = [COL_NOMBRE, COL_MUNICIPIO, COL_DEPARTAMENTO, COL_SECTOR, COL_TERRITORIO,
              COL_SECTOR_FILTRO, COL_REPETIDO]

SIN_DEPARTAMENTO = "Sin departamento específico"
SUFIJO_REGION = "(encuentro regional)"

_DF = None
_CLASIF = None


def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn").lower()


def _lista(texto: str) -> list:
    return [t.strip() for t in str(texto).split(";") if t.strip()]


def cargar() -> pd.DataFrame:
    """Los proyectos del anexo, sin las filas que el PDF repite tal cual, con las listas de
    departamentos y sectores listas para filtrar (columnas «_territorios» y «_sectores»)."""
    global _DF
    if _DF is not None:
        return _DF
    df = pd.read_excel(ARCHIVO, sheet_name=HOJA, dtype=str).fillna("")
    faltan = [c for c in NECESARIAS if c not in df.columns]
    if faltan:
        raise ValueError(f"{ARCHIVO.name}, hoja «{HOJA}»: faltan las columnas {faltan}")
    df = df[df[COL_REPETIDO].str.strip() != "Sí"].reset_index(drop=True)
    df["_territorios"] = df[COL_TERRITORIO].map(_lista)
    df["_sectores"] = df[COL_SECTOR_FILTRO].map(_lista)
    _DF = df
    return _DF


def _orden_territorio(t: str):
    # Departamentos, luego encuentros regionales y, al final, lo que no tiene departamento.
    grupo = 2 if t == SIN_DEPARTAMENTO else 1 if t.endswith(SUFIJO_REGION) else 0
    return grupo, _sin_tildes(t)


def opciones() -> tuple:
    """(territorios, sectores): [(valor, cantidad de proyectos)], para los selectores."""
    df = cargar()
    terr, sect = {}, {}
    for lista in df["_territorios"]:
        for t in lista:
            terr[t] = terr.get(t, 0) + 1
    for lista in df["_sectores"]:
        for s in lista:
            sect[s] = sect.get(s, 0) + 1
    return (sorted(terr.items(), key=lambda kv: _orden_territorio(kv[0])),
            sorted(sect.items(), key=lambda kv: _sin_tildes(kv[0])))


def filtrar(territorio=None, sector=None) -> pd.DataFrame:
    """Proyectos de un departamento (o región) y de un sector; None = todos."""
    df = cargar()
    if territorio:
        df = df[df["_territorios"].map(lambda l: territorio in l)]
    if sector:
        df = df[df["_sectores"].map(lambda l: sector in l)]
    return df


def resumen() -> dict:
    df = cargar()
    return {"n": int(len(df))}


def resumen_filtro(df: pd.DataFrame, maximo: int = 5) -> dict:
    """Qué hay en un conjunto de proyectos: sectores (ya unificados) y municipios más frecuentes."""
    sect, mun = {}, {}
    for lista in df["_sectores"]:
        for s in lista:
            sect[s] = sect.get(s, 0) + 1
    for m in df[COL_MUNICIPIO]:
        if m.strip():
            mun[m] = mun.get(m, 0) + 1
    orden = lambda d: sorted(d.items(), key=lambda kv: (-kv[1], _sin_tildes(kv[0])))[:maximo]
    return {"sectores": orden(sect), "municipios": orden(mun)}


def _codigos(texto: str) -> list:
    return [c.strip() for c in str(texto).split(";") if c.strip()]


def clasificacion() -> dict:
    """Clasificación de prueba de algunos proyectos, por «N.°» (texto): el score y Claude.
    Devuelve {} si el archivo no existe: la página funciona igual sin ella."""
    global _CLASIF
    if _CLASIF is not None:
        return _CLASIF
    _CLASIF = {}
    if ARCHIVO_CLASIFICACION.exists():
        df = pd.read_excel(ARCHIVO_CLASIFICACION, sheet_name=HOJA_CLASIFICACION, dtype=str).fillna("")
        for _, r in df.iterrows():
            _CLASIF[r[COL_N].strip()] = {
                "score": [c for c in [r["Score: línea más cercana"].strip()] + _codigos(r["Score: otras más cercanas"]) if c],
                "claude": r["Claude: línea principal"].strip(),
                "alternativas": _codigos(r["Claude: alternativas"]),
                "criterio": r["Claude: criterio"].strip(),
                "coinciden": r["¿Coinciden?"].strip(),
            }
    return _CLASIF
