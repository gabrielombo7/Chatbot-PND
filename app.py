"""
app.py — Orientador del PND 2026-2030 (interfaz Streamlit)
===========================================================
Dos secciones en una página:

  Izquierda  Visor del árbol eje → tema → estrategia, con búsqueda literal
             propia. Es un componente HTML autocontenido (arbol.py), así que
             plegar y desplegar no recarga la aplicación.
  Derecha    Chat que traduce una pregunta en lenguaje corriente a términos del
             documento y devuelve las estrategias donde esos términos aparecen.
             Se puede plegar hacia el lado para dejarle todo el ancho al árbol.

Para correrlo:
    pip install -r requirements.txt
    cp .streamlit/secrets.toml.ejemplo .streamlit/secrets.toml   # y pon la llave
    streamlit run app.py
"""

import os

import anthropic
import streamlit as st

try:   # Streamlit está retirando components.v1; ver incrustar()
    import streamlit.components.v1 as components
except Exception:
    components = None

import arbol
import buscador as B
import motor

st.set_page_config(page_title="Orientador del PND 2026-2030",
                   page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")

ALTO_ARBOL = 840
ALTO_CHAT = 640      # alto de la conversación cuando ya es larga (entonces tiene su propio scroll)
MENSAJES_PARA_SCROLL = 4   # con menos mensajes el recuadro se ajusta al contenido

# ---------------------------------------------------------------------------
# Estilos de la página (el árbol trae los suyos aparte)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
  .stApp{background:#FBFBFC}
  .block-container{padding-top:1.5rem;padding-bottom:1rem;max-width:1900px;
    padding-left:1.25rem !important;padding-right:1.25rem !important}
  html,body,[class*="st-"],.stMarkdown{font-family:"IBM Plex Sans",system-ui,sans-serif}
  /* Los iconos de Streamlit son una fuente de ligaduras: si se les pisa la fuente,
     se ve el nombre del icono (p. ej. «_arrow_right») en vez del dibujo. */
  [data-testid="stIconMaterial"]{font-family:"Material Symbols Rounded" !important}
  #MainMenu,footer,header{visibility:hidden}

  .titulo{font-family:"Source Serif 4",Georgia,serif;font-size:27px;font-weight:600;
    letter-spacing:-.012em;color:#15181D;margin:0 0 3px;line-height:1.2}
  .bajada{font-size:14px;color:#5B6472;margin:0;max-width:74ch;line-height:1.5}
  .regla{border:0;border-top:1px solid #E3E6EB;margin:16px 0 10px}

  .rotulo-col{font-size:12.5px;font-weight:600;color:#5B6472;margin:0 0 2px}
  .ayuda-col{font-size:12.5px;color:#8A929E;margin:0 0 10px;line-height:1.45}

  .aviso{font-size:12.5px;color:#6B6252;background:#FDFAF0;border:1px solid #EDE2C4;
    border-radius:7px;padding:9px 12px;line-height:1.5;margin:0 0 12px}

  /* Tooltip de ayuda: sólo CSS, se abre con el cursor o con el foco (también al tocar). */
  .tip{position:relative;display:inline-flex;align-items:center;justify-content:center;
    width:16px;height:16px;margin-left:7px;border:1px solid #C9CED6;border-radius:50%;
    color:#8A929E;font:600 10.5px "IBM Plex Sans",sans-serif;cursor:help;
    vertical-align:middle;outline:none}
  .tip:hover,.tip:focus{color:#15181D;border-color:#8A929E}
  .tip-cuerpo{display:none;position:absolute;top:calc(100% + 8px);left:-10px;z-index:60;
    width:min(340px,78vw);background:#15181D;color:#F2F4F7;
    font:400 12.5px/1.5 "IBM Plex Sans",sans-serif;padding:10px 12px;border-radius:8px;
    box-shadow:0 6px 20px rgba(21,24,29,.28);text-align:left;cursor:default}
  .tip.der .tip-cuerpo{left:auto;right:-10px}
  .tip:hover .tip-cuerpo,.tip:focus .tip-cuerpo{display:block}
  .tip-cuerpo b{font-weight:600;color:#fff}
  .tip-cuerpo .tp{display:block;margin:0 0 6px}
  .tip-cuerpo .tp:last-child{margin:0}

  div[data-testid="stChatMessage"]{background:transparent;padding:.35rem 0}
  .stButton>button{font-family:"IBM Plex Sans",sans-serif;font-size:13.5px;
    border-radius:7px;border:1px solid #E3E6EB;background:#fff;color:#333A45;
    font-weight:500;transition:background .13s,color .13s}
  .stButton>button:hover{background:#F2F4F7;color:#15181D;border-color:#D2D7DE}
  div[data-testid="stForm"]{border:0;padding:0}
  .stTextInput input{font-size:14px;border-radius:7px}
  div[data-testid="stExpander"] details{border:1px solid #E3E6EB;border-radius:7px;
    background:#fff}
  .stCaption,div[data-testid="stCaptionContainer"]{font-size:12.5px;color:#8A929E}
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Datos y cliente
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def cargar():
    B.validar_reglas()
    return B.cargar_estructura(), B.catalogo()


def cliente():
    llave = None
    try:
        llave = st.secrets.get("ANTHROPIC_API_KEY", None)
    except Exception:
        pass
    return anthropic.Anthropic(api_key=llave or os.environ.get("ANTHROPIC_API_KEY", "")) \
        if (llave or os.environ.get("ANTHROPIC_API_KEY")) else None


try:
    DF, CAT = cargar()
except FileNotFoundError:
    st.error("No encontré `data/Estructura_PND_Palabras_claves.xlsx`. "
             "Pon ahí el archivo de estructura y recarga la página.")
    st.stop()
except ValueError as e:
    st.error(str(e))
    st.stop()

st.session_state.setdefault("chat_abierto", True)
st.session_state.setdefault("historial", [])
st.session_state.setdefault("niveles", {})
st.session_state.setdefault("coincidencias", {})
st.session_state.setdefault("terminos", [])

# ---------------------------------------------------------------------------
# Encabezado
# ---------------------------------------------------------------------------
enc_izq, enc_der = st.columns([1, 0.17], gap="small")
with enc_izq:
    st.markdown(
        '<p class="titulo">Orientador del Plan Nacional de Desarrollo 2026-2030</p>'
        f'<p class="bajada">Dónde se ubicaría una idea en la estructura del Plan: '
        f'{CAT["n_ejes"]} ejes, {CAT["n_temas"]} temas y {CAT["n_estrategias"]} '
        f'estrategias. Cada resultado es una opción sugerida.</p>',
        unsafe_allow_html=True)
with enc_der:
    st.write("")
    etiqueta = "Plegar el chat" if st.session_state.chat_abierto else "Abrir el chat"
    if st.button(etiqueta, use_container_width=True, key="alternar"):
        st.session_state.chat_abierto = not st.session_state.chat_abierto
        st.rerun()

st.markdown('<hr class="regla">', unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Secciones
# ---------------------------------------------------------------------------
def tip(cuerpo, lado="izq"):
    return (f'<span class="tip {lado}" tabindex="0"><span aria-hidden="true">i</span>'
            f'<span class="tip-cuerpo" role="tooltip">{cuerpo}</span></span>')


TIP_ARBOL = (
    "<span class=\"tp\">Cuando el chat responde, el árbol marca en amarillo las estrategias "
    "en tres grupos:</span>"
    "<span class=\"tp\"><b>Más cercanas:</b> la mejor, o las mejores si empatan. "
    "<b>Relacionadas:</b> parecidas. <b>En la descripción:</b> su tema menciona la "
    "palabra en su descripción.</span>"
    "<span class=\"tp\">Con «Mostrar» ves un grupo a la vez, o todo el árbol. La «i» de cada "
    "eje y tema muestra su descripción.</span>")

TIP_CHAT = (
    "<span class=\"tp\">Describe el proyecto en tus palabras. El asistente las traduce al vocabulario "
    "del documento, busca por coincidencia de palabras y muestra dónde encontró cada "
    "opción.</span>"
    "<span class=\"tp\">El asistente no tiene el PND en memoria: cada respuesta sale de una búsqueda de "
    "palabras sobre el archivo de estructura. Si la búsqueda no encuentra nada, lo dice.</span>")


def incrustar(html, alto):
    """st.iframe reemplaza a components.html (que Streamlit retira); con versiones
    antiguas, que no lo tienen, se usa la anterior."""
    if hasattr(st, "iframe"):
        st.iframe(html, height=alto)
    else:
        components.html(html, height=alto, scrolling=True)


def pintar_arbol():
    st.markdown('<div class="rotulo-col">Árbol del Plan' + tip(TIP_ARBOL) + '</div>'
                '<p class="ayuda-col">Abre un eje o un tema, y haz clic en una estrategia para ver '
                'sus palabras clave. El buscador de esta sección es literal: encuentra la '
                'palabra sólo si está escrita igual.</p>',
                unsafe_allow_html=True)
    incrustar(arbol.render(DF, st.session_state.niveles, st.session_state.terminos,
                           st.session_state.coincidencias), ALTO_ARBOL)


def pintar_terminos(busquedas):
    """Los términos que se buscaron (sin los que agregó el diccionario)."""
    vistos, buscados = set(), []
    for b in busquedas:
        del_dicc = set(b.get("terminos_del_diccionario") or [])
        for t in b.get("terminos_buscados", []):
            if t not in del_dicc and t not in vistos:
                vistos.add(t)
                buscados.append(t)
    if buscados:
        st.markdown("**Términos buscados:** " + ", ".join(f"`{t}`" for t in buscados))


def pintar_notas(busquedas):
    """Documentación de esta respuesta, en gris: sinónimos, reglas, totales y score."""
    notas = []
    for b in busquedas:
        for a in b.get("sinonimos_aplicados", []):
            notas.append(f"Sinónimos agregados a la búsqueda para «{a['palabra']}»: "
                         + ", ".join(a["terminos"]) + ".")
        notas += [n for n in b.get("avisos_reglas", []) if n not in notas]

    ult = busquedas[-1]
    niv = ult.get("niveles") or {}
    if ult.get("n_resultados"):
        notas.append(f"Marcadas {ult['n_resultados']} de las {CAT['n_estrategias']} estrategias: "
                     f"Más cercanas ({len(niv.get('cercanas', []))}), "
                     f"Relacionadas ({len(niv.get('relacionadas', []))}) y "
                     f"En la descripción ({len(niv.get('descripcion', []))}).")
        if ult.get("n_omitidas"):
            notas.append(f"Otras {ult['n_omitidas']} coinciden muy poco (menos del "
                         f"{round(100 * B.UMBRAL_RELACIONADAS)} % del mejor puntaje) y no se muestran.")
    else:
        notas.append(f"Ninguna de las {CAT['n_estrategias']} estrategias contiene esos términos.")

    pw = B.PESO_CAMPO
    notas.append(
        "Cómo se ordena: por cada término que coincide se suma el peso del campo "
        f"(palabras clave {pw['palabras clave']}, nombre {pw['nombre de la estrategia']}, "
        f"tema {pw['tema']}) × el origen del término "
        "(×2 los de tu pregunta, ×1 los sinónimos) × su especificidad (un término que "
        "aparece en muchas estrategias vale menos). "
        f"Más cercanas: desde el {round(100 * B.UMBRAL_CERCANAS)} % del mejor puntaje; "
        f"Relacionadas: desde el {round(100 * B.UMBRAL_RELACIONADAS)} %. «En la descripción» "
        "no tiene puntaje: son estrategias cuyo tema menciona la palabra en su descripción.")

    with st.expander("Notas"):
        for n in notas:
            st.caption(n)


def pintar_historial():
    for msg in st.session_state.historial:
        if not isinstance(msg.get("content"), str):
            continue
        with st.chat_message(msg["role"], avatar="🧭" if msg["role"] == "assistant" else "📝"):
            busquedas = [ll["resultado"] for ll in msg.get("llamadas", [])
                         if ll["herramienta"] == "buscar_estrategias"
                         and isinstance(ll["resultado"], dict)]
            es_resp = msg["role"] == "assistant" and busquedas
            if es_resp:
                pintar_terminos(busquedas)
            st.markdown(msg["content"])
            if es_resp:
                pintar_notas(busquedas)


def procesar(cli, pregunta):
    st.session_state.historial.append({"role": "user", "content": pregunta})
    with st.chat_message("user", avatar="📝"):
        st.markdown(pregunta)
    with st.chat_message("assistant", avatar="🧭"):
        with st.spinner("Buscando en la estructura…"):
            try:
                txt, llamadas, terms = motor.responder(cli, st.session_state.historial)
            except anthropic.APIStatusError as e:
                st.error(f"El API respondió con un error ({e.status_code}). "
                         "Revisa la llave y el saldo de la cuenta.")
                st.session_state.historial.pop()
                return
            except Exception as e:
                st.error(f"No se pudo completar la consulta: {e}")
                st.session_state.historial.pop()
                return
    st.session_state.historial.append(
        {"role": "assistant", "content": txt, "llamadas": llamadas})
    st.session_state.niveles, st.session_state.coincidencias = motor.marcas_arbol(llamadas)
    st.session_state.terminos = terms
    st.rerun()


def pintar_chat():
    st.markdown('<div class="rotulo-col">Dónde ubico mi idea' + tip(TIP_CHAT, "der") + '</div>'
                '<p class="ayuda-col">Escribe tu idea, proyecto o programa con tus propias '
                'palabras y te muestro en qué estrategias del Plan podría ubicarse.</p>',
                unsafe_allow_html=True)

    cli = cliente()
    if cli is None:
        st.markdown('<div class="aviso">Falta la llave del API. Ponla en '
                    '<code>.streamlit/secrets.toml</code> como '
                    '<code>ANTHROPIC_API_KEY</code> y recarga. Mientras tanto, el árbol '
                    'y su buscador funcionan sin llave.</div>', unsafe_allow_html=True)
        return

    # La conversación va en un recuadro con scroll propio, para que el chat nunca
    # alargue la página y deje el árbol fuera de vista. Se crea aquí, arriba del
    # formulario, y se llena más abajo cuando ya se sabe si hay pregunta.
    zona = st.container()

    if not st.session_state.historial and not st.session_state.get("pendiente"):
        for ejemplo in ["Quiero construir un colegio, ¿a qué estrategia me remito?",
                        "¿Dónde van las becas de estudio?",
                        "Acueducto y alcantarillado en un municipio pequeño",
                        "Un programa de empleo para jóvenes rurales"]:
            if st.button(ejemplo, key=f"ej_{hash(ejemplo)}", use_container_width=True):
                st.session_state.pendiente = ejemplo
                st.rerun()

    with st.form("preguntar", clear_on_submit=True):
        texto = st.text_input("Tu pregunta", placeholder="Escribe tu pregunta…",
                              label_visibility="collapsed")
        c1, c2 = st.columns([1, 1])
        enviar = c1.form_submit_button("Buscar", use_container_width=True, type="primary")
        limpiar = c2.form_submit_button("Limpiar", use_container_width=True)

    if limpiar:
        st.session_state.historial = []
        st.session_state.niveles = {}
        st.session_state.coincidencias = {}
        st.session_state.terminos = []
        st.rerun()

    pregunta = texto if (enviar and texto.strip()) else st.session_state.pop("pendiente", None)
    if not (st.session_state.historial or pregunta):
        return

    with zona:
        largo = len(st.session_state.historial) >= MENSAJES_PARA_SCROLL
        caja = (st.container(height=ALTO_CHAT, border=False) if largo
                else st.container(border=False))
    with caja:
        pintar_historial()
        if pregunta:
            procesar(cli, pregunta)


if st.session_state.chat_abierto:
    col_arbol, col_chat = st.columns([3.7, 1], gap="medium")
    with col_arbol:
        pintar_arbol()
    with col_chat:
        pintar_chat()
else:
    pintar_arbol()
