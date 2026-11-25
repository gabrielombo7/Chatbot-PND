"""
digitalizar_anexo4.py — Digitaliza el Anexo 4 de las Bases del PND 2026-2030 a Excel.
=====================================================================================
El anexo («Indicativo Proyectos y Megaproyectos Regionales», 225 páginas) trae dos tablas:

  1. «Megaproyectos y proyectos de alto impacto local»: Departamento, Municipio, Nombre del
     proyecto, Sector y Base de identificación.
  2. «Otras iniciativas y necesidades de encuentros regionales»: Encuentro regional, Nombre del
     proyecto, Sector y Base de identificación.

Este script lee las tablas del PDF tal cual (no corrige ortografía ni nombres) y escribe el libro
que usa la página (data/Proyectos_Megaproyectos_Regionales.xlsx). Además de lo que dice el PDF, el
libro trae dos columnas para filtrar, que son las que usa la página:

  * «Departamento o región (filtro)»: los departamentos de cada proyecto, separados por «; »
    (un proyecto de varios departamentos sale en cada uno). Los encuentros regionales que no son un
    departamento («Pacífico», «Amazonia»…) quedan con su nombre, y lo nacional o sin departamento,
    como «Sin departamento específico».
  * «Sector (filtro)»: el sector del PDF, con los nombres equivalentes unificados (p. ej.
    «Salud» y «Salud y Protección Social» -> «Salud»). La tabla completa está en la hoja «Notas».

Uso (desde la raíz del repo; sólo se necesita para volver a generar el libro):
    pip install pdfplumber openpyxl
    python herramientas/digitalizar_anexo4.py <anexo4.pdf> data/Proyectos_Megaproyectos_Regionales.xlsx
"""

import collections
import datetime
import re
import sys
import unicodedata

import openpyxl
import pdfplumber
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

SECCION_A = "Megaproyectos y proyectos de alto impacto local"
SECCION_B = "Otras iniciativas y necesidades de encuentros regionales"
SIN_DEPARTAMENTO = "Sin departamento específico"

# --------------------------------------------------------------------------------------
# Departamentos
# --------------------------------------------------------------------------------------
# (nombre, patrón sobre el texto en minúsculas y sin tildes). El orden importa: los nombres
# compuestos van primero y se borran del texto al encontrarse, para que «cauca» no se encuentre
# dentro de «valle del cauca» ni «santander» dentro de «norte de santander».
DEPARTAMENTOS = [
    ("Valle del Cauca", r"valle del cauca"),
    ("Norte de Santander", r"norte de santander"),
    ("San Andrés, Providencia y Santa Catalina", r"san andres"),
    ("Bogotá D.C.", r"bogota"),
    ("La Guajira", r"la guajira"),
    ("Amazonas", r"amazonas"),
    ("Antioquia", r"antioquia"),
    ("Arauca", r"arauca"),
    ("Atlántico", r"atlantico"),
    ("Bolívar", r"bolivar"),
    ("Boyacá", r"boyaca"),
    ("Caldas", r"caldas"),
    ("Caquetá", r"caqueta"),
    ("Casanare", r"casanare"),
    ("Cauca", r"cauca"),
    ("Cesar", r"cesar"),
    ("Chocó", r"choco"),
    ("Córdoba", r"cordoba"),
    ("Cundinamarca", r"cundinamarca"),
    ("Guainía", r"guainia"),
    ("Guaviare", r"guaviare"),
    ("Huila", r"huila"),
    ("Magdalena", r"magdalena"),
    ("Meta", r"meta"),
    ("Nariño", r"narino"),
    ("Putumayo", r"putumayo"),
    ("Quindío", r"quindio"),
    ("Risaralda", r"risaralda"),
    ("Santander", r"santander"),
    ("Sucre", r"sucre"),
    ("Tolima", r"tolima"),
    ("Vaupés", r"vaupes"),
    ("Vichada", r"vichada"),
]
# Encuentros regionales (tabla 2) que equivalen a uno o varios departamentos; el resto son
# regiones y conservan su nombre. «Insular» es el archipiélago de San Andrés.
ENCUENTRO_A_DEPARTAMENTOS = {
    "Santanderes": ["Santander", "Norte de Santander"],
    "Insular": ["San Andrés, Providencia y Santa Catalina"],
}


