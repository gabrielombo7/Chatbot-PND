# Orientador del PND 2026-2030 — documentación técnica

Este archivo es para que otra sesión de Claude (u otra persona) entienda el
proyecto sin tener que leer todo el código primero. Léelo antes de tocar nada.

## 1. Qué es esto

Una página que ayuda a ubicar una idea, un proyecto o un programa dentro de la
estructura del Plan Nacional de Desarrollo 2026-2030: **eje → tema →
estrategia**. La hace Gabriel (DNP, Dirección de Programación de Inversiones
Públicas) como ejercicio preliminar y sencillo — esto **orienta**, no define.

Dos secciones:
- **Árbol** — visor plegable de la estructura completa, con buscador propio
  (literal) y fichas con descripción y palabras clave de cada estrategia.
- **Chat** — la persona describe su idea en lenguaje corriente; el asistente
  traduce eso a términos del documento, busca por coincidencia de palabras y
  devuelve las estrategias donde esos términos aparecen, con la evidencia de
  dónde coincidió cada uno.

## 2. Estado actual (2026-11-10)

- Funciona en local con `streamlit run app.py`.
- El código está en GitHub: **`gabrielombo7/Chatbot-PND`**
  (`https://github.com/gabrielombo7/Chatbot-PND`), rama `main`, 2 commits.
- Streamlit Community Cloud ya está conectado a la cuenta de GitHub de Gabriel,
  pero no está confirmado que la app ya esté desplegada ahí — falta configurar
  el *secret* `ANTHROPIC_API_KEY` en el panel de la app (nunca va en el repo).
- **Visibilidad del repo sin confirmar.** El archivo de estructura dice "uso
  interno" en su columna de fuente — conviene que el repo sea **privado**
  hasta que alguien del DNP confirme que puede ser público.

### Limpieza pendiente en el repo (no se hizo porque no era lo pedido)

El repo tiene equipaje de más, todo inofensivo pero evitable:
- `__pycache__/*.pyc` quedó commiteado (binarios de bytecode, nada sensible).
- `.DS_Store` quedó commiteado.
- Existe una carpeta **`para_github/` anidada y duplicada** dentro del propio
  repo (quedó de un paso intermedio de despliegue): repite `app.py`, `arbol.py`,
  etc. Los archivos que Streamlit Cloud realmente usa son los del nivel raíz
  del repo (`app.py`, no `para_github/app.py`), así que la copia anidada es
  puro ruido y conviene borrarla del repo (`git rm -r para_github`).
- No hay `.gitignore`. Se recomienda uno con:
  ```
  .streamlit/secrets.toml
  __pycache__/
  *.pyc
  .DS_Store
  ```
- **Verificado:** no hay ninguna llave de API en el historial de git. Lo único
  que aparece al buscar "ANTHROPIC_API_KEY" es el *nombre* de la variable en
  `app.py` (`st.secrets.get("ANTHROPIC_API_KEY", ...)`), nunca un valor.

## 3. La pregunta que motivó este documento: ¿GitHub Pages o Streamlit?

**GitHub Pages es hosting 100% estático**: solo sirve HTML/CSS/JS que corre en
el navegador de quien visita la página. No hay servidor, no hay Python, no hay
forma de esconder una llave — cualquier texto que viaje al navegador es
legible por cualquiera con "ver código fuente".

Eso traza una frontera exacta en este proyecto, y es la frontera central de
todo el diseño:

| Pieza | Qué hace | ¿Corre en GitHub Pages? |
|---|---|---|
| **Árbol** (`arbol.py` → HTML) | Muestra la estructura, pliega/despliega, buscador literal en el navegador | **Sí**, tal cual. Ya es HTML/CSS/JS autocontenido con los datos incrustados como JSON. |
| **Buscador de palabras** (`buscador.py`) | Las 3 capas de coincidencia (ver sección 4) | **Sí, pero hay que reescribirlo en JavaScript.** Hoy está en Python y corre del lado del servidor de Streamlit. La lógica es simple (normalizar texto, recortar palabras, comparar conjuntos) y se puede portar a JS sin perder nada: no usa ninguna librería de Python que no tenga equivalente trivial en JS. |
| **Traducción de la pregunta + redacción** (`motor.py`, llama a Claude) | Convierte "quiero un colegio" en `["colegio", "infraestructura educativa", ...]` y redacta la respuesta en lenguaje natural | **No.** Necesita la llave del API de Anthropic, y una llave en JS de cliente queda expuesta a cualquiera. Esto requiere un servidor (Streamlit, una función serverless, un pequeño backend) que la guarde y haga la llamada por la persona. |

