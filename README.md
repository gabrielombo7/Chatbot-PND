# Orientador del PND 2026-2030

Página que ayuda a ubicar una idea, un proyecto o un programa dentro de la
estructura del Plan Nacional de Desarrollo: **eje → tema → estrategia**.

Tiene dos secciones. A la izquierda, un visor del árbol con la descripción y las
palabras clave de cada estrategia. A la derecha, un chat que traduce una pregunta
en lenguaje corriente a términos del documento y devuelve las estrategias donde
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
| `data/Estructura_PND_Palabras_claves.xlsx` | La estructura. Se lee directo del Excel. |
| `data/sinonimos.csv` | Diccionario editable de palabra corriente → término del documento. |

## Cómo busca

No hay modelo entrenado, ni puntajes aprendidos, ni análisis semántico. Todo es
coincidencia de texto en tres capas, y cada una se explica en una frase.

**Capa 1 — literal.** La palabra tal como se escribió, sin tildes ni mayúsculas.

**Capa 2 — raíz.** Los primeros caracteres de la palabra, para que *educativa*
encuentre *educación* y *educativo*. La regla es fija: 8 letras o más, los
primeros 6 caracteres; 6 o 7 letras, los primeros 5; menos de 6, la palabra
completa.

**Capa 3 — sinónimos.** El diccionario de `data/sinonimos.csv` traduce palabras de
uso corriente al vocabulario del documento. Esta capa existe porque el documento
no dice *colegio*, dice *infraestructura educativa*; no dice *beca*, dice
*financiación estudiantil*.

El orden de los resultados sale de un score que se explica en una línea. Se busca
sólo en tres campos —**palabras clave, nombre de la estrategia y tema**; la descripción
no cuenta— y, por cada término que coincide, se suma:

> peso del campo × multiplicador de origen × especificidad del término

- **Peso del campo:** palabras clave 4, nombre 4, tema 3.
- **Multiplicador de origen:** ×2 para los términos que llegan a la búsqueda (los de
  la persona y los que el modelo traduce); ×1 para los que agrega el diccionario.
- **Especificidad:** un término que aparece en muchas estrategias dice poco. Vale
  ln(total ÷ estrategias donde aparece): un término que está en 1 de las 123
  estrategias vale 4,8; uno que está en 26 vale 1,6.

Ese score lo calcula `buscador.py`, no el modelo: el modelo sólo elige los términos
de búsqueda.

Con el score se arman tres niveles, siempre relativos al mejor resultado:

| Nivel | Regla | Dónde se ve |
|---|---|---|
| **Más cercana** | ≥ 60 % del mejor score (los empates con el mejor siempre entran) | respuesta del chat (hasta 5) y árbol |
| **Otra** | ≥ 15 % del mejor, hasta 10 | desplegable «Otras estrategias» y árbol |
| **Relacionada** | el resto | sólo el árbol |

Dos estrategias con el mismo score reciben el mismo trato: nunca se elige entre ellas.
Los umbrales y los topes están al comienzo de `buscador.py` (`UMBRAL_CERCANAS`,
`UMBRAL_OTRAS`, `MAX_CHAT`, `MAX_TOGGLE`).

Cada resultado viene con la evidencia —qué término coincidió y en qué campo— y la
interfaz la muestra: la respuesta trae las más cercanas y el desplegable «Otras
estrategias» las siguientes. En el árbol, todas las que coincidieron se marcan en
amarillo con su insignia; las más cercanas se abren solas y la ficha dice «Coincide
con» qué términos, en qué campo. Si la sugerencia está mal, se puede ver exactamente
por qué.

## Qué hace el modelo y qué no

El modelo **no tiene el PND en memoria**: el *system prompt* sólo lleva los
nombres de los 7 ejes. Su única función es convertir la pregunta en términos de
búsqueda y redactar lo que devolvió la herramienta.

Las consecuencias importan:

- No puede inventar una estrategia, porque nunca recibió la lista.
- Si la búsqueda no encuentra nada, lo dice; no tiene con qué rellenar.
- Los códigos y nombres que escribe son los que le devolvió `buscador.py`.

Modelo: `claude-haiku-4-5`. Cada consulta cuesta una fracción de centavo. Conviene
poner un tope de gasto en la consola de Anthropic.

## Mantenimiento

**Cuando cambie la estructura:** reemplaza
`data/Estructura_PND_Palabras_claves.xlsx` por la versión nueva y reinicia la
aplicación. No hay nada codificado a mano: los ejes, los temas, las estrategias y
las palabras clave se leen del archivo. Debe conservar las mismas 9 columnas en el
mismo orden; si no, la aplicación avisa al arrancar en vez de fallar en silencio.

**Cuando una búsqueda no encuentre algo que debería:** casi siempre es que falta
una fila en `data/sinonimos.csv`. Se abre en Excel, se agrega la palabra corriente
y los términos del documento separados por `;`, y se reinicia. No hay que tocar
código.

Al agregar una fila conviene verificar que el término de destino **sí exista** en
el archivo de estructura; si no existe, la fila no sirve de nada. La forma rápida
de comprobarlo es buscar la palabra en el buscador del árbol, que es literal.

## Lo que no hace

- No cubre las iniciativas ni los indicadores: trabaja sólo sobre el archivo de
  estructura y palabras clave. El análisis de la matriz de iniciativas está en
  `analisis_iniciativas/`.
- No pondera, no decide ni recomienda. Describe dónde aparecen las palabras.
- La estructura del PND todavía está en elaboración; 17 de las 123 estrategias
  aún no tienen descripción propia y en esas la búsqueda depende de las palabras
  clave y del nombre.