def sin_tildes(t: str) -> str:
    t = unicodedata.normalize("NFD", t)
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def departamentos_de(texto: str) -> list:
    """Departamentos que menciona un texto como «Valle del Cauca, Risaralda y Caldas», en el
    orden en que aparecen."""
    resto = " " + sin_tildes(texto) + " "
    hallados = []
    for nombre, patron in DEPARTAMENTOS:
        m = re.search(r"(?<![a-z])" + patron + r"(?![a-z])", resto)
        if m:
            hallados.append((m.start(), nombre))
            resto = resto[:m.start()] + " " * (m.end() - m.start()) + resto[m.end():]
    return [nombre for _, nombre in sorted(hallados)]


def territorios_de(seccion: str, texto: str) -> list:
    if seccion == SECCION_A:
        dptos = departamentos_de(texto)
        return dptos or [SIN_DEPARTAMENTO]
    if texto in ENCUENTRO_A_DEPARTAMENTOS:
        return ENCUENTRO_A_DEPARTAMENTOS[texto]
    dptos = departamentos_de(texto)
    if len(dptos) == 1 and sin_tildes(texto).strip() == sin_tildes(dptos[0]).strip():
        return dptos                      # el encuentro regional es un departamento
    return [f"{texto} (encuentro regional)"]


# --------------------------------------------------------------------------------------
# Sectores: nombres equivalentes entre las fuentes del anexo, unificados para filtrar
# --------------------------------------------------------------------------------------
SECTOR_AGRUPADO = {
    "Vías e infraestructura de transporte": "Transporte",
    "Transporte": "Transporte",
    "Salud": "Salud",
    "Salud y Protección Social": "Salud",
    "Vivienda": "Vivienda, Ciudad y Territorio",
    "Vivienda, Ciudad y Territorio": "Vivienda, Ciudad y Territorio",
    "Ambiente y gestión del riesgo": "Ambiente y gestión del riesgo",
    "Ambiente y Desarrollo Sostenible": "Ambiente y gestión del riesgo",
    "Desarrollo económico y turismo": "Comercio, Industria y Turismo",
    "Comercio, Industria y Turismo": "Comercio, Industria y Turismo",
    "Agropecuario y desarrollo rural": "Agricultura y Desarrollo Rural",
    "Agricultura y Desarrollo Rural": "Agricultura y Desarrollo Rural",
    "Energía": "Minas y Energía",
    "Minas y Energía": "Minas y Energía",
    "Inclusión social y primera infancia": "Inclusión social",
    "Inclusión Social y Reconciliación": "Inclusión social",
    "TIC y conectividad": "TIC y conectividad",
    "Tecnologías de la Información y las Comunicaciones": "TIC y conectividad",
    "Deporte y recreación": "Deporte y Recreación",
    "Deporte y Recreación": "Deporte y Recreación",
}


def sectores_de(texto: str) -> list:
    """Sectores de un proyecto (algunos traen varios, separados por « / »), ya unificados."""
    salida = []
    for s in [p.strip() for p in texto.split(" / ") if p.strip()]:
        g = SECTOR_AGRUPADO.get(s, s)
        if g not in salida:
            salida.append(g)
    return salida


# --------------------------------------------------------------------------------------
# Lectura del PDF
# --------------------------------------------------------------------------------------
def limpia(celda) -> str:
    t = unicodedata.normalize("NFC", (celda or "").replace("\n", " "))
    return re.sub(r"\s+", " ", t).strip()


def leer_pdf(ruta: str) -> list:
    filas = []
    with pdfplumber.open(ruta) as pdf:
        for n, pag in enumerate(pdf.pages, 1):
            for tabla in pag.extract_tables():
                enc = [limpia(c) for c in tabla[0]] if tabla else []
                if not enc:
                    continue
                if enc[0] == "Departamento":
                    seccion, esperadas = SECCION_A, 5
                elif enc[0] == "Encuentros regionales":
                    seccion, esperadas = SECCION_B, 4
                else:
                    raise ValueError(f"Tabla desconocida en la página {n}: {enc}")
                for fila in tabla[1:]:
                    c = [limpia(x) for x in fila]
                    if len(c) != esperadas or not all(c):
                        raise ValueError(f"Fila incompleta en la página {n}: {c}")
                    if seccion == SECCION_A:
                        dep, mun, nombre, sector, base = c
                    else:
                        (dep, nombre, sector, base), mun = c, ""
                    filas.append({"seccion": seccion, "dep_pdf": dep, "municipio": mun,
                                  "nombre": nombre, "sector_pdf": sector, "base": base, "pagina": n})
    return filas


