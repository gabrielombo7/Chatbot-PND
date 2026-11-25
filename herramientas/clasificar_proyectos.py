"""
clasificar_proyectos.py — Compara dos maneras de ubicar proyectos en las líneas estratégicas del Plan.
=====================================================================================================
Toma proyectos del Anexo 4 (data/Proyectos_Megaproyectos_Regionales.xlsx) y los ubica de dos maneras:

  * **Score:** el motor del orientador (buscador.py) usando sólo las palabras del nombre del proyecto
    (`terminos_del_texto`), sin el modelo de lenguaje. Es el piso: en la aplicación, el modelo elige
    mejores términos, pero aquí no hay llave del API.
  * **Claude:** una clasificación hecha leyendo el catálogo del Plan (código, nombre, palabras clave y
    descripción del tema). Es un criterio, no una verdad: puede corregirse editando el libro que genera
    este script (data/Clasificacion_proyectos.xlsx), que es el que lee la página.

Escribe data/Clasificacion_proyectos.xlsx con las dos ubicaciones, el criterio y si coinciden.

Uso (desde la raíz del repo):
    python herramientas/clasificar_proyectos.py
"""

import datetime
import os
import sys

import openpyxl
import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
import buscador as B  # noqa: E402

ENTRADA = os.path.join(RAIZ, "data", "Proyectos_Megaproyectos_Regionales.xlsx")
SALIDA = os.path.join(RAIZ, "data", "Clasificacion_proyectos.xlsx")

