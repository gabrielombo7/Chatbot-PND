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
import streamlit.components.v1 as components

import arbol
import buscador as B
import motor

st.set_page_config(page_title="Orientador del PND 2026-2030",
                   page_icon="🧭", layout="wide",
                   initial_sidebar_state="collapsed")

ALTO_ARBOL = 680

# ---------------------------------------------------------------------------
# Estilos de la página (el árbol trae los suyos aparte)
# ---------------------------------------------------------------------------
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
  .stApp{background:#FBFBFC}
  .block-container{padding-top:1.5rem;padding-bottom:1rem;max-width:1500px}
  html,body,[class*="st-"],.stMarkdown{font-family:"IBM Plex Sans",system-ui,sans-serif}
  #MainMenu,footer,header{visibility:hidden}

  .titulo{font-family:"Source Serif 4",Georgia,serif;font-size:27px;font-weight:600;
    letter-spacing:-.012em;color:#15181D;margin:0 0 3px;line-height:1.2}
  .bajada{font-size:14px;color:#5B6472;margin:0;max-width:74ch;line-height:1.5}
  .regla{border:0;border-top:1px solid #E3E6EB;margin:16px 0 10px}

  .rotulo-col{font-size:12.5px;font-weight:600;color:#5B6472;margin:0 0 2px}
  .ayuda-col{font-size:12.5px;color:#8A929E;margin:0 0 10px;line-height:1.45}

  .aviso{font-size:12.5px;color:#6B6252;background:#FDFAF0;border:1px solid #EDE2C4;
    border-radius:7px;padding:9px 12px;line-height:1.5;margin:0 0 12px}

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
st.session_state.setdefault("senaladas", [])
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
        f'estrategias. Orienta la búsqueda; la ubicación definitiva la define el área '
        f'competente.</p>', unsafe_allow_html=True)
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
def pintar_arbol():
    st.markdown('<p class="rotulo-col">Árbol del Plan</p>'
                '<p class="ayuda-col">Haz clic en una estrategia para ver su '
                'descripción y sus palabras clave. El buscador de esta sección es '
                'literal: encuentra la palabra sólo si está escrita igual.</p>',
                unsafe_allow_html=True)
    components.html(
        arbol.render(DF, st.session_state.senaladas, st.session_state.terminos),
        height=ALTO_ARBOL, scrolling=True)


def pintar_chat():
    st.markdown('<p class="rotulo-col">Dónde ubico mi idea</p>'
                '<p class="ayuda-col">Describe el proyecto en tus palabras. '
                'El asistente los traduce al vocabulario del documento, busca por '
                'coincidencia de palabras y muestra dónde encontró cada opción.</p>',
                unsafe_allow_html=True)

    cli = cliente()
    if cli is None:
        st.markdown('<div class="aviso">Falta la llave del API. Ponla en '
                    '<code>.streamlit/secrets.toml</code> como '
                    '<code>ANTHROPIC_API_KEY</code> y recarga. Mientras tanto, el árbol '
                    'y su buscador funcionan sin llave.</div>', unsafe_allow_html=True)
        return

    if not st.session_state.historial:
        st.markdown('<div class="aviso">El asistente no tiene el PND en memoria: '
                    'cada respuesta sale de una búsqueda de palabras sobre el archivo de '
                    'estructura. Si la búsqueda no encuentra nada, lo dice.</div>',
                    unsafe_allow_html=True)
        st.caption("Para probar:")
        for ejemplo in ["Quiero construir un colegio, ¿a qué estrategia me remito?",
                        "¿Dónde van las becas de estudio?",
                        "Acueducto y alcantarillado en un municipio pequeño",
                        "Un programa de empleo para jóvenes rurales"]:
            if st.button(ejemplo, key=f"ej_{hash(ejemplo)}", use_container_width=True):
                st.session_state.pendiente = ejemplo
                st.rerun()

    for i, msg in enumerate(st.session_state.historial):
        if not isinstance(msg.get("content"), str):
            continue
        with st.chat_message(msg["role"], avatar="🧭" if msg["role"] == "assistant" else "🙂"):
            st.markdown(msg["content"])
            if msg["role"] == "assistant" and msg.get("llamadas"):
                with st.expander("Cómo se encontró"):
                    for ll in msg["llamadas"]:
                        res = ll["resultado"]
                        if ll["herramienta"] == "buscar_estrategias":
                            st.markdown("**Términos buscados:** "
                                        + ", ".join(f"`{t}`" for t in res.get("terminos_buscados", [])))
                            dicc = res.get("terminos_del_diccionario") or []
                            if dicc:
                                st.caption("Del diccionario de sinónimos: "
                                           + ", ".join(dicc))
                            st.caption(f"{res.get('n_resultados', 0)} estrategias "
                                       f"contienen alguno de esos términos.")
                            for r in res.get("resultados", []):
                                detalle = "; ".join(
                                    f"«{c['termino']}» en {c['campo']} ({c['tipo']})"
                                    for c in r["coincidencias"])
                                st.markdown(f"**{r['codigo']}** · {r['estrategia']}  \n"
                                            f"<span style='color:#8A929E;font-size:12.5px'>"
                                            f"{detalle}</span>", unsafe_allow_html=True)
                        else:
                            st.markdown(f"**{ll['herramienta']}** · `{ll['argumentos']}`")
                            st.json(res, expanded=False)

    with st.form("preguntar", clear_on_submit=True):
        texto = st.text_input("Tu pregunta", placeholder="Escribe tu pregunta…",
                              label_visibility="collapsed")
        c1, c2 = st.columns([1, 1])
        enviar = c1.form_submit_button("Buscar", use_container_width=True, type="primary")
        limpiar = c2.form_submit_button("Limpiar", use_container_width=True)

    if limpiar:
        st.session_state.historial = []
        st.session_state.senaladas = []
        st.session_state.terminos = []
        st.rerun()

    pregunta = texto if (enviar and texto.strip()) else st.session_state.pop("pendiente", None)
    if not pregunta:
        return

    st.session_state.historial.append({"role": "user", "content": pregunta})
    with st.chat_message("user", avatar="🙂"):
        st.markdown(pregunta)
    with st.chat_message("assistant", avatar="🧭"):
        with st.spinner("Buscando en la estructura…"):
            try:
                txt, llamadas, codigos, terms = motor.responder(cli, st.session_state.historial)
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
    st.session_state.senaladas = codigos
    st.session_state.terminos = terms
    st.rerun()


if st.session_state.chat_abierto:
    col_arbol, col_chat = st.columns([1.5, 1], gap="large")
    with col_arbol:
        pintar_arbol()
    with col_chat:
        pintar_chat()
else:
    pintar_arbol()
