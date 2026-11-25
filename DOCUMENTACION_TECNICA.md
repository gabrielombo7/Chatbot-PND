# Orientador del PND 2026-2030 — documentación técnica

Este archivo es para que otra sesión de Claude (u otra persona) entienda el
proyecto sin tener que leer todo el código primero. Léelo antes de tocar nada.

## 1. Qué es esto

Una página que ayuda a ubicar una idea, un proyecto o un programa dentro de la
estructura del Plan Nacional de Desarrollo 2026-2030: **eje → tema →
línea estratégica**. La hace Gabriel (DNP, Dirección de Programación de Inversiones
Públicas) como ejercicio preliminar y sencillo — esto **orienta**, no define.

Dos secciones:
- **Árbol** — visor plegable de la estructura completa, con buscador propio
  (literal), descripción de cada eje y tema, y fichas con las palabras clave de cada
  línea estratégica (las líneas estratégicas no tienen descripción).
- **Chat** — la persona describe su idea en lenguaje corriente; el asistente
  traduce eso a términos del documento, busca por coincidencia de palabras y
  devuelve las líneas estratégicas donde esos términos aparecen, con la evidencia de
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
| **Traducción de la pregunta** (`motor.py`, llama a Claude) | Convierte "quiero un colegio" en términos del vocabulario del Plan (con el catálogo a la vista); la respuesta la escribe el código desde los datos | **No.** Necesita la llave del API de Anthropic, y una llave en JS de cliente queda expuesta a cualquiera. Esto requiere un servidor (Streamlit, una función serverless, un pequeño backend) que la guarde y haga la llamada por la persona. |

**Conclusión práctica:** no es "GitHub Pages o Streamlit" sino **qué parte va
en cada uno**. Hay tres caminos razonables:

1. **Todo en Streamlit** (como está hoy). Más simple de mantener porque es un
   solo lenguaje (Python) y un solo sitio. Costo: depende de que Streamlit
   Community Cloud esté arriba, y la primera carga after de inactividad tarda
   unos segundos en "despertar".
2. **Todo en GitHub Pages, sin el LLM.** Se porta `buscador.py` a JavaScript
   (capas 1 y 2 son mecánicas; la capa 3 es leer el mismo `sinonimos.csv` como
   JSON). La persona escribe palabras sueltas en vez de una pregunta en
   lenguaje natural, y la página le muestra las líneas estratégicas donde esas palabras
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

### El LLM (Claude, vía `motor.py`) solo hace una cosa

**Traducir** lo que escribe la persona a términos de búsqueda con el vocabulario del Plan
(y, si el texto no dice qué es el proyecto, pedir un dato). Para eso el *system prompt* lleva
el **catálogo oficial** generado desde el libro (`motor.catalogo_texto()`: ejes, temas con su
descripción, y cada línea estratégica con su nombre y palabras clave; unas 9 mil palabras,
con `cache_control` para que se guarde en caché). Ya no se mantiene un diccionario para
que el modelo conozca el vocabulario: al cambiar el libro cambia el catálogo.

**El modelo no redacta los resultados.** Conocer el catálogo hace posible que el modelo
nombre líneas que la búsqueda no devolvió, así que el diseño lo impide en código:

1. Con resultados, la respuesta la escribe `motor.texto_busqueda` desde el resultado de
   `buscar_estrategias` (código, nombre y palabras clave tal cual, y dónde coincidió cada
   una). El texto del modelo no entra, y no hace falta una segunda llamada al modelo.
2. El modelo **siempre responde con una herramienta** (`tool_choice` «any»): `buscar_estrategias`,
   `listar_vocabulario`, `detalle_estrategia` o `contestar` (texto breve para pedir un dato, saludar
   o decir que no trata del Plan). Si su `contestar` contiene un código de línea que ninguna
   herramienta devolvió, o el nombre de una línea que no devolvió ninguna
   (`motor.lineas_ajenas`), se rechaza con un `tool_result` de error y la siguiente llamada obliga a
   `buscar_estrategias` (`tool_choice` por nombre). Los códigos que ya se mostraron antes en la
   conversación se pueden volver a mencionar. Es el defecto que se corrigió el 18 de noviembre:
   sin esto, el modelo podía contestar de memoria con una línea del catálogo, el texto se
   descartaba y la búsqueda de respaldo con palabras sueltas daba nada («placa huella») o ruido.
   Además, las frases de 2 o más palabras del diccionario que escribió la persona
   (`buscador.frases_del_diccionario`) se agregan a los términos de toda búsqueda.
