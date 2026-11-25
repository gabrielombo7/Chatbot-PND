"""
proyectos.py — Proyectos y megaproyectos regionales (Anexo 4 de las Bases del PND 2026-2030).
==============================================================================================
Consulta directa sobre data/Proyectos_Megaproyectos_Regionales.xlsx, el anexo digitalizado con
herramientas/digitalizar_anexo4.py. No usa el modelo de lenguaje ni la búsqueda por palabras:
sólo filtra por departamento (o región) y por sector.

El libro trae las columnas del PDF tal cual y dos columnas para filtrar, ya normalizadas:
«Departamento o región (filtro)» y «Sector (filtro)», con varios valores separados por «; ».
Un proyecto de varios departamentos o sectores sale en cada uno.
"""

import unicodedata
from pathlib import Path

import pandas as pd

ARCHIVO = Path(__file__).parent / "data" / "Proyectos_Megaproyectos_Regionales.xlsx"
HOJA = "Proyectos"

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
