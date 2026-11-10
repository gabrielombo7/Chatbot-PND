"""
arbol.py — Visor del árbol del PND como un componente HTML autocontenido.
=========================================================================
Genera una sola página HTML (estilos y script incluidos) que Streamlit
incrusta con st.components.v1.html. Toda la interacción —plegar, desplegar,
buscar, abrir la ficha— ocurre en el navegador, así que no recarga la
aplicación ni pierde el estado del chat.

Concepto visual: el árbol se lee como el índice de un documento de planeación.
La numeración (1.2.3) es la columna vertebral, alineada a la izquierda con
cifras tabulares; el nombre cuelga a su derecha. Cada eje tiene un color que
aparece sólo como una línea vertical, no como un bloque relleno.
"""

import json

# Un color por eje. Tonos desaturados, distinguibles entre sí y legibles
# sobre papel claro. El número corresponde a la columna "Número del eje".
COLOR_EJE = {
    1: "#0F766E",  # Colombia desde las regiones
    2: "#6D28D9",  # Talento, Conocimiento e Innovación
    3: "#A1541C",  # Patriotismo Constitucional
    4: "#B01A5B",  # Milagro Social
    5: "#1D4ED8",  # Milagro económico
    6: "#475569",  # Transformación del Estado
    7: "#15803D",  # Reconstrucción, Transformación y Resiliencia
}
COLOR_POR_DEFECTO = "#5B6472"


def construir_datos(df) -> list:
    """Convierte el DataFrame plano en la jerarquía eje -> tema -> estrategia."""
    ejes = []
    for (eje_n, eje_nom), g_eje in df.groupby(["eje_n", "eje"], sort=True):
        temas = []
        for (tema_n, tema_nom), g_tema in g_eje.groupby(["tema_n", "tema"], sort=True):
            temas.append({
                "num": str(tema_n), "nombre": tema_nom,
                "estrategias": [{
                    "cod": r["est_n"], "nombre": r["est"],
                    "desc": r["desc"], "kw": r["kw_lista"],
                } for _, r in g_tema.iterrows()],
            })
        ejes.append({
            "num": int(eje_n), "nombre": eje_nom,
            "color": COLOR_EJE.get(int(eje_n), COLOR_POR_DEFECTO),
            "temas": temas,
            "n_est": int(len(g_eje)),
        })
    return ejes


