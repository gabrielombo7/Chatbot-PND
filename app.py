"""
app.py — Orientador del PND 2026-2030 (interfaz Streamlit)
===========================================================
Dos secciones en una página:

  Izquierda  Visor del árbol eje → tema → línea estratégica, con búsqueda literal
             propia. Es un componente HTML autocontenido (arbol.py), así que
             plegar y desplegar no recarga la aplicación.
  Derecha    Chat que traduce una pregunta en lenguaje corriente a términos del
             documento y devuelve las líneas estratégicas donde esos términos aparecen.
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
  @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@500;600;700&family=Nunito+Sans:wght@300;400;600;700&display=swap');
  /* Paleta de la cartilla de las audiencias públicas del PPI 2027-2030 (DNP). */
  :root{
    --fondo:#F7F7F7; --tarjeta:#EEECEB; --texto:#585758; --texto-fuerte:#3C3D3E;
    --marino-oscuro:#103760; --marino:#1B3E6C; --tabla:#2C4779;
    --azul-medio:#0F5987; --azul-texto:#347399; --azul-claro:#578CAB;
    --celeste:#63AADE; --celeste-2:#468BC2; --linea:#DCDAD8;
  }
  .stApp{background:var(--fondo)}
  /* barra superior de cuatro tonos, como en la cartilla */
  .stApp::before{content:"";position:fixed;top:0;left:0;right:0;height:5px;z-index:999;
    background:linear-gradient(90deg,var(--marino-oscuro) 0 25%,var(--tabla) 25% 50%,
      var(--celeste-2) 50% 75%,var(--celeste) 75% 100%)}
  .block-container{padding-top:1.7rem;padding-bottom:1rem;max-width:1900px;
    padding-left:1.25rem !important;padding-right:1.25rem !important}
  html,body,[class*="st-"],.stMarkdown{font-family:"Nunito Sans",system-ui,sans-serif}
  /* Los iconos de Streamlit son una fuente de ligaduras: si se les pisa la fuente,
     se ve el nombre del icono (p. ej. «_arrow_right») en vez del dibujo. */
  [data-testid="stIconMaterial"]{font-family:"Material Symbols Rounded" !important}
  #MainMenu,footer,header{visibility:hidden}

  /* encabezado: línea vertical azul + etiqueta, título en Poppins */
  .cab{border-left:3px solid var(--celeste-2);padding-left:10px;margin:0 0 8px;
    font-size:13px;font-weight:600;color:var(--azul-claro);line-height:1.25}
  .stMarkdown p.titulo{font-family:"Poppins",sans-serif;font-size:28px;font-weight:700;
    letter-spacing:-.01em;color:var(--marino);margin:0 0 4px;line-height:1.2}
  .stMarkdown p.bajada{font-size:16.5px;font-weight:300;color:var(--texto);margin:0;max-width:78ch;line-height:1.55}
  /* palabras resaltadas en azul, como en las frases de la cartilla */
  .rz{color:var(--azul-texto);font-weight:700}
  .rz-f{background:var(--azul-claro);color:#fff;font-weight:600;padding:1px 8px;border-radius:4px}
  /* recuadro «PILAS»: franja azul marino con la etiqueta vertical */
  .pilas{display:flex;align-items:center;gap:16px;margin:14px 0 6px;padding:12px 18px;
    background:linear-gradient(100deg,var(--marino-oscuro),var(--marino) 60%,var(--tabla));
    border-radius:10px;color:#fff}
  .pilas-et{font-family:"Poppins",sans-serif;font-weight:700;font-size:13px;letter-spacing:.12em;
    writing-mode:vertical-rl;transform:rotate(180deg);color:#fff;opacity:.95}
  .stMarkdown .pilas p{margin:0;font-size:15.5px;line-height:1.5;color:#fff}
  .stMarkdown .pilas b{color:#fff;font-weight:700}

  /* encabezados de sección numerados: «01.» + título entre dos líneas */
  .sec{display:flex;align-items:baseline;gap:8px;margin:6px 0 8px;padding:6px 0;
    border-top:1px solid var(--marino);border-bottom:1px solid var(--marino)}
  .sec-n{font-family:"Poppins",sans-serif;font-weight:700;font-size:20px;color:#A7B9CB}
  .sec-t{font-family:"Poppins",sans-serif;font-weight:600;font-size:20px;color:var(--marino)}
  .stMarkdown .sec-t,.stMarkdown .sec-n{line-height:1.2}
  .stMarkdown p.ayuda-col{font-size:15px;font-weight:300;color:var(--texto);margin:0 0 10px;line-height:1.55}

  .aviso{font-size:14px;color:var(--marino);background:var(--tarjeta);border:1px solid var(--linea);
    border-radius:10px;padding:10px 14px;line-height:1.5;margin:0 0 12px}

  /* Tooltip de ayuda: sólo CSS, se abre con el cursor o con el foco (también al tocar). */
  .tip{position:relative;display:inline-flex;align-items:center;justify-content:center;
    width:18px;height:18px;margin-left:7px;border:1px solid var(--azul-claro);border-radius:50%;
    color:var(--azul-claro);font:700 11px "Nunito Sans",sans-serif;cursor:help;
    vertical-align:middle;outline:none;align-self:center}
  .tip:hover,.tip:focus{color:#fff;background:var(--marino);border-color:var(--marino)}
  .tip-cuerpo{display:none;position:absolute;top:calc(100% + 8px);left:-10px;z-index:60;
    width:min(340px,78vw);background:var(--marino-oscuro);color:#EAF1F8;
    font:400 13.5px/1.5 "Nunito Sans",sans-serif;padding:11px 14px;border-radius:10px;
    box-shadow:0 8px 24px rgba(16,55,96,.3);text-align:left;cursor:default}
  .tip.der .tip-cuerpo{left:auto;right:-10px}
  .tip:hover .tip-cuerpo,.tip:focus .tip-cuerpo{display:block}
  .tip-cuerpo b{font-weight:700;color:#fff}
  .tip-cuerpo .tp{display:block;margin:0 0 6px}
  .tip-cuerpo .tp:last-child{margin:0}

  div[data-testid="stChatMessage"]{background:transparent;padding:.35rem 0}
  .stMarkdown p,.stMarkdown li{color:var(--texto-fuerte)}
  .stMarkdown code{background:#E3EEF7;color:var(--azul-medio);border-radius:5px;padding:1px 7px;font-size:.9em}
  .stButton>button{font-family:"Nunito Sans",sans-serif;font-size:15px;
    border-radius:10px;border:1px solid var(--linea);background:#fff;color:var(--marino);
    font-weight:600;transition:background .13s,color .13s}
  .stButton>button:hover{background:#EAF1F8;color:var(--marino-oscuro);border-color:var(--azul-claro)}
  div[data-testid="stForm"]{border:0;padding:0}
  .stTextInput input{font-size:15px;border-radius:10px}
  div[data-testid="stExpander"] details{border:1px solid var(--linea);border-radius:10px;
    background:var(--tarjeta)}
  .stCaption,div[data-testid="stCaptionContainer"]{font-size:13.5px;color:var(--texto)}
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
        '<div class="cab">Audiencias públicas<br>PPI 2027-2030</div>'
        '<p class="titulo">Orientador del Plan Nacional de Desarrollo 2026-2030</p>'
        f'<p class="bajada">Dónde se ubicaría una idea en la estructura del Plan: '
        f'<span class="rz">{CAT["n_ejes"]} ejes</span>, <span class="rz">{CAT["n_temas"]} temas</span> '
        f'y <span class="rz">{CAT["n_estrategias"]} líneas estratégicas</span>.</p>'
        '<div class="pilas"><span class="pilas-et">PILAS</span>'
        '<p>Cada resultado es una <b>opción sugerida</b> que te ayuda a identificar las '
        '<b>líneas estratégicas</b> del catálogo de ejes, temas y líneas estratégicas.</p></div>',
        unsafe_allow_html=True)
with enc_der:
    st.write("")
    etiqueta = "Plegar el chat" if st.session_state.chat_abierto else "Abrir el chat"
    if st.button(etiqueta, use_container_width=True, key="alternar"):
        st.session_state.chat_abierto = not st.session_state.chat_abierto
        st.rerun()



# ---------------------------------------------------------------------------
# Secciones
# ---------------------------------------------------------------------------
def tip(cuerpo, lado="izq"):
    return (f'<span class="tip {lado}" tabindex="0"><span aria-hidden="true">i</span>'
            f'<span class="tip-cuerpo" role="tooltip">{cuerpo}</span></span>')


TIP_ARBOL = (
    "<span class=\"tp\">Cuando el chat responde, el árbol marca en azul las líneas estratégicas "
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
    st.markdown('<div class="sec"><span class="sec-n">01.</span><span class="sec-t">Árbol del Plan</span>'
                + tip(TIP_ARBOL) + '</div>'
                '<p class="ayuda-col">Abre un eje o un tema, y haz clic en una línea estratégica para ver '
                'sus <span class="rz">palabras clave</span>. El buscador de esta sección es literal: encuentra la '
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
        notas.append(f"Marcadas {ult['n_resultados']} de las {CAT['n_estrategias']} líneas estratégicas: "
                     f"Más cercanas ({len(niv.get('cercanas', []))}), "
                     f"Relacionadas ({len(niv.get('relacionadas', []))}) y "
                     f"En la descripción ({len(niv.get('descripcion', []))}).")
        if ult.get("n_omitidas"):
            notas.append(f"Otras {ult['n_omitidas']} coinciden muy poco (menos del "
                         f"{round(100 * B.UMBRAL_RELACIONADAS)} % del mejor puntaje) y no se muestran.")
    else:
        notas.append(f"Ninguna de las {CAT['n_estrategias']} líneas estratégicas contiene esos términos.")

    pw = B.PESO_CAMPO
    notas.append(
        "Cómo se ordena: por cada término que coincide se suma el peso del campo "
        f"(palabras clave {pw['palabras clave']}, nombre {pw['nombre de la línea estratégica']}, "
        f"tema {pw['tema']}) × el origen del término "
        "(×2 los de tu pregunta, ×1 los sinónimos) × su especificidad (un término que "
        "aparece en muchas líneas estratégicas vale menos). "
        f"Más cercanas: desde el {round(100 * B.UMBRAL_CERCANAS)} % del mejor puntaje; "
        f"Relacionadas: desde el {round(100 * B.UMBRAL_RELACIONADAS)} %. «En la descripción» "
        "no tiene puntaje: son líneas estratégicas cuyo tema menciona la palabra en su descripción.")

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
    st.markdown('<div class="sec"><span class="sec-n">02.</span><span class="sec-t">Dónde ubico mi idea</span>'
                + tip(TIP_CHAT, "der") + '</div>'
                '<p class="ayuda-col">Escribe tu idea, proyecto o programa con tus propias '
                'palabras y te muestro en qué líneas estratégicas del Plan podría ubicarse.</p>',
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
        for ejemplo in ["Quiero construir un colegio, ¿a qué línea estratégica me remito?",
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