3. Una ficha pedida por código se escribe también desde los datos (`texto_ficha`).

El ciclo (`motor.responder`) es: Claude pide `buscar_estrategias(terminos)` → Python ejecuta la
búsqueda real → si hay resultados, el texto sale de los datos (`_cerrar`); si no, el resultado
vuelve a Claude como *tool_result* para que reintente (o llame `listar_vocabulario`). Si nada
sirve, `_cerrar` busca con las palabras de la persona (`buscador.terminos_del_texto`: frases del
diccionario más palabras útiles, sin verbos de trámite ni la pregunta misma). Hay un tope de 6
vueltas para que un ciclo que no converge no cuelgue la conversación.

### El código de coincidencia exacta (`buscador.py`) hace todo lo demás

**No hay modelo entrenado, ni puntajes aprendidos, ni análisis semántico.**
Todo es comparación de texto, en tres capas, cada una explicable en una frase:

- **Capa 1 — literal.** La palabra tal como se escribió, sin tildes ni
  mayúsculas (función `normalizar`).
- **Capa 2 — raíz.** Los primeros caracteres de la palabra, para que
  *"educativa"* encuentre *"educación"*. Regla fija y documentada en el código
  (función `raiz`): 8+ letras → 7 caracteres; 6-7 letras → 5; menos de 6 → la
  palabra completa. (La misma regla está en `arbol.py`, para resaltar las palabras clave.)
- **Capa 3 — sinónimos.** El archivo `data/sinonimos.csv` traduce palabras de
  uso corriente ("colegio", "beca") a los términos que sí usa el documento
  ("infraestructura educativa", "financiación estudiantil"). Es una tabla
  editable a mano, sin lógica difusa: una palabra de la izquierda, una lista
  de términos de la derecha separados por `;`.

El **orden de los resultados** sale de un score declarado, no aprendido (función
`buscar_estrategias`). Se busca en palabras clave, nombre de la línea estratégica y nombre del
tema; las descripciones de eje y tema sólo se muestran (las palabras clave del tema no se usan ni se muestran)
(sumarlas solo añadía ruido). Por cada término que coincide se suma: peso del campo
(`PESO_CAMPO`: clave 4, nombre 4, tema 3; si el mismo término coincide también en otro campo
de la misma línea, cada campo adicional suma `OTROS_CAMPOS` = la mitad de su peso) × multiplicador de origen (×2 los términos
que llegan a la herramienta, ×1 los que agrega el diccionario de sinónimos) ×
especificidad (ln(total ÷ líneas estratégicas donde aparece el término): un término frecuente
como «infraestructura», en 26 de 122 líneas estratégicas, vale poco). Un término que aparece
en menos de 3 líneas estratégicas cuenta como si apareciera en 3 (`MIN_ESTRATEGIAS_ESPECIFICIDAD`),
para que una sola palabra rara no domine; no resuelve los homónimos (ver sección 8).

El modelo **no puntúa ni ordena**: sólo elige los términos de búsqueda; a partir
de ahí el orden lo calcula la función. Por eso términos distintos pueden dar
rankings distintos para la misma pregunta.

Las **categorías** (claves `cercanas`, `relacionadas`, `descripcion`) son: *Más cercanas*
(≥ 85 % del mejor score y como máximo 3, `MAX_CERCANAS`; las que sobran pasan a *Relacionadas*;
desempate: más términos distintos coincidentes y, al final, el código),
*Relacionadas* (≥ 30 %, hasta 10 más las que sobraron, `MAX_RELACIONADAS`) y *En la descripción* (sin puntaje:
líneas estratégicas sin coincidencia propia cuyo tema menciona el término en su descripción —la del
eje no cuenta: marcaría todas sus líneas estratégicas—,
buscando sólo con los términos «escrito» —los del usuario o el modelo—, porque los
sinónimos genéricos del diccionario la inundarían). Lo que queda por debajo del 30 % no se
muestra (`n_omitidas`). Las constantes están al inicio de `buscador.py`.