# --------------------------------------------------------------------------------------
# Escritura del libro
# --------------------------------------------------------------------------------------
COLUMNAS = [
    ("N.°", 7), ("Sección", 34), ("Departamento o encuentro regional (PDF)", 26), ("Municipio", 20),
    ("Nombre del proyecto", 90), ("Sector (PDF)", 30), ("Base de identificación", 28),
    ("Página del PDF", 9), ("Departamento o región (filtro)", 30), ("Sector (filtro)", 30),
    ("Repetido en el PDF", 11),
]
AZUL, AZUL_CLARO = "1B3E6C", "347399"


def escribir(filas: list, salida: str, origen: str):
    for i, f in enumerate(filas, 1):
        f["n"] = i
        f["territorios"] = "; ".join(territorios_de(f["seccion"], f["dep_pdf"]))
        f["sectores"] = "; ".join(sectores_de(f["sector_pdf"]))
    vistos = set()
    for f in filas:
        clave = (f["seccion"], f["dep_pdf"], f["municipio"], f["nombre"], f["sector_pdf"], f["base"])
        f["repetido"] = "Sí" if clave in vistos else ""
        vistos.add(clave)

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Proyectos"
    ws.append([c for c, _ in COLUMNAS])
    for f in filas:
        ws.append([f["n"], f["seccion"], f["dep_pdf"], f["municipio"], f["nombre"], f["sector_pdf"],
                   f["base"], f["pagina"], f["territorios"], f["sectores"], f["repetido"]])
    for j, (_, ancho) in enumerate(COLUMNAS, 1):
        ws.column_dimensions[get_column_letter(j)].width = ancho
        c = ws.cell(1, j)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=AZUL_CLARO if j in (9, 10) else AZUL)
        c.alignment = Alignment(wrap_text=True, vertical="center")
    for fila in ws.iter_rows(min_row=2):
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions

    # ---- Notas
    nt = wb.create_sheet("Notas")
    por_seccion = collections.Counter(f["seccion"] for f in filas)
    n_rep = sum(1 for f in filas if f["repetido"])
    notas = [
        ("Fuente", origen),
        ("Digitalizado", datetime.date.today().isoformat() + " con herramientas/digitalizar_anexo4.py"),
        ("Proyectos", f"{len(filas)} filas ({n_rep} repetidas tal cual en el PDF, marcadas en la última columna)"),
        (SECCION_A, f"{por_seccion[SECCION_A]} filas"),
        (SECCION_B, f"{por_seccion[SECCION_B]} filas"),
        ("", ""),
        ("Qué es cada columna", ""),
        ("Columnas con «(PDF)» y las demás hasta «Página del PDF»", "Tal como están en el PDF: no se corrigió ortografía, mayúsculas ni nombres."),
        ("Departamento o región (filtro)", "Departamentos de cada proyecto, separados por «; ». Un proyecto de varios departamentos sale en cada uno. Los encuentros regionales que no son un departamento conservan su nombre «(encuentro regional)»; lo nacional o sin departamento, «Sin departamento específico». «Santanderes» se toma como Santander y Norte de Santander, e «Insular» como San Andrés, Providencia y Santa Catalina. La página usa esta columna."),
        ("Sector (filtro)", "El sector del PDF con los nombres equivalentes unificados (tabla de abajo). Un proyecto con varios sectores («A / B») sale en cada uno. La página usa esta columna."),
        ("", ""),
        ("Si no estás de acuerdo con una agrupación", "Cambia el valor en la columna «Sector (filtro)» o «Departamento o región (filtro)» (por ejemplo con Buscar y reemplazar); la página lee esas columnas tal cual."),
        ("", ""),
        ("Sector (PDF)", "Sector (filtro)   ·   proyectos"),
    ]
    cuenta = collections.Counter(s.strip() for f in filas for s in f["sector_pdf"].split(" / "))
    for s, n in sorted(cuenta.items(), key=lambda kv: (SECTOR_AGRUPADO.get(kv[0], kv[0]), kv[0])):
        notas.append((s, f"{SECTOR_AGRUPADO.get(s, s)}   ·   {n}"))
    for fila in notas:
        nt.append(list(fila))
    nt.column_dimensions["A"].width = 52
    nt.column_dimensions["B"].width = 110
    for fila in nt.iter_rows():
        fila[0].font = Font(bold=True)
        for c in fila:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    wb.save(salida)


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    pdf, salida = sys.argv[1], sys.argv[2]
    filas = leer_pdf(pdf)
    escribir(filas, salida, "Anexo 4. Indicativo Proyectos y Megaproyectos Regionales (Bases del PND 2026-2030)")
    print(f"{len(filas)} filas escritas en {salida}")


if __name__ == "__main__":
    main()