# Clasificación de Claude: N.° del proyecto -> (línea principal, alternativas razonables, criterio).
# Amazonas (N.° 1 a 11) y las iniciativas del encuentro regional «Amazonia» (N.° 2659 en adelante).
CLASIFICACION_CLAUDE = {
    '1': ('4.6.3', ['5.1.8'], 'Economía propia de comunidades indígenas (infraestructura productiva y comercial)'),
    '2': ('4.5.4', ['4.6.4'], 'Acueducto: agua potable'),
    '3': ('4.5.4', ['4.5.5'], 'Plan maestro de acueducto y alcantarillado'),
    '4': ('4.5.4', ['4.5.5', '4.6.4'], 'Plan maestro de acueducto y alcantarillado en comunidades'),
    '5': ('2.1.1', ['4.6.1'], 'Infraestructura educativa (entornos para aprender), incluye territorios indígenas'),
    '6': ('4.3.1', ['4.2.1'], 'Ambiguo: centro de integración y desarrollo social (familia, niñez)'),
    '7': ('3.1.3', [], 'NUSE 123 y cámaras: seguridad y convivencia'),
    '8': ('4.5.3', ['4.5.1', '5.1.7'], 'Vía urbana: movilidad'),
    '9': ('4.5.1', ['4.5.3', '4.5.4'], 'Intervención urbana integral (vial, urbanística y redes)'),
    '10': ('2.1.1', [], 'Infraestructura educativa'),
    '11': ('4.5.3', ['4.5.1'], 'Vía urbana: movilidad'),
    '2659': ('5.1.7', [], 'Vía rural: conectividad terrestre'),
    '2660': ('5.1.3', ['5.2.6'], 'Aeropuerto regional: infraestructura estratégica de transporte'),
    '2661': ('5.1.3', ['5.2.6'], 'Aeropuerto regional: infraestructura estratégica de transporte'),
    '2662': ('5.3.1', ['5.1.3'], 'Centro logístico fluvial y aéreo'),
    '2663': ('5.1.3', ['5.3.1', '5.1.7'], 'Navegabilidad de ríos: infraestructura de transporte'),
    '2664': ('5.1.7', [], 'Pavimentación de un corredor vial'),
    '2665': ('4.5.4', [], 'Plan maestro de acueducto'),
    '2666': ('5.1.9', ['4.6.3'], 'Turismo de naturaleza con comunidades'),
    '2667': ('4.5.2', [], 'Vivienda digna'),
    '2668': ('5.2.5', [], 'Conectividad digital'),
    '2669': ('5.2.6', ['5.1.3'], 'Transporte aéreo regional (hidroaviones)'),
    '2670': ('5.1.3', ['5.2.6'], 'Aeropuerto regional: infraestructura estratégica de transporte'),
    '2671': ('4.5.4', ['4.5.5'], 'Acueducto y alcantarillado'),
    '2672': ('5.1.3', ['5.3.1'], 'Muelle fluvial: infraestructura de transporte'),
    '2717': ('4.5.4', ['4.6.4'], 'Acueducto para comunidades indígenas rurales'),
    '2718': ('7.4.1', ['5.4.2'], 'Infraestructura contra sequía e inundaciones: adaptación y riesgo'),
    '2719': ('4.5.2', ['4.5.1'], 'Vivienda con servicios y vías en barrios en riesgo'),
    '2720': ('7.4.1', ['4.1.1'], 'Infraestructura básica y gestión del riesgo (mixto con salud)'),
    '2721': ('5.1.3', ['3.5.1'], 'Proyecto binacional de navegabilidad y dragado'),
    '2722': ('4.4.5', [], 'Formación de artistas'),
    '2723': ('5.1.3', ['5.3.1'], 'Muelles y navegabilidad de ríos'),
    '2724': ('5.1.3', ['5.1.7'], 'Puerto civil (y vías terciarias)'),
    '2725': ('2.1.4', [], 'Modernización de la gestión educativa'),
    '2726': ('2.3.1', ['5.2.1'], 'Capacidades de ciencia, tecnología e innovación con enfoque territorial'),
    '2727': ('4.6.4', ['4.5.4'], 'Agua potable y energía para pueblos étnicos'),
    '2728': ('4.6.7', ['4.6.2'], 'Planes de vida de pueblos indígenas'),
    '2729': ('4.6.1', ['4.1.1'], 'Salud con saberes ancestrales (intercultural)'),
    '2730': ('4.6.4', ['4.5.4'], 'Agua y saneamiento con enfoque diferencial y cultural'),
    '2865': ('5.2.7', ['5.4.2'], 'Energía solar: transición energética'),
    '2866': ('5.4.3', [], 'Bioeconomía regenerativa'),
    '2867': ('5.2.2', ['5.4.3', '2.3.1'], 'Investigación con biodiversidad'),
    '2868': ('5.1.8', ['5.2.3'], 'Capacidades productivas y comerciales de productores'),
    '2869': ('1.4.1', ['5.1.1'], 'Régimen especial para la Amazonía (zonas económicas especiales)'),
    '2870': ('5.4.5', ['2.3.1'], 'Agenda ABC (así se llama en el Plan)'),
    '2871': ('3.1.2', ['3.1.1'], 'Presencia institucional y seguridad en fronteras'),
    '2872': ('5.2.5', ['2.1.1'], 'Conectividad 5G educativa, sanitaria y productiva'),
    '2873': ('7.4.1', [], 'Gestión del riesgo'),
    '2874': ('3.2.1', ['3.1.1'], 'Instituciones de justicia en el territorio'),
    '2875': ('3.2.4', ['5.2.8'], 'Lavado de activos y crimen organizado'),
    '2876': ('3.4.2', [], 'Unidad para las Víctimas'),
    '2877': ('4.3.3', ['4.1.1'], 'Centros de rehabilitación integral'),
    '2878': ('4.1.4', [], 'Soberanía alimentaria'),
    '2879': ('4.4.2', ['4.4.3'], 'Redes de museos: patrimonio y acceso cultural'),
    '2880': ('5.3.3', [], 'Normatividad aduanera y de transporte'),
    '2881': ('5.4.2', ['5.4.3'], 'Bonos de carbono'),
    '2882': ('6.3.3', ['3.3.2'], 'Transparencia y veeduría ciudadana'),
    '2883': ('6.3.1', ['6.1.1', '6.3.3'], 'Eficiencia estatal, trámites y control de la corrupción'),
    '2884': ('2.2.2', ['2.2.1'], 'Educación para el trabajo'),
    '2885': ('4.6.1', [], 'Cierre de brechas de pueblos étnicos'),
    '2886': ('6.1.1', ['3.3.1'], 'Servicios del Estado en territorios indígenas (Registraduría)'),
    '2887': ('4.3.2', [], 'Personas mayores'),
    '2888': ('3.1.3', ['4.1.4'], 'Centro de convivencia ciudadana (descripción poco clara)'),
}

COLUMNAS = [
    ("N.°", 7), ("Nombre del proyecto", 70), ("Departamento o encuentro regional (PDF)", 22),
    ("Sector (PDF)", 24), ("Palabras que usó el score (del nombre)", 34),
    ("Score: línea más cercana", 11), ("Score: nombre de esa línea", 38), ("Score: otras más cercanas", 14),
    ("Claude: línea principal", 11), ("Claude: nombre de esa línea", 38), ("Claude: alternativas", 14),
    ("Claude: criterio", 40), ("¿Coinciden?", 18),
]
AZUL, AZUL_CLARO = "1B3E6C", "347399"