Una **consulta muy amplia** (`muy_amplia`: 3 o más líneas llegan al umbral de «Más cercanas» y
son de al menos 2 temas distintos; si son del mismo tema, p. ej. un acueducto, se muestran sin
preguntar) trae `sugerencias`: palabras clave del PND, tal cual, que contienen los términos que
coincidieron y dicen algo más (`_sugerencias`). El prompt de `motor.py` obliga a buscar aunque
llegue una sola palabra, y `texto_busqueda` avisa que da muchos resultados y pregunta de qué
tipo con esas sugerencias.

Las **reglas** (`data/reglas.csv`, columnas `aplica_a`, `palabras_disparadoras`,
`nota`) restringen grupos de líneas estratégicas: si la pregunta no menciona ninguna palabra
disparadora (se compara por raíz y sólo con los términos que llegaron a la búsqueda,
no con los del diccionario), el grupo no se muestra y la interfaz lo avisa en «Notas».
Hoy: el eje 7 (reconstrucción tras el sismo) sólo se sugiere si se habla de un
desastre. Si todo lo que coincidió pertenece a un grupo restringido, se muestra igual.
`validar_reglas()` corre al arrancar y falla con un mensaje claro si el archivo apunta
a algo que no existe.

`buscar_estrategias` devuelve `resultados` (las «más cercanas», máximo 3, con evidencia; lo que ve
el modelo, junto con `n_cercanas`, `muy_amplia`, `sugerencias` y, si no hay cercanas,
`en_descripcion`) y, sólo para la interfaz, `niveles`, `coincidencias`, `avisos_reglas` y
`n_omitidas` (`motor.SOLO_INTERFAZ` las quita antes de llamar al modelo). El árbol marca
todas en azul con su insignia, deja preseleccionada «Más cercanas» con su ficha
abierta, resalta sus palabras clave que coincidieron (con la misma regla de raíz del
buscador), esconde las descripciones de eje y tema tras un botón «i» y trae botones para ver
una categoría a la vez (o todo). Ya no tiene «Exacta», «Plegar todo» ni «Desplegar todo»: la
búsqueda exacta se hace entre comillas.

Cada resultado trae la evidencia completa (qué término, en qué campo, por cuál
capa), y eso es lo que la interfaz muestra en «Coincidencia directa» (la palabra clave se
muestra tal como está escrita en el documento).

**Por qué importa esta separación:** todo lo que decide *qué líneas estratégicas
aparecen* es determinista, está en `buscador.py`, se puede probar sin llamar a
ningún API y no cambia entre una ejecución y otra. Lo único no determinista es la
*elección de los términos* por parte del modelo (con los mismos términos, el resultado
siempre es el mismo; con otras palabras, puede cambiar). Si algún día se audita por qué el
orientador sugirió algo, la respuesta siempre está en `buscador.py`, nunca en el modelo.

## 5. Archivos del repo