**Conclusión práctica:** no es "GitHub Pages o Streamlit" sino **qué parte va
en cada uno**. Hay tres caminos razonables:

1. **Todo en Streamlit** (como está hoy). Más simple de mantener porque es un
   solo lenguaje (Python) y un solo sitio. Costo: depende de que Streamlit
   Community Cloud esté arriba, y la primera carga after de inactividad tarda
   unos segundos en "despertar".
2. **Todo en GitHub Pages, sin el LLM.** Se porta `buscador.py` a JavaScript
   (capas 1 y 2 son mecánicas; la capa 3 es leer el mismo `sinonimos.csv` como
   JSON). La persona escribe palabras sueltas en vez de una pregunta en
   lenguaje natural, y la página le muestra las estrategias donde esas palabras
   aparecen, con la misma evidencia de hoy. **Se pierde** la traducción
   automática de "colegio" a "infraestructura educativa" salvo que la persona
   ya conozca el diccionario, y se pierde la redacción en prosa. **Se gana**
   gratuidad total, carga instantánea, cero dependencia de que un servicio
   externo esté activo, y nada que mantener del lado del API.
3. **Híbrido**: el árbol vive en GitHub Pages (gratis, rápido, siempre
   disponible) y el chat con LLM sigue en Streamlit, enlazado desde la página
   de GitHub Pages. Requiere mantener dos sitios y sincronizar el Excel de
   estructura en los dos lugares.

Ninguna opción es objetivamente mejor — depende de si el valor del chat (la
traducción automática de lenguaje corriente a vocabulario del documento) vale
la complejidad de mantener un backend. Dado que el proyecto es "muy preliminar
y sencillo", la opción 2 (todo en GitHub Pages, sin LLM, con una caja de texto
que corre la búsqueda de palabras en el navegador) calza bien con esa
intención y es la más barata de mantener. Pero eso lo decide Gabriel.

## 4. Dónde entra el LLM y dónde el código de coincidencia exacta

Esta es la distinción de diseño más importante del proyecto. Todo el código
la respeta y conviene que cualquier cambio futuro también la respete.

### El LLM (Claude, vía `motor.py`) solo hace dos cosas

1. **Traducir** la pregunta de la persona a una lista de términos de búsqueda
   (palabras de la persona + palabras con que el documento nombraría lo mismo).
2. **Redactar** en prosa lo que devolvió la búsqueda, citando el código exacto
   y el campo donde coincidió cada término.

El modelo **no tiene el contenido del PND en memoria.** El *system prompt* de
`motor.py` solo lleva los nombres de los 7 ejes — ni los temas, ni las
estrategias, ni las palabras clave. Esto es deliberado: si el modelo tuviera
la estructura completa en el prompt, podría "recordar mal" un código o
mezclar dos estrategias parecidas. Al no tener nada, no tiene de dónde
inventar: cada estrategia que menciona viene literalmente del resultado JSON
que le devolvió una herramienta, en la misma llamada.

El ciclo (`motor.responder`) es: Claude pide `buscar_estrategias(terminos)` →
Python ejecuta la búsqueda real → el resultado (con código, nombre, eje, tema,
evidencia) se le devuelve a Claude como *tool_result* → Claude redacta la
respuesta final usando solo esos datos. Hay un tope de 6 vueltas para que un
ciclo que no converge no cuelgue la conversación.

### El código de coincidencia exacta (`buscador.py`) hace todo lo demás

**No hay modelo entrenado, ni puntajes aprendidos, ni análisis semántico.**
Todo es comparación de texto, en tres capas, cada una explicable en una frase:

- **Capa 1 — literal.** La palabra tal como se escribió, sin tildes ni
  mayúsculas (función `normalizar`).
- **Capa 2 — raíz.** Los primeros caracteres de la palabra, para que
  *"educativa"* encuentre *"educación"*. Regla fija y documentada en el código
  (función `raiz`): 8+ letras → 6 caracteres; 6-7 letras → 5; menos de 6 → la
  palabra completa.
