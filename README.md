# Orientador del PND 2026-2030

Página que ayuda a ubicar una idea, un proyecto o un programa dentro de la
estructura del Plan Nacional de Desarrollo: **eje → tema → línea estratégica**.

Tiene dos secciones. A la izquierda, un visor del árbol con la descripción de cada
eje y de cada tema y las palabras clave de cada línea estratégica. A la derecha, un chat que traduce una pregunta
en lenguaje corriente a términos del documento y devuelve las líneas estratégicas donde
esos términos aparecen. El chat se pliega hacia el lado para dejarle todo el
ancho al árbol.

Esto **orienta**: cada resultado es una opción sugerida.

## Cómo correrlo

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.ejemplo .streamlit/secrets.toml   # y pon la llave
streamlit run app.py
```

El árbol y su buscador funcionan sin llave. La llave sólo hace falta para el chat.

## Archivos

| Archivo | Qué contiene |
|---|---|
| `app.py` | Interfaz: las dos secciones y el plegado del chat. |
| `arbol.py` | Genera el visor del árbol como HTML autocontenido. |
| `buscador.py` | **La búsqueda. Aquí se decide todo lo que se encuentra.** |
| `motor.py` | Herramientas que ve el modelo, reglas de comportamiento y ciclo de conversación. |
| `proyectos.py` | Filtra los proyectos y megaproyectos regionales por departamento y sector (sin modelo ni búsqueda por palabras). |
| `herramientas/digitalizar_anexo4.py` | Vuelve a generar el Excel de proyectos desde el PDF del Anexo 4 (sólo si cambia el PDF). |
| `herramientas/clasificar_proyectos.py` | Genera `data/Clasificacion_proyectos.xlsx`: ubica proyectos en las líneas estratégicas con el score y con Claude, y compara. |
| `data/Estructura_PND_Palabras_claves.xlsx` | La estructura. Se lee directo del Excel. |
| `data/Proyectos_Megaproyectos_Regionales.xlsx` | El Anexo 4 de las Bases del PND digitalizado: 2.888 proyectos. |
| `data/Clasificacion_proyectos.xlsx` | Clasificación de prueba de 63 proyectos (Amazonas y el encuentro «Amazonia») en las líneas estratégicas: score frente a Claude. |
| `data/sinonimos.csv` | Diccionario editable de palabra corriente → término del documento. |
| `data/reglas.csv` | Reglas editables: grupos de líneas estratégicas (p. ej. el eje 7) que solo se sugieren si la pregunta menciona sus palabras disparadoras. |

## Cómo busca

No hay modelo entrenado, ni puntajes aprendidos, ni análisis semántico. Todo es
coincidencia de texto en tres capas, y cada una se explica en una frase.

**Capa 1 — literal.** La palabra tal como se escribió, sin tildes ni mayúsculas.

**Capa 2 — raíz.** Los primeros caracteres de la palabra, para que *educativa*
encuentre *educación* y *educativo*. La regla es fija: 8 letras o más, los
primeros 7 caracteres; 6 o 7 letras, los primeros 5; menos de 6, la palabra
completa. (Con 7, *integración* ya no coincide con *integridad*.)

**Capa 3 — sinónimos.** El diccionario de `data/sinonimos.csv` traduce palabras de
uso corriente al vocabulario del documento. Esta capa existe porque el documento
no dice *colegio*, dice *infraestructura educativa*; no dice *beca*, dice
*financiación estudiantil*.

El orden de los resultados sale de un score que se explica en una línea. Se busca en
tres campos —**palabras clave, nombre de la línea estratégica y tema**— y, por cada término
que coincide, se suma:

> (peso del campo + la mitad del peso de cada otro campo donde también coincide) × multiplicador de origen × especificidad del término

- **Peso del campo:** palabras clave 4, nombre 4, tema 3. Si el mismo término aparece
  también en otro campo de la misma línea (por ejemplo «salud» en una palabra clave, en
  el nombre y en el tema), cada campo adicional suma la mitad de su peso: confirma que la
  línea trata de eso, sin duplicar el puntaje. Es lo que desempata a «Salud en las
  regiones» frente a líneas que sólo mencionan «salud» en una palabra clave.
- **Multiplicador de origen:** ×2 para los términos que llegan a la búsqueda (los de
  la persona y los que el modelo traduce); ×1 para los que agrega el diccionario.
- **Especificidad:** un término que aparece en muchas líneas estratégicas dice poco. Vale
  ln(total ÷ líneas estratégicas donde aparece), contando como mínimo 3 líneas estratégicas para
  que una sola palabra rara no domine: un término que está en 3 de las 122
  líneas estratégicas vale 3,7; uno que está en 26 vale 1,5.
- **Las líneas estratégicas no tienen descripción:** sólo palabras clave. Las descripciones y
  las palabras clave de eje y tema se muestran en el árbol, pero no puntúan.

Ese score lo calcula `buscador.py`, no el modelo: el modelo sólo elige los términos
de búsqueda.

Con el score se arman dos grupos, siempre relativos al mejor resultado, y un tercero
que no depende del score:

| Categoría | Regla | Dónde se ve |
|---|---|---|
| **Más cercanas** | ≥ 85 % del mejor score y **como máximo 3** (si hay más, las que sobran pasan a «Relacionadas»; el desempate es por más términos distintos coincidentes y, al final, por código) | respuesta del chat y árbol |
| **Relacionadas** | ≥ 30 % del mejor, hasta 10 (más las «Más cercanas» que sobraron) | árbol |
| **En la descripción** | líneas estratégicas sin coincidencia propia cuyo **tema** menciona el término en su descripción; sin puntaje, y sólo con los términos de la persona o del modelo (no con los del diccionario) | árbol |

Lo que coincide por debajo del 30 % no se muestra. Los umbrales y los topes están al
comienzo de `buscador.py` (`UMBRAL_CERCANAS`, `MAX_CERCANAS`, `UMBRAL_RELACIONADAS`,
`MAX_RELACIONADAS`).

**Consultas amplias.** Si 3 o más líneas llegan al umbral de «Más cercanas» y son de temas
distintos (por ejemplo con «infraestructura»: defensa, salud, cultura), la consulta no distingue
y el buscador lo señala (`muy_amplia`) y
ofrece, tal cual están en el PND, las palabras clave que la concretan («Infraestructura
deportiva», «Infraestructura cultural»…). La respuesta dice que da muchos resultados y
pregunta de qué tipo, y el árbol muestra todo de todos modos. Una palabra suelta se busca
siempre, sin pedir aclaración antes.

**Reglas (`data/reglas.csv`).** Hay grupos de líneas estratégicas que solo tienen sentido para
ciertas preguntas. Hoy: el **eje 7** (reconstrucción tras el sismo) solo se sugiere si
la pregunta menciona un desastre —terremoto, incendio, inundación…—; si no, sus
líneas estratégicas no se muestran y la respuesta lo avisa en «Notas». El archivo tiene tres
columnas: `aplica_a` (`eje 7`, `tema 7.1` o un código `7.1.3`), `palabras_disparadoras`
(separadas por `;`) y `nota` (si lleva comas, entre comillas). Se edita en Excel; si
apunta a algo que no existe, la aplicación avisa al arrancar.

Cada resultado viene con la evidencia —qué término coincidió y en qué campo— y la
interfaz la muestra. La respuesta del chat trae las «Más cercanas» (máximo 3) y, debajo, el
desplegable «Notas» con la documentación de esa búsqueda: sinónimos agregados, reglas
que actuaron, cuántas líneas estratégicas hay en cada categoría y cómo se calcula el orden. En
el árbol, todas las marcadas se pintan en azul con su insignia; después de cada
respuesta el árbol queda en «Más cercanas» (ficha abierta, con sus palabras clave
resaltadas) y los botones «Mostrar: Más cercanas · Relacionadas · En la descripción ·
Todos» cambian de grupo. La descripción de cada eje y tema
está escondida tras su botón «i». Dos pequeños «i» de la página explican qué es el chat y
qué significan las categorías.
Si la sugerencia está mal, se puede ver exactamente por qué.

El buscador propio del árbol resalta lo que escribes; entre comillas busca sólo palabras
completas («deporte» no encuentra «deportivo»). Cuando la conversación del
chat ya es larga, tiene su propio scroll para que no alargue la página y deje el árbol
fuera de vista. El tema es siempre claro (`.streamlit/config.toml`), aunque el
dispositivo esté en modo oscuro.

## Qué hace el modelo y qué no

El modelo **ve el catálogo oficial** (códigos, nombres y palabras clave de las 122 líneas
estratégicas, más la descripción de cada tema, tomados del libro de estructura) y lo usa
para una sola cosa: traducir lo que escribe la persona al vocabulario del Plan y elegir
los términos de búsqueda. Si el texto no dice qué es el proyecto («AVEM Fase 1»; no
«Gasoducto Aguazul–Yopal», que dice qué es), pide una descripción en vez de buscar. Si es una
sola palabra genérica («infraestructura»), busca sólo esa palabra y la interfaz pregunta de qué
tipo. Como el catálogo sale del libro, al cambiar el libro cambia lo que ve el modelo.

El modelo ve también el **diccionario de vocabulario corriente** (`data/sinonimos.csv`), sólo con los
términos que el Plan sí tiene escritos (`buscador.sinonimos_vivos`). Así entiende que «placa huella» es
un proyecto de vías terciarias en vez de preguntar qué es. Es la jerga que el modelo no conoce por sí
solo; lo demás lo traduce él con el catálogo. Añadir 21 filas más de jerga de proyectos (pavimentación,
PTAR, estadio, CCTV…), cada una con términos que existen en el Plan, **no cambió ningún resultado** en
las pruebas, y por eso no se dejaron: más filas sólo valen si el modelo falla por no conocer una palabra.

**No redacta los resultados.** Las líneas estratégicas de la respuesta —código, nombre,
dónde coincidió y palabras clave— las escribe `motor.py` desde el libro, a partir de lo
que devolvió `buscador.py`. Dos candados evitan que el modelo, que conoce el catálogo,
presente algo que la búsqueda no encontró:

- La respuesta con resultados sale de los datos; el texto del modelo no entra.
- El modelo **siempre responde con una herramienta** (`tool_choice` «any»): `buscar_estrategias`
  para una idea o proyecto, o `contestar` sólo para pedir un dato que falta, saludar o decir
  que el mensaje no trata del Plan. No puede contestar «de memoria» con una línea del catálogo.
- Si su `contestar` nombra un código o una línea que ninguna herramienta devolvió (ni se
  mostró antes en la conversación), ese texto se descarta y se le obliga a buscar.
- Las frases de dos o más palabras de `data/sinonimos.csv` que escriba la persona («placa
  huella») se agregan siempre a la búsqueda, aunque el modelo las haya reformulado. Las de una
  sola palabra se dejan a su criterio («casa» en «casa de gobierno» no es vivienda).
- Si aun así no hay una respuesta utilizable, se busca con las palabras de la persona (las
  frases del diccionario más sus palabras útiles, sin verbos de trámite ni la pregunta misma).

Además, con resultados no hace falta una segunda llamada al modelo: cada consulta cuesta
una llamada, y el catálogo, que no cambia, se guarda en caché.

Modelo: `claude-haiku-4-5`. Cada consulta cuesta una fracción de centavo. Conviene
poner un tope de gasto en la consola de Anthropic.

## Proyectos y Megaproyectos regionales

La sección 03 de la página lista los proyectos del **Anexo 4** de las Bases del PND 2026-2030
(«Indicativo Proyectos y Megaproyectos Regionales», 225 páginas), digitalizado en
`data/Proyectos_Megaproyectos_Regionales.xlsx`. Dos selectores —**departamento o región** y
**sector**— filtran la lista, que muestra el nombre del proyecto, su municipio, su departamento y su
sector; con «Todos» en ambos se ven los primeros 500. Elegir en un selector no recarga el árbol ni
el chat (es un fragmento de Streamlit).

El libro trae las dos tablas del anexo —«Megaproyectos y proyectos de alto impacto local» (2.495
filas, con departamento y municipio) y «Otras iniciativas y necesidades de encuentros regionales»
(393 filas, con el nombre del encuentro regional)— con el texto tal cual está en el PDF, incluidos sus
errores de ortografía y algún nombre cortado en el propio PDF. Además trae dos columnas para filtrar:

- **Departamento o región (filtro):** los departamentos de cada proyecto; uno de varios departamentos
  sale en cada uno. Los encuentros regionales que no son un departamento («Pacífico», «Amazonia»…)
  conservan su nombre; «Santanderes» se toma como Santander y Norte de Santander e «Insular» como San
  Andrés, Providencia y Santa Catalina; lo nacional queda como «Sin departamento específico».
- **Sector (filtro):** el sector del PDF con los nombres equivalentes unificados («Salud» y «Salud y
  Protección Social», «Transporte» y «Vías e infraestructura de transporte», «Energía» y «Minas y
  Energía»…). La tabla completa está en la hoja «Notas». Si una agrupación no te convence, cambia el valor
  de esa columna en la hoja «Proyectos»; la página la lee tal cual.

**Clasificación de prueba.** Los 63 proyectos de Amazonas y del encuentro regional «Amazonia» traen, en la
lista, su ubicación en las líneas estratégicas del Plan de dos maneras, y si coinciden: el **orientador** es
lo que hace la aplicación (el modelo elige los términos y el score ubica las líneas) y **Claude** es una
clasificación hecha leyendo el catálogo del Plan. La segunda es un criterio, no una verdad: se corrige
editando las columnas «Claude: …» de `data/Clasificacion_proyectos.xlsx`, que es lo que lee la página. El
orientador es una sola corrida y el modelo varía un poco entre corridas (unos 2 o 3 de 63 proyectos
cambian de línea). Al elegir un departamento aparece además un resumen de sectores y municipios.

Cinco filas aparecen repetidas tal cual en el PDF: están en el libro, marcadas en «Repetido en el PDF»,
y la página no las muestra dos veces. Para volver a generar el libro si cambia el PDF:
`pip install pdfplumber openpyxl` y `python herramientas/digitalizar_anexo4.py <pdf> data/Proyectos_Megaproyectos_Regionales.xlsx`.

## Probar los cambios

- `python herramientas/pruebas_rapidas.py` (sin llave ni red): el ciclo del modelo con un modelo simulado y el
  buscador con casos conocidos. Dice «TODO OK» o cuál falló.
- `ANTHROPIC_API_KEY=... python herramientas/clasificar_proyectos.py` (con llave de prueba; cuesta unos
  centavos): corre los 63 proyectos con el modelo real y escribe `data/Clasificacion_proyectos.xlsx`. Como el
  modelo no es determinista, conviene comparar el promedio de dos o tres corridas antes de concluir. El API
  ya no acepta fijar `temperature`, así que no se puede quitar esa variación.

## Mantenimiento

**Cuando cambie la estructura:** reemplaza
`data/Estructura_PND_Palabras_claves.xlsx` por la versión nueva y reinicia la
aplicación. Se leen tres hojas por nombre: `VF_Ejes` (eje, descripción), `VF_Temas`
(tema, descripción) y `VF_Estructura` (línea estratégica y su única lista de palabras clave, de 1 a 10).
**La fuente oficial es el anexo técnico del PDF «Audiencias Públicas PPI 2027-2030»**: de allí salen los nombres,
las descripciones de ejes y temas y las palabras clave del libro (3.1.6 y 7.1.2 traen sólo 3 en el PDF). No hay nada codificado a mano, ni siquiera cuántos ejes,
temas o líneas estratégicas hay. Al arrancar se valida que todo cuadre (que cada tema exista,
que los códigos encajen, 1–10 palabras clave, descripciones completas…) y, si algo
falla, la aplicación lo dice con un mensaje claro en vez de fallar en silencio.

**Cuando una búsqueda no encuentre algo que debería:** como el modelo ve el catálogo, casi
siempre es que el Plan no tiene una palabra clave para eso (un asunto de contenido, no de
código). El diccionario `data/sinonimos.csv` ya **no es necesario** para que el modelo
entienda el vocabulario, pero sigue funcionando como ayuda opcional: se abre en Excel, se
agrega la palabra corriente y los términos del documento separados por `;`, y se
reinicia. No hay que tocar código.

Al agregar una fila conviene verificar que el término de destino **sí exista** en
el archivo de estructura; si no existe, la fila no sirve de nada. La forma rápida
de comprobarlo es buscar la palabra en el buscador del árbol, que es literal.

## Lo que no hace

- No cubre las iniciativas ni los indicadores: trabaja sólo sobre el archivo de
  estructura y palabras clave. El análisis de la matriz de iniciativas está en
  `analisis_iniciativas/`.
- No pondera, no decide ni recomienda. Describe dónde aparecen las palabras.
- Los códigos de línea estratégica de esta versión **no son los de versiones anteriores**
  (se reutilizaron y renumeraron); lo que se enlace a la estructura, como los
  indicadores, debe usar los códigos nuevos. La columna «Código anterior» del libro
  sirve sólo para una migración puntual.