tema = lambda c: ".".join(c.split(".")[:2])
eje = lambda c: c.split(".")[0]


def coincidencia(score_cercanas, principal, alternativas):
    """Igual / Compatible / Entre sus más cercanas / Mismo tema / Mismo eje / Distinta / Sin resultado."""
    if not score_cercanas:
        return "Sin resultado"
    primera = score_cercanas[0]
    if primera == principal:
        return "Igual"
    if primera in alternativas:
        return "Compatible"
    if any(c == principal or c in alternativas for c in score_cercanas):
        return "Entre sus más cercanas"
    if tema(primera) == tema(principal):
        return "Mismo tema"
    if eje(primera) == eje(principal):
        return "Mismo eje"
    return "Distinta"


def main():
    proy = pd.read_excel(ENTRADA, sheet_name="Proyectos", dtype=str).fillna("").set_index("N.°")
    nombres = {r["est_n"]: r["est"] for _, r in B.cargar_estructura().iterrows()}
    filas = []
    for n, (principal, alternativas, criterio) in CLASIFICACION_CLAUDE.items():
        for c in [principal, *alternativas]:
            assert c in nombres, f"código inexistente en el catálogo: {c}"
        p = proy.loc[n]
        terminos = B.terminos_del_texto(p["Nombre del proyecto"])
        res = B.buscar_estrategias(terminos)
        cercanas = [x["codigo"] for x in res["resultados"]]
        filas.append([
            n, p["Nombre del proyecto"], p["Departamento o encuentro regional (PDF)"], p["Sector (PDF)"],
            "; ".join(terminos), cercanas[0] if cercanas else "", nombres.get(cercanas[0], "") if cercanas else "",
            "; ".join(cercanas[1:]), principal, nombres[principal], "; ".join(alternativas), criterio,
            coincidencia(cercanas, principal, alternativas)])

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Clasificación"
    ws.append([c for c, _ in COLUMNAS])
    for f in filas:
        ws.append(f)
    for j, (_, ancho) in enumerate(COLUMNAS, 1):
        ws.column_dimensions[get_column_letter(j)].width = ancho
        c = ws.cell(1, j)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL_CLARO if 6 <= j <= 8 else AZUL)
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "C2"
    ws.auto_filter.ref = ws.dimensions

    cuenta = pd.Series([f[-1] for f in filas]).value_counts()
    total = len(filas)
    nt = wb.create_sheet("Notas")
    notas = [
        ("Qué es esto", "Ubicación de algunos proyectos del Anexo 4 en las líneas estratégicas del Plan, de dos maneras."),
        ("Generado", datetime.date.today().isoformat() + " con herramientas/clasificar_proyectos.py"),
        ("Score", "El motor del orientador (buscador.py) con sólo las palabras del nombre del proyecto, sin el modelo de "
                  "lenguaje. Es el piso: en la aplicación el modelo elige mejores términos."),
        ("Claude", "Clasificación hecha leyendo el catálogo del Plan. Es un criterio, no una verdad: se puede corregir "
                   "editando las columnas «Claude: …» de la hoja «Clasificación»; la página las lee tal cual. Si cambias "
                   "la línea principal, cambia también «¿Coinciden?»."),
        ("Proyectos clasificados", f"{total}"),
        ("", ""),
        ("¿Coinciden? (score frente a Claude)", ""),
        ("Igual", "La línea más cercana del score es la principal de Claude."),
        ("Compatible", "La línea más cercana del score es una de las alternativas razonables de Claude."),
        ("Entre sus más cercanas", "Claude coincide con alguna de las (hasta 3) más cercanas del score, pero no con la primera."),
        ("Mismo tema / Mismo eje", "La primera del score cae en el mismo tema (p. ej. 4.5) o eje (p. ej. 4) que la de Claude."),
        ("Distinta / Sin resultado", "Cae en otro eje, o el score no encontró nada."),
        ("", ""),
        ("Resultado", ""),
    ]
    for etiqueta in ("Igual", "Compatible", "Entre sus más cercanas", "Mismo tema", "Mismo eje", "Distinta", "Sin resultado"):
        notas.append((etiqueta, f"{int(cuenta.get(etiqueta, 0))} de {total}"))
    for fila in notas:
        nt.append(list(fila))
    nt.column_dimensions["A"].width = 38
    nt.column_dimensions["B"].width = 110
    for fila in nt.iter_rows():
        fila[0].font = Font(bold=True)
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(SALIDA)
    print(f"{total} proyectos clasificados en {SALIDA}")
    print(cuenta.to_dict())


if __name__ == "__main__":
    main()