- **Capa 3 — sinónimos.** El archivo `data/sinonimos.csv` traduce palabras de
  uso corriente ("colegio", "beca") a los términos que sí usa el documento
  ("infraestructura educativa", "financiación estudiantil"). Es una tabla
  editable a mano, sin lógica difusa: una palabra de la izquierda, una lista
  de términos de la derecha separados por `;`.

El **orden de los resultados** también es una regla declarada, no un puntaje
estadístico (función `buscar_estrategias`):
1. cuántos términos distintos coincidieron;
2. en qué campo coincidieron — palabras clave y nombre de la estrategia pesan
   más que el tema, y el tema más que la descripción (diccionario
   `PESO_CAMPO`);
3. los términos que llegan a la herramienta (los de la persona y los que el
   modelo traduce al vocabulario del documento) pesan el doble que los que
   agrega el diccionario de sinónimos (ver `factor` en `buscar_estrategias`).

El modelo **no puntúa ni ordena**: sólo elige los términos de búsqueda; a partir
de ahí el orden lo calcula la función. Por eso términos distintos pueden dar
rankings distintos para la misma pregunta.

`buscar_estrategias` devuelve las 5 mejores con su evidencia (`resultados`, lo
único que ve el modelo) y los códigos de **todas** las que coincidieron en ese
mismo orden (`codigos_ordenados`, sólo para el árbol). El árbol los marca todos
en amarillo con una insignia: **Top 1** (la mejor), **Top 5** (de la 2.ª a la
5.ª) y **Relacionada** (el resto), y baja al Top 1. Ojo: «Top 5» significa
«entre las cinco primeras», no «buena coincidencia»; a veces la 2.ª ya es débil.

Cada resultado trae la evidencia completa (qué término, en qué campo, por cuál
capa), y eso es lo que la interfaz muestra en "Otras estrategias" y lo que el
LLM usa para redactar, sin tener que inventar justificaciones.

**Por qué importa esta separación:** todo lo que decide *qué estrategias
aparecen* es determinista, está en `buscador.py`, se puede probar sin llamar a
ningún API y no cambia entre una ejecución y otra. Lo único no determinista es
la *redacción* del texto final. Si algún día se audita por qué el orientador
sugirió algo, la respuesta siempre está en `buscador.py`, nunca en el modelo.

## 5. Archivos del repo

| Archivo | Qué contiene |
|---|---|
| `app.py` | Interfaz Streamlit: las dos secciones, el plegado del chat, el historial de conversación, los términos buscados con los sinónimos aplicados, y el expander "Otras estrategias". |
| `arbol.py` | Genera el visor del árbol como **HTML/CSS/JS autocontenido** (se incrusta con `st.components.v1.html`). Es portable tal cual a cualquier hosting estático, incluido GitHub Pages. |
| `buscador.py` | **El corazón del proyecto.** Carga el Excel de estructura, carga el diccionario de sinónimos, y expone `buscar_estrategias`, `listar_vocabulario` y `detalle_estrategia`. Todo documentado en docstrings largos a propósito. |
| `motor.py` | Las herramientas que ve Claude, el *system prompt*, y el ciclo de conversación (`responder`). Modelo: `claude-haiku-4-5`. |
| `data/Estructura_PND_Palabras_claves.xlsx` | La fuente de verdad. 9 columnas: número/nombre de eje, número/nombre de tema, número/nombre de estrategia, descripción, palabras clave, fuente. Se lee directo; si cambia la estructura, se reemplaza este archivo y se reinicia la app — no hay nada codificado a mano. |
| `data/sinonimos.csv` | El diccionario de la capa 3. Columnas: `palabra`, `terminos_documento` (separados por `;`), `nota`. ~110 filas ya verificadas contra el Excel (cada término de destino existe de verdad en el documento). |
| `requirements.txt` | `streamlit`, `anthropic`, `pandas`, `openpyxl`. |
| `.streamlit/config.toml` | Tema visual (colores, tipografía). |
| `.streamlit/secrets.toml.ejemplo` | Plantilla. El real (`secrets.toml`) **nunca** se commitea — en Streamlit Cloud se configura desde Settings → Secrets de la app. |
| `README.md` | Documentación orientada a correr y mantener la app (cómo instalar, cómo funciona la búsqueda en corto, qué hacer cuando cambie la estructura o falte un sinónimo). Este archivo (`DOCUMENTACION_TECNICA.md`) es el complemento orientado a quien va a **editar el diseño o portar la app**, no solo mantenerla. |