| Archivo | Qué contiene |
|---|---|
| `app.py` | Interfaz Streamlit: las dos secciones, el plegado del chat, el historial de conversación, los términos buscados con los sinónimos aplicados, el expander "Notas" (sinónimos, reglas, totales y cómo se ordena, generado desde las constantes de `buscador.py`) y los tooltips de ayuda (CSS, sin JavaScript). |
| `arbol.py` | Genera el visor del árbol como **HTML/CSS/JS autocontenido** (se incrusta con `st.iframe`, o con `st.components.v1.html` en versiones antiguas de Streamlit). Es portable tal cual a cualquier hosting estático, incluido GitHub Pages. |
| `buscador.py` | **El corazón del proyecto.** Carga y valida el Excel de estructura, carga el diccionario de sinónimos, y expone `buscar_estrategias`, `listar_vocabulario` y `detalle_estrategia`. Todo documentado en docstrings largos a propósito. |
| `proyectos.py` | Proyectos y megaproyectos regionales (Anexo 4): carga `data/Proyectos_Megaproyectos_Regionales.xlsx`, quita las filas repetidas tal cual en el PDF y filtra por departamento/región y sector con las columnas «(filtro)», que traen varios valores separados por «; ». Sin modelo ni búsqueda por palabras. |
| `herramientas/digitalizar_anexo4.py` | Lee las dos tablas del PDF del Anexo 4 con `pdfplumber` y escribe el libro (hojas «Proyectos» y «Notas»). Normaliza sólo las dos columnas de filtro; el resto es el texto del PDF. |
| `motor.py` | Las herramientas que ve Claude, el *system prompt* con el catálogo, el ciclo de conversación (`responder`), el texto de la respuesta (`texto_busqueda`, `texto_ficha`) y el candado contra líneas ajenas (`lineas_ajenas`). Modelo: `claude-haiku-4-5`. |
| `data/Estructura_PND_Palabras_claves.xlsx` | La fuente de verdad, versión final. Tres hojas por nombre: `VF_Ejes` (descripción), `VF_Temas` (descripción) y `VF_Estructura` (línea estratégica, una sola lista de 1 a 10 palabras clave, código anterior). El contenido proviene del anexo técnico del PDF «Audiencias Públicas PPI 2027-2030», tomado como versión oficial. Las otras hojas del libro se ignoran. `buscador.cargar_estructura()` las valida y las une en una fila por línea estratégica; `cargar_tablas()` devuelve las tres tablas con llaves por código (para el tablero y los indicadores). Si cambia la estructura, se reemplaza este archivo y se reinicia la app. |
| `data/sinonimos.csv` | El diccionario de la capa 3. Columnas: `palabra`, `terminos_documento` (separados por `;`), `nota`. ~110 filas ya verificadas contra el Excel (cada término de destino existe de verdad en el documento). |
| `requirements.txt` | `streamlit`, `anthropic`, `pandas`, `openpyxl`. |
| `.streamlit/config.toml` | Tema visual (colores, tipografía). |
| `.streamlit/secrets.toml.ejemplo` | Plantilla. El real (`secrets.toml`) **nunca** se commitea — en Streamlit Cloud se configura desde Settings → Secrets de la app. |
| `README.md` | Documentación orientada a correr y mantener la app (cómo instalar, cómo funciona la búsqueda en corto, qué hacer cuando cambie la estructura o falte un sinónimo). Este archivo (`DOCUMENTACION_TECNICA.md`) es el complemento orientado a quien va a **editar el diseño o portar la app**, no solo mantenerla. |

Hay además una carpeta hermana `analisis_iniciativas/` (fuera de este repo,
en `Chatbot/analisis_iniciativas/`) con el análisis de la segunda fuente —la
matriz de iniciativas e indicadores— y su homologación con este árbol. No es
parte de la app; es el insumo que explica, en `informe.html`, por qué ciertas
líneas estratégicas no tienen iniciativas enlazadas todavía y por qué una idea puede
encajar en más de un eje. Quien vaya a enriquecer el orientador con
iniciativas/indicadores debe partir de ahí.

## 6. Reglas de diseño que no se deben romper al editar

1. **El modelo puede ver el catálogo, pero no escribe resultados.** Las líneas
   estratégicas que se muestran salen siempre del resultado de la herramienta, escritas por
   código; y un texto del modelo que nombre una línea que ninguna herramienta devolvió se
   descarta (`lineas_ajenas`). Si se cambia la redacción de la respuesta, hay que conservar
   estas dos garantías.
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
- De `analisis_iniciativas/homologacion_estrategias.csv`: 36 líneas estratégicas con
  homologación "débil" y 15 sin correspondencia, pendientes de revisión
  humana antes de usarse para enriquecer el árbol con iniciativas reales.
- Decidir entre las 3 opciones de la sección 3 (Streamlit / GitHub Pages sin
  LLM / híbrido) — es una decisión de producto, no técnica.

### Nota sobre la estructura final (2026-11-11)

- Los **códigos no son estables** entre la versión anterior y esta: 14 líneas estratégicas nuevas reutilizan códigos
  que eran de otra y 24 se renumeraron. Lo que se enlace a la estructura (indicadores, iniciativas) debe
  usar los códigos nuevos; `codigo_anterior` solo sirve para migrar una vez.
- **Homónimos:** el buscador es literal, así que «escuela» encuentra 1.2.1 por su palabra clave
  «Escuela Superior de Administración Pública (ESAP)». El tope de especificidad no lo corrige; lo
  resolvería una lista de exclusiones editable (término + línea estratégica) o un ajuste de contenido.
- **Vacío de contenido:** fuera del eje 7 ninguna línea estratégica trae «infraestructura educativa», así que
  «colegio» empata varias líneas estratégicas de educación por la palabra `educacion`.