PLANTILLA = """<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root{
    --papel:#FBFBFC; --tinta:#15181D; --suave:#5B6472; --tenue:#8A929E;
    --regla:#E3E6EB; --realce:#1F4FD8; --marca:#FEF6D9; --marca-borde:#E8C84A;
    --serif:"Source Serif 4",Georgia,serif;
    --sans:"IBM Plex Sans",system-ui,-apple-system,sans-serif;
  }
  *{box-sizing:border-box}
  html,body{margin:0;padding:0;background:var(--papel);color:var(--tinta);
    font-family:var(--sans);font-size:15px;line-height:1.5;
    -webkit-font-smoothing:antialiased}
  #raiz{padding:4px 2px 48px}

  /* ---------- barra de búsqueda ---------- */
  .barra{position:sticky;top:0;z-index:20;background:var(--papel);
    padding:10px 2px 12px;border-bottom:1px solid var(--regla);
    display:flex;gap:10px;align-items:center;flex-wrap:wrap}
  .campo{position:relative;flex:1 1 260px;min-width:200px}
  .campo svg{position:absolute;left:11px;top:50%;transform:translateY(-50%);
    color:var(--tenue);pointer-events:none}
  input[type=search]{width:100%;font:inherit;color:var(--tinta);
    padding:9px 12px 9px 34px;border:1px solid var(--regla);border-radius:7px;
    background:#fff;outline:none;transition:border-color .13s,box-shadow .13s}
  input[type=search]:focus{border-color:var(--realce);
    box-shadow:0 0 0 3px rgba(31,79,216,.13)}
  input[type=search]::-webkit-search-cancel-button{cursor:pointer}
  .acciones{display:flex;gap:6px;align-items:center;flex-wrap:wrap}
  .niveles{display:flex;gap:6px;align-items:center;margin-left:6px;padding-left:12px;
    border-left:1px solid var(--regla)}
  .niveles .rot{font-size:12.5px;color:var(--tenue)}
  button.ctrl[aria-pressed=true]{background:var(--tinta);color:#fff;border-color:var(--tinta)}
  button.ctrl .n{opacity:.7;font-variant-numeric:tabular-nums}
  button.vertodo.coincide{background:var(--marca);border-radius:5px;padding:4px 8px;
    box-shadow:inset 0 0 0 1px var(--marca-borde);color:#6B4F00}  button.ctrl{font:inherit;font-size:13.5px;color:var(--suave);background:#fff;
    border:1px solid var(--regla);border-radius:7px;padding:8px 13px;cursor:pointer;
    transition:background .13s,color .13s,border-color .13s}
  button.ctrl:hover{background:#F2F4F7;color:var(--tinta)}
  button.ctrl:focus-visible,summary:focus-visible,.est:focus-visible{
    outline:2px solid var(--realce);outline-offset:2px}
  .conteo{font-size:13px;color:var(--tenue);font-variant-numeric:tabular-nums;
    flex-basis:100%}
  .conteo b{color:var(--tinta);font-weight:500}

  /* ---------- eje ---------- */
  details.eje{border-left:3px solid var(--c);margin:18px 0 0;padding-left:15px}
  details.eje>summary{list-style:none;cursor:pointer;display:flex;gap:11px;
    align-items:baseline;padding:5px 0}
  details.eje>summary::-webkit-details-marker{display:none}
  .eje-num{font-family:var(--sans);font-weight:600;font-size:12.5px;color:var(--c);
    font-variant-numeric:tabular-nums;min-width:14px;letter-spacing:.02em}
  .eje-nom{font-family:var(--serif);font-size:20.5px;font-weight:600;
    line-height:1.26;letter-spacing:-.008em;flex:1}
  .eje-cnt{font-size:12.5px;color:var(--tenue);font-variant-numeric:tabular-nums;
    white-space:nowrap}
  details.eje>summary:hover .eje-nom{color:var(--c)}
  .flecha{color:var(--tenue);transition:transform .16s ease;flex-shrink:0;
    margin-top:5px}
  details[open]>summary .flecha{transform:rotate(90deg)}

  /* ---------- tema ---------- */
  details.tema{margin:2px 0 2px 2px}
  details.tema>summary{list-style:none;cursor:pointer;display:flex;gap:9px;
    align-items:baseline;padding:6px 0;border-top:1px solid var(--regla)}
  details.tema>summary::-webkit-details-marker{display:none}
  .tema-num{font-weight:600;font-size:13px;color:var(--c);
    font-variant-numeric:tabular-nums;min-width:30px}
  .tema-nom{font-size:14.5px;font-weight:500;flex:1;line-height:1.4}
  .tema-cnt{font-size:12px;color:var(--tenue);font-variant-numeric:tabular-nums}
  details.tema>summary:hover .tema-nom{color:var(--c)}

  /* ---------- estrategia ---------- */
  .lista{margin:0 0 6px;padding:0 0 0 39px}
  .est{display:flex;gap:11px;align-items:baseline;padding:7px 10px 7px 9px;
    cursor:pointer;border-radius:5px;position:relative;
    transition:background .11s}
  .est:hover{background:#F2F4F7}
  .est[aria-expanded=true]{background:#F2F4F7}
  .est-cod{font-size:12.5px;color:var(--tenue);font-variant-numeric:tabular-nums;
    min-width:36px;padding-top:2px;letter-spacing:.01em}
  .est[aria-expanded=true] .est-cod,.est:hover .est-cod{color:var(--c)}
  .est-nom{font-family:var(--serif);font-size:16px;line-height:1.38;flex:1}
  .est.senalada{background:var(--marca);box-shadow:inset 3px 0 0 var(--marca-borde)}
  .est.senalada:hover{background:#FBEFC5}
  .insignia{font-size:11px;font-weight:600;border-radius:4px;padding:1.5px 7px;
    white-space:nowrap;align-self:center;letter-spacing:.01em}
  .insignia.t1{background:#166534;color:#fff}
  .insignia.t2{background:#DBEAFE;color:#1E40AF;box-shadow:inset 0 0 0 1px #A9C4F5}
  .insignia.t3{background:#fff;color:#5B6472;box-shadow:inset 0 0 0 1px #D2D7DE}

  /* ---------- ficha ---------- */
  .ficha{display:none;margin:2px 0 14px 48px;padding:15px 20px 16px;
    background:#fff;border:1px solid #DDE1E8;border-radius:8px;
    border-left:3px solid var(--c);box-shadow:0 1px 2px rgba(21,24,29,.04)}
  .ficha.abierta{display:block}
  .ficha h4{margin:0 0 3px;font-family:var(--serif);font-size:16.5px;
    font-weight:600;line-height:1.32}
  .ficha .ruta{font-size:12.5px;color:var(--tenue);margin:0 0 11px;
    line-height:1.45}
  /* La descripción queda recogida hasta que se pide con el botón. */
  button.vertodo{font:inherit;font-size:13px;font-weight:500;color:var(--realce);
    background:none;border:0;padding:4px 0;margin:2px 0 0;cursor:pointer;
    display:inline-flex;align-items:center;gap:6px}
  button.vertodo:hover{text-decoration:underline}
  button.vertodo .flecha{margin-top:0;color:currentColor}
  button.vertodo[aria-expanded=true] .flecha{transform:rotate(90deg)}
  .desc{display:none;margin:8px 0 2px;padding-top:10px;border-top:1px solid var(--regla)}
  .desc.abierta{display:block}
  .desc p{margin:0;font-family:var(--serif);font-size:15px;line-height:1.62;
    max-width:68ch;color:#262B33;white-space:pre-line}
  .ficha .vacio{font-family:var(--sans);font-size:13.5px;color:var(--tenue);
    font-style:normal;background:#F7F8FA;padding:9px 12px;border-radius:6px;
    max-width:68ch}
  .rotulo{font-size:12px;color:var(--suave);font-weight:500;margin:0 0 6px}
  .chips{display:flex;flex-wrap:wrap;gap:5px;margin:0 0 6px}
  .chip{font-size:12.5px;background:#F2F4F7;color:#333A45;border-radius:5px;
    padding:3px 9px;line-height:1.45}
  .chip.coincide{background:var(--marca);color:#6B4F00;
    box-shadow:inset 0 0 0 1px var(--marca-borde)}
  mark{background:var(--marca);color:inherit;padding:0 1px;border-radius:2px;
    box-shadow:0 1px 0 var(--marca-borde)}
  .oculto{display:none !important}
  .nada{padding:30px 4px;color:var(--suave);font-size:14.5px;max-width:52ch}
  .nada b{color:var(--tinta);font-weight:500}
  @media (prefers-reduced-motion:reduce){*{transition:none !important}}
</style></head><body><div id="raiz">

<div class="barra">
  <div class="campo">
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/>
      <path d="M20 20l-4.3-4.3"/></svg>
    <input type="search" id="q" placeholder="Buscar en el árbol: agua, vivienda, docente…"
      autocomplete="off" aria-label="Buscar en el árbol">
  </div>
  <div class="acciones">
    <button class="ctrl" id="abrir">Desplegar todo</button>
    <button class="ctrl" id="cerrar">Plegar todo</button>
  </div>
  <div class="conteo" id="conteo"></div>
</div>

<div id="arbol"></div>
<div class="nada oculto" id="nada"></div>
</div>

<script>
const EJES = __DATOS__;
const NIVELES = __NIVELES__;   /* {top1:[...], top2:[...], top3:[...]} */
const COINC = __COINCIDENCIAS__;   /* {código: [{termino, campo}]} */
const TERMINOS = __TERMINOS__;

const NIVEL = {};
const CLASE = {top1: "t1", top2: "t2", top3: "t3"};
for(const k in CLASE) (NIVELES[k] || []).forEach(c => { NIVEL[c] = CLASE[k]; });
const ROTULO = {t1: "Top 1", t2: "Top 2", t3: "Top 3"};
const HAY_NIVELES = Object.keys(NIVEL).length > 0;

const sinTildes = s => s.normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").toLowerCase();
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

/* Resalta en el texto los términos que vienen del chat. */
function resaltar(texto, terminos){
  let html = esc(texto);
  if(!terminos.length) return html;
  const plano = sinTildes(html);
  const tramos = [];
  for(const t of terminos){
    const tn = sinTildes(t);
    if(tn.length < 3) continue;
    let i = plano.indexOf(tn);
    while(i !== -1){ tramos.push([i, i+tn.length]); i = plano.indexOf(tn, i+tn.length); }
  }
  if(!tramos.length) return html;
  tramos.sort((a,b)=>a[0]-b[0]);
  const unidos = [];
  for(const t of tramos){
    const u = unidos[unidos.length-1];
    if(u && t[0] <= u[1]) u[1] = Math.max(u[1], t[1]); else unidos.push([...t]);
  }
  let salida = "", pos = 0;
  for(const [a,b] of unidos){
    salida += html.slice(pos,a) + "<mark>" + html.slice(a,b) + "</mark>";
    pos = b;
  }
  return salida + html.slice(pos);
}

const FLECHA = '<svg class="flecha" width="11" height="11" viewBox="0 0 24 24" '
  + 'fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" '
  + 'stroke-linejoin="round"><path d="M9 5l7 7-7 7"/></svg>';

/* Misma regla de raíz que buscador.py: 8+ letras -> 6; 6-7 -> 5; menos, completa. */
const raiz = w => w.length >= 8 ? w.slice(0,6) : (w.length >= 6 ? w.slice(0,5) : w);
const palabras = s => sinTildes(s).replace(/[^a-z0-9ñ ]/g," ").split(/\\s+/).filter(w => w.length >= 4);
function chipCoincide(k, terminosKw){
  const kn = sinTildes(k), kr = new Set(palabras(k).map(raiz));
  return terminosKw.some(t => {
    if(kn.includes(sinTildes(t))) return true;
    const tr = palabras(t).map(raiz);
    return tr.length > 0 && tr.every(r => kr.has(r));
  });
}

function ficha(e, color){
  const co = COINC[e.cod] || [];
  const terminosKw = co.filter(c => c.campo === "palabras clave").map(c => c.termino);
  const enDesc = co.some(c => c.campo === "descripción");
  const extra = enDesc ? " · aquí coincide" : "";
  const desc = e.desc
    ? '<button class="vertodo' + (enDesc ? ' coincide' : '') + '" type="button" aria-expanded="false"'
      + ' data-extra="' + extra + '">' + FLECHA
      + '<span class="vertodo-txt">Ver descripción' + extra + '</span></button>'
      + '<div class="desc"><p data-raw="' + esc(e.desc) + '">' + resaltar(e.desc, TERMINOS) + '</p></div>'
    : '<p class="vacio">Esta estrategia aparece en el árbol sin descripción propia.'
      + (e.kw.length ? ' Las palabras clave son la única referencia disponible.' : '') + '</p>';
  const chips = e.kw.length
    ? '<p class="rotulo">Palabras clave</p><div class="chips">' + e.kw.map(k =>
        '<span class="chip' + (chipCoincide(k, terminosKw) ? ' coincide' : '') + '" data-raw="'
        + esc(k) + '">' + esc(k) + '</span>').join("") + '</div>'
    : "";
  return '<div class="ficha" id="f-' + esc(e.cod) + '" style="--c:' + color + '">'
    + chips + desc + '</div>';
}

function dibujar(){
  const partes = [];
  for(const eje of EJES){
    const temas = eje.temas.map(t => {
      const ests = t.estrategias.map(e => {
        const nivel = NIVEL[e.cod];
        return '<div class="est' + (nivel?' senalada '+nivel:'') + '" role="button" tabindex="0"'
          + ' aria-expanded="false" data-cod="' + esc(e.cod) + '"'
          + ' data-buscar="' + esc(sinTildes(e.cod+" "+e.nombre+" "+t.nombre+" "+e.kw.join(" ")+" "+(e.desc||""))) + '">'
          + '<span class="est-cod">' + esc(e.cod) + '</span>'
          + '<span class="est-nom" data-raw="' + esc(e.nombre) + '">' + resaltar(e.nombre, TERMINOS) + '</span>'
          + (nivel ? '<span class="insignia ' + nivel + '">' + ROTULO[nivel] + '</span>' : "")
          + '</div>' + ficha(e, eje.color);
      }).join("");
      const n = t.estrategias.length;
      return '<details class="tema"><summary>' + FLECHA
        + '<span class="tema-num">' + esc(t.num) + '</span>'
        + '<span class="tema-nom" data-raw="' + esc(t.nombre) + '">' + resaltar(t.nombre, TERMINOS) + '</span>'
        + '<span class="tema-cnt">' + n + '</span></summary>'
        + '<div class="lista">' + ests + '</div></details>';
    }).join("");
    partes.push('<details class="eje" style="--c:' + eje.color + '"><summary>' + FLECHA
      + '<span class="eje-num">' + eje.num + '</span>'
      + '<span class="eje-nom" data-raw="' + esc(eje.nombre) + '">' + resaltar(eje.nombre, TERMINOS) + '</span>'
      + '<span class="eje-cnt">' + eje.n_est + ' estrategias</span></summary>'
      + temas + '</details>');
  }
  document.getElementById("arbol").innerHTML = partes.join("");
}

/* Abrir y cerrar la ficha de una estrategia. */
function alternar(el){
  const f = document.getElementById("f-" + el.dataset.cod);
  const abierta = f.classList.toggle("abierta");
  el.setAttribute("aria-expanded", abierta ? "true" : "false");
}
document.getElementById("arbol").addEventListener("click", ev => {
  const ver = ev.target.closest("button.vertodo");
  if(ver){
    const abierta = ver.nextElementSibling.classList.toggle("abierta");
    ver.setAttribute("aria-expanded", abierta ? "true" : "false");
    ver.querySelector(".vertodo-txt").textContent =
      (abierta ? "Ocultar descripción" : "Ver descripción") + (ver.dataset.extra || "");
    return;
  }
  const el = ev.target.closest(".est");
  if(el) alternar(el);
});
document.getElementById("arbol").addEventListener("keydown", ev => {
  if(ev.key !== "Enter" && ev.key !== " ") return;
  const el = ev.target.closest(".est");
  if(el){ ev.preventDefault(); alternar(el); }
});

/* Búsqueda literal dentro del árbol, en el navegador. */
const caja = document.getElementById("q");
const conteo = document.getElementById("conteo");
const nada = document.getElementById("nada");

const FILTRO = new Set();   /* niveles elegidos con los botones; vacío = todo el árbol */
const pasaNivel = e => FILTRO.size === 0 || [...FILTRO].some(n => e.classList.contains(n));

let ultimaBusqueda = "";
const AUTO = [];   /* fichas/descripciones que abrió la búsqueda, para cerrarlas al cambiarla */

function cerrarAuto(){
  AUTO.splice(0).forEach(([tipo, e]) => {
    const f = document.getElementById("f-" + e.dataset.cod);
    if(tipo === "f"){ f.classList.remove("abierta"); e.setAttribute("aria-expanded","false"); }
    else {
      const b = f.querySelector(".vertodo");
      f.querySelector(".desc").classList.remove("abierta");
      b.setAttribute("aria-expanded","false");
      b.querySelector(".vertodo-txt").textContent = "Ver descripción" + (b.dataset.extra || "");
    }
  });
}

/* Con pocas coincidencias se abre la ficha (palabras clave resaltadas) y, si la palabra
   está en la descripción, también la descripción. */
function abrirAuto(t){
  document.querySelectorAll(".est:not(.oculto)").forEach(e => {
    const f = document.getElementById("f-" + e.dataset.cod);
    if(!f.classList.contains("abierta")){
      f.classList.add("abierta"); e.setAttribute("aria-expanded","true"); AUTO.push(["f", e]);
    }
    const d = f.querySelector(".desc"), b = f.querySelector(".vertodo");
    if(d && b && !d.classList.contains("abierta")
       && sinTildes(d.querySelector("p").dataset.raw || "").includes(t)){
      d.classList.add("abierta"); b.setAttribute("aria-expanded","true");
      b.querySelector(".vertodo-txt").textContent = "Ocultar descripción" + (b.dataset.extra || "");
      AUTO.push(["d", e]);
    }
  });
}

function filtrar(){
  const t = sinTildes(caja.value.trim());
  const ests = document.querySelectorAll(".est");
  let visibles = 0;

  ests.forEach(e => {
    const pasa = (!t || e.dataset.buscar.includes(t)) && pasaNivel(e);
    e.classList.toggle("oculto", !pasa);
    if(!pasa) document.getElementById("f-" + e.dataset.cod).classList.remove("abierta");
    document.getElementById("f-" + e.dataset.cod).classList.toggle("oculto", !pasa);
    if(pasa) visibles++;
  });

  /* Lo escrito en el buscador se resalta en nombres, temas, ejes, palabras clave y
     descripciones; al borrarlo quedan sólo las marcas del chat. */
  if(t !== ultimaBusqueda){
    ultimaBusqueda = t;
    cerrarAuto();
    document.querySelectorAll("[data-raw]").forEach(el => {
      const base = el.classList.contains("chip") ? [] : TERMINOS;
      el.innerHTML = resaltar(el.dataset.raw, t ? base.concat([t]) : base);
    });
  }
  if(t && visibles <= 8) abrirAuto(t);

  document.querySelectorAll("details.tema").forEach(d => {
    const hay = d.querySelectorAll(".est:not(.oculto)").length;
    d.classList.toggle("oculto", hay === 0);
    if(t || FILTRO.size) d.open = hay > 0;
  });
  document.querySelectorAll("details.eje").forEach(d => {
    const hay = d.querySelectorAll(".est:not(.oculto)").length;
    d.classList.toggle("oculto", hay === 0);
    if(t || FILTRO.size) d.open = hay > 0;
  });

  if(t || FILTRO.size){
    const cuales = [...FILTRO].sort().map(n => ROTULO[n]).join(" + ");
    conteo.innerHTML = "<b>" + visibles + "</b> de " + ests.length + " estrategias"
      + (t ? " contienen «" + esc(caja.value.trim()) + "»" : "")
      + (t && FILTRO.size ? " en " : "") + (!t ? " en " : "") + cuales;
    nada.classList.toggle("oculto", visibles > 0);
    if(visibles === 0){
      nada.innerHTML = t
        ? "Ninguna estrategia contiene <b>«" + esc(caja.value.trim())
          + "»</b>" + (FILTRO.size ? " en " + cuales : "") + ". Esta búsqueda es literal: "
          + "encuentra la palabra sólo si está escrita igual en el árbol. Para una búsqueda "
          + "que traduzca al vocabulario del documento, usa el chat."
        : "Ninguna estrategia en " + cuales + ".";
    }
  } else {
    conteo.innerHTML = "<b>" + ests.length + "</b> estrategias en "
      + document.querySelectorAll("details.eje").length + " ejes";
    nada.classList.add("oculto");
  }
}
let temporizador;
caja.addEventListener("input", () => {
  clearTimeout(temporizador);
  temporizador = setTimeout(filtrar, 110);
});

document.getElementById("abrir").onclick = () =>
  document.querySelectorAll("details").forEach(d => d.open = true);
document.getElementById("cerrar").onclick = () => {
  document.querySelectorAll("details").forEach(d => d.open = false);
  document.querySelectorAll(".ficha").forEach(f => f.classList.remove("abierta"));
  document.querySelectorAll(".est").forEach(e => e.setAttribute("aria-expanded","false"));
  /* Al quedar corto el árbol, vuelve al inicio para que no quede espacio en blanco. */
  window.scrollTo(0, 0);
};

dibujar();

/* Botones «Mostrar»: Todos, Top 1, Top 2, Top 3. Los niveles se pueden combinar y
   «Todos» quita el filtro. Aparecen al lado de Plegar/Desplegar. */
if(HAY_NIVELES){
  const grupo = document.createElement("div");
  grupo.className = "niveles";
  grupo.innerHTML = '<span class="rot">Mostrar:</span>'
    + '<button class="ctrl" type="button" data-n="" aria-pressed="true">Todos</button>'
    + ["t1","t2","t3"].map(c => {
      const n = document.querySelectorAll(".est." + c).length;
      return n ? '<button class="ctrl" type="button" data-n="' + c + '" aria-pressed="false">'
        + ROTULO[c] + ' <span class="n">(' + n + ')</span></button>' : "";
    }).join("");
  document.querySelector(".acciones").appendChild(grupo);
  const pintarEstado = () => grupo.querySelectorAll("button").forEach(b =>
    b.setAttribute("aria-pressed",
      String(b.dataset.n ? FILTRO.has(b.dataset.n) : FILTRO.size === 0)));
  grupo.addEventListener("click", ev => {
    const b = ev.target.closest("button[data-n]");
    if(!b) return;
    const n = b.dataset.n;
    if(!n) FILTRO.clear();
    else if(FILTRO.has(n)) FILTRO.delete(n); else FILTRO.add(n);
    pintarEstado();
    filtrar();
    const destino = document.querySelector(FILTRO.size ? ".est.senalada:not(.oculto)" : ".est.t1");
    if(destino) destino.scrollIntoView({block:"center", behavior:"auto"});
  });
}
filtrar();

/* Lleva al Top 1: primero asegura que el árbol esté a la vista en la página y luego
   centra la estrategia dentro del árbol. */
function irAlTop1(suave){
  const primera = document.querySelector(".est.t1");
  if(!primera) return;
  const quieto = !suave || matchMedia("(prefers-reduced-motion:reduce)").matches;
  try{ if(window.frameElement) window.frameElement.scrollIntoView({block:"nearest", behavior:"auto"}); }
  catch(e){}
  primera.scrollIntoView({block:"center", behavior: quieto ? "auto" : "smooth"});
}

/* Si el chat señaló estrategias, se abren sus ramas, se abre la ficha de las Top 1
   (todas por igual) y se baja a la primera en el orden del árbol. */
if(HAY_NIVELES){
  document.querySelectorAll(".est.senalada").forEach(e => {
    let p = e.parentElement;
    while(p){ if(p.tagName === "DETAILS") p.open = true; p = p.parentElement; }
  });
  document.querySelectorAll(".est.t1").forEach(e => alternar(e));
  setTimeout(() => irAlTop1(true), 160);
  /* otra vez cuando ya cargaron las fuentes y el diseño se asentó */
  setTimeout(() => irAlTop1(false), 900);
}
</script></body></html>
"""


def render(df, niveles=None, terminos=None, coincidencias=None) -> str:
    """Devuelve el HTML del árbol.

    niveles:       {'top1': [...], 'top2': [...], 'top3': [...]} con los
                   códigos que encontró el chat; se marcan en amarillo con su insignia.
    terminos:      términos a resaltar dentro del texto.
    coincidencias: {código: [{'termino', 'campo'}]}, para resaltar palabras clave.
    """
    datos = construir_datos(df)
    return (PLANTILLA
            .replace("__DATOS__", json.dumps(datos, ensure_ascii=False))
            .replace("__NIVELES__", json.dumps(niveles or {}, ensure_ascii=False))
            .replace("__COINCIDENCIAS__", json.dumps(coincidencias or {}, ensure_ascii=False))
            .replace("__TERMINOS__", json.dumps(sorted(terminos or []), ensure_ascii=False)))