Hay además una carpeta hermana `analisis_iniciativas/` (fuera de este repo,
en `Chatbot/analisis_iniciativas/`) con el análisis de la segunda fuente —la
matriz de iniciativas e indicadores— y su homologación con este árbol. No es
parte de la app; es el insumo que explica, en `informe.html`, por qué ciertas
estrategias no tienen iniciativas enlazadas todavía y por qué una idea puede
encajar en más de un eje. Quien vaya a enriquecer el orientador con
iniciativas/indicadores debe partir de ahí.

## 6. Reglas de diseño que no se deben romper al editar

1. **El modelo nunca recibe la estructura completa.** Si se le ocurre a
   alguien "optimizar" metiendo todo el árbol en el *system prompt* para que
   el modelo "ya sepa" las estrategias, se rompe la garantía de que no
   inventa. La única fuente de verdad en cada respuesta es el resultado de la
   herramienta en esa misma llamada.
2. **Toda sugerencia trae evidencia** (término, campo, capa). Si se agrega una
   forma nueva de buscar, debe poder explicar en una frase por qué encontró lo
   que encontró.
3. **El orden de resultados es una regla escrita, no un modelo entrenado.** Si
   se cambia el orden, se documenta la nueva regla en el docstring de
   `buscar_estrategias`, igual que las actuales.
4. **El diccionario de sinónimos solo lleva términos que existen de verdad**
   en el Excel de estructura. Antes de agregar una fila, se verifica con el
   buscador literal del árbol (que no tiene ninguna capa de traducción) que el
   término de destino aparece.
5. **Nunca se commitea `secrets.toml`.** Solo `secrets.toml.ejemplo`.

## 7. Si te piden portar el árbol+buscador a GitHub Pages

Pasos, en orden:
1. Copiar `arbol.py` casi literal: ya genera HTML/CSS/JS puro. Cambiar la
   función `render` para que, en vez de devolver un string para
   `st.components.v1.html`, escriba un archivo `index.html` completo.
2. Portar `buscador.py` a JavaScript. Es mecánico: `normalizar` (regex +
   `normalize("NFD")`, existe igual en JS), `raiz` (slicing de string),
   `expandir` (leer `sinonimos.csv` convertido a JSON y hacer lookups en un
   diccionario), `buscar_estrategias` (recorrer un array de objetos — el
   mismo Excel convertido a JSON con pandas una sola vez, en build time).
3. Convertir `data/Estructura_PND_Palabras_claves.xlsx` y
   `data/sinonimos.csv` a JSON una vez (con un script de Python, no a mano) y
   publicarlos junto al HTML. Cuando cambie el Excel, se vuelve a correr ese
   script de conversión antes de publicar — no hay conexión en vivo a un
   Excel desde una página estática.
4. Decidir qué pasa con la pregunta en lenguaje natural: sin el LLM, la caja
   de búsqueda recibe palabras sueltas, no una oración. Se puede mantener una
   UX parecida con un campo de texto libre que igual corre las 3 capas (la
   capa 3 ya traduce "colegio" aunque la persona no sepa el vocabulario
   exacto), solo que sin la redacción en prosa de Claude: se muestra
   directamente la lista de resultados con su evidencia, que es, de hecho, lo
   mismo que hoy se le pasa a Claude para que redacte.
5. Nada de esto toca `motor.py`: si más adelante se quiere mantener un chat
   con LLM además del buscador estático, se despliega aparte (Streamlit u
   otro backend) y se enlaza desde la página de GitHub Pages.

## 8. Pendientes conocidos (de la conversación con Gabriel)

- Confirmar visibilidad del repo (recomendado: privado).
- Limpiar el repo: quitar `__pycache__`, `.DS_Store`, la carpeta `para_github/`
  duplicada; agregar `.gitignore`.
- Configurar el secret `ANTHROPIC_API_KEY` en Streamlit Cloud si se sigue ese
  camino.
- De `analisis_iniciativas/homologacion_estrategias.csv`: 36 estrategias con
  homologación "débil" y 15 sin correspondencia, pendientes de revisión
  humana antes de usarse para enriquecer el árbol con iniciativas reales.
- Decidir entre las 3 opciones de la sección 3 (Streamlit / GitHub Pages sin
  LLM / híbrido) — es una decisión de producto, no técnica.