- `sinonimos.csv`: 25 de 139 destinos no coinciden hoy de forma literal; 4 filas quedaron sin ningún
  destino que exista (`credito educativo`, `luz`, `electricidad`, `sgp`).

## Identidad visual (cartilla de las audiencias públicas)

La página sigue la cartilla del PDF «Audiencias Públicas PPI 2027-2030»: texto gris `#585758`,
azul marino `#1B3E6C`/`#103760`, azules de apoyo `#347399`, `#468BC2` y `#63AADE`, fondo `#F7F7F7`
y tarjetas `#EEECEB`. Títulos en Poppins y cuerpo en Nunito Sans (Google Fonts); barra superior de
cuatro tonos; secciones numeradas («01.», «02.»); recuadro «PILAS» en azul marino; frases con las
palabras clave resaltadas en azul (`.rz` en `app.py`); ejes como barras azul marino y filtros en
forma de píldora. El vocabulario de la interfaz es **«línea estratégica»** (antes «estrategia»);
internamente los nombres de funciones y tablas (`buscar_estrategias`, `estrategia_id`) no cambian.
Las marcas del árbol son azules (antes amarillas) y no hay un color por eje: los ejes usan tonos de la
misma familia azul (`COLOR_EJE` en `arbol.py`).


## Pruebas con proyectos reales del portafolio

Con 30 nombres sorteados de la hoja `BD_DNP_` del portafolio de proyectos (semilla fija), y una
línea esperada por criterio de quien probó (a revisar por quien conoce el Plan), el motor sin
modelo y usando sólo las palabras del nombre ubicó bien la primera cercana en 14 de 29 casos (el
caso 30 no dice qué es el proyecto); con términos escritos como los escribiría el modelo con el
catálogo a la vista, 27 de 29. El primer número es un piso (el nombre trae municipios y palabras de
trámite que el modelo ignora); el segundo, un techo optimista (los términos los escribió quien
conocía el catálogo). Un prototipo que sólo lee el texto del PDF con un ranking de texto (BM25)
quedó peor (9 a 10 de 29): el lenguaje del Plan es de política y el de los proyectos es de obra, y
ese puente lo hace el modelo. **Falta medir el modelo real** con la misma lista.


## Proyectos y Megaproyectos regionales (Anexo 4)

Sección 03 de `app.py` (`pintar_proyectos`, un `st.fragment`: cambiar un selector no recarga el árbol ni
el chat). Los datos salen de `data/Proyectos_Megaproyectos_Regionales.xlsx`, generado con
`herramientas/digitalizar_anexo4.py` desde el PDF del anexo (225 páginas, 2.888 filas: 2.495 de
«Megaproyectos y proyectos de alto impacto local» y 393 de «Otras iniciativas y necesidades de encuentros
regionales»). La extracción no encontró filas con celdas vacías ni columnas de más; se comparó a mano contra
la imagen de varias páginas (2, 12, 100, 194, 195, 225) y coincide fila por fila.

Decisiones que conviene conocer:

- **Texto fiel.** No se corrige ortografía ni se completan nombres: el PDF trae errores («Adecuacion de
  obrasde…») y algún nombre cortado («…del corregimiento de»).
- **Filtro de territorio.** El departamento de cada fila se interpreta con una lista de los 32 departamentos y
  Bogotá (`DEPARTAMENTOS`, por patrones sin tildes; los nombres compuestos como «Valle del Cauca» se buscan
  primero para que «Cauca» no coincida dentro). Los textos con varios departamentos («Meta, Casanare,
  Arauca y Vichada») dan una lista; un proyecto sale en cada uno. Los encuentros regionales de la tabla 2
  que no son un departamento quedan con su nombre; «Santanderes» e «Insular» se mapean a sus departamentos.
- **Filtro de sector.** El anexo mezcla dos nomenclaturas (la de la Gerencia de Regiones y la de los
  sectores administrativos) y variantes de mayúsculas. `SECTOR_AGRUPADO` unifica sólo equivalentes
  claros; los sectores con proyectos de varios sectores («A / B») salen en cada uno. El sector original se
  muestra siempre en la lista. La clasificación de origen es la del PDF: por ejemplo «Vivienda» incluye
  algunos acueductos y «Otro» incluye edificios de gobierno.
- **Repetidos.** Cinco filas son idénticas en el PDF; el libro las conserva marcadas y `proyectos.cargar`
  las omite.
- Los proyectos no se enlazan todavía a las líneas estratégicas del Plan: el anexo no trae esa columna.

### Clasificación de prueba de proyectos en las líneas estratégicas (Amazonas y «Amazonia»)

`herramientas/clasificar_proyectos.py` ubica 63 proyectos (los 11 de Amazonas y las 52 iniciativas del encuentro
regional «Amazonia») de tres maneras y escribe `data/Clasificacion_proyectos.xlsx`, que lee `proyectos.clasificacion()`:

- **Orientador:** el flujo real de la aplicación (`motor.responder` con el modelo): el modelo elige los términos y
  `buscador.buscar_estrategias` ubica. Una corrida; necesita `ANTHROPIC_API_KEY`.
- **Solo score:** `buscar_estrategias(terminos_del_texto(nombre))`, con las palabras del nombre y sin el modelo. Es el piso.
- **Claude:** una línea principal y alternativas razonables, leyendo el catálogo; es un criterio a revisar.
- **¿Coinciden?:** Igual, Compatible (la del orientador es una alternativa), Entre sus más cercanas, Mismo tema,
  Mismo eje, Distinta o Sin resultado.

**Resultados con el modelo real (claude-haiku-4-5), 25 de noviembre de 2026.** Se usaron dos conjuntos: T1, los 63
proyectos de arriba contra la clasificación de Claude, y T2, 29 proyectos del portafolio `BD_DNP_` (hoja del archivo
de proyectos) contra una línea esperada por criterio. Como el modelo varía entre corridas, se compararon promedios:

| | T1 igual o compatible (de 63) | T1 tema o mejor | T2 1.ª cercana correcta (de 29) |
|---|---|---|---|
| Solo score (palabras del nombre, sin modelo) | 26 (41 %) | 37 | 14 |
| Versión anterior (modelo con catálogo, sin diccionario) | 39,5 (63 %) | 52 | 26,5 |
| Versión enviada (con diccionario en el prompt) | 43,5 (69 %) | 53,5 | 25,0 |

T1 mejora unos 4 proyectos; T2 queda igual dentro del ruido (cambian 4 o 5 ítems ambiguos, como 7.4.1 frente a 7.4.2).
Lo que sí cambió, y se vio en las corridas: «placa huella» ya no hace que el modelo pregunte qué es (busca y da 5.1.7);
«infraestructura» sola pregunta de qué tipo; y «Gasoducto Aguazul–Yopal» o «Muelle de Puerto Santander» ya no se toman
por un nombre propio sin significado.

**Qué se probó y se descartó** (cada cambio se midió con los términos que había elegido el modelo en 8 corridas
guardadas, sin volver a llamarlo): contar una palabra clave una sola vez aunque coincidan dos términos con ella
ayudaba a 2 proyectos con términos del modelo pero **empeoraba 5 con las palabras del nombre**, y el efecto con el
modelo era de 0,6 proyectos: se quitó. Descartar las palabras de trámite («mejoramiento», «ampliación») de lo que
manda el modelo: sin efecto. 21 filas nuevas de jerga de proyectos en el diccionario: sin efecto. La regla de las
palabras cortas (que «gas natural» no coincida con «base natural») y que una frase del diccionario gane sobre sus
palabras sí se dejaron: no cambian el promedio, pero corrigen fallos reales y no perjudican.

**Dónde sigue fallando:** aeropuertos, muelles y puertos (el Plan no los nombra; el modelo elige 5.1.7 o 5.2.5 por
«conectividad», y la referencia de Claude, 5.1.3, es discutible); términos genéricos que agrega el modelo
(«conectividad», «infraestructura») y sacan del primer lugar a la línea correcta; y proyectos mixtos (vivienda con
vías). El diccionario trae 7 filas sin ningún término que el Plan tenga escrito, que el modelo no ve y que conviene
revisar o borrar: `credito educativo`, `luz`, `electricidad`, `regalias`, `sgp`, `joven` y `predio`; otras 36 tienen
algún término que ya no existe con el libro oficial (`buscador.sinonimos_muertos()` las lista).
