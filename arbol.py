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
                "desc": g_tema["tema_desc"].iloc[0], "kw": g_tema["tema_kw_lista"].iloc[0],
                "estrategias": [{
                    "cod": r["est_n"], "nombre": r["est"], "kw": r["kw_lista"],
                } for _, r in g_tema.iterrows()],
            })
        ejes.append({
            "num": int(eje_n), "nombre": eje_nom, "desc": g_eje["eje_desc"].iloc[0],
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
    font-family:var(--sans);font-size:17px;line-height:1.5;
    -webkit-font-smoothing:antialiased}
  #raiz{padding:4px 2px 56px}

  /* ---------- barra de búsqueda ---------- */
  .barra{position:sticky;top:0;z-index:20;background:var(--papel);
    padding:12px 2px 14px;border-bottom:1px solid var(--regla);
    display:flex;gap:12px;align-items:center;flex-wrap:wrap}
  .campo{position:relative;flex:1 1 280px;min-width:200px}
  .campo svg{position:absolute;left:14px;top:50%;transform:translateY(-50%);
    color:var(--tenue);pointer-events:none}
  input[type=search]{width:100%;font:inherit;font-size:16px;color:var(--tinta);
    padding:11px 14px 11px 41px;border:1px solid var(--regla);border-radius:9px;
    background:#fff;outline:none;transition:border-color .13s,box-shadow .13s}
  input[type=search]:focus{border-color:var(--realce);
    box-shadow:0 0 0 3px rgba(31,79,216,.13)}
  input[type=search]::-webkit-search-cancel-button{cursor:pointer}
  .acciones{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
  .niveles{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-left:6px;
    padding-left:14px;border-left:1px solid var(--regla)}
  .niveles .rot{font-size:14px;color:var(--tenue)}
  button.ctrl{font:inherit;font-size:15px;color:var(--suave);background:#fff;
    border:1px solid var(--regla);border-radius:9px;padding:10px 15px;cursor:pointer;
    transition:background .13s,color .13s,border-color .13s}
  button.ctrl[aria-pressed=true]{background:var(--tinta);color:#fff;border-color:var(--tinta)}
  button.ctrl .n{opacity:.7;font-variant-numeric:tabular-nums}
  button.ctrl:hover{background:#F2F4F7;color:var(--tinta)}
  button.ctrl[aria-pressed=true]:hover{background:var(--tinta);color:#fff}
  button.ctrl:focus-visible,summary:focus-visible,.est:focus-visible,button.info:focus-visible{
    outline:2px solid var(--realce);outline-offset:2px}
  .conteo{font-size:14px;color:var(--tenue);font-variant-numeric:tabular-nums;
    flex-basis:100%}
  .conteo b{color:var(--tinta);font-weight:500}

  /* ---------- eje ---------- */
  details.eje{border-left:3px solid var(--c);margin:26px 0 0;padding-left:18px}
  details.eje>summary{list-style:none;cursor:pointer;display:flex;gap:13px;
    align-items:baseline;padding:6px 0}
  details.eje>summary::-webkit-details-marker{display:none}
  .eje-num{font-family:var(--sans);font-weight:600;font-size:15px;color:var(--c);
    font-variant-numeric:tabular-nums;min-width:16px;letter-spacing:.02em}
  .eje-nom{font-family:var(--serif);font-size:26px;font-weight:600;
    line-height:1.26;letter-spacing:-.008em;flex:1}
  .eje-cnt{font-size:14px;color:var(--tenue);font-variant-numeric:tabular-nums;
    white-space:nowrap}
  details.eje>summary:hover .eje-nom{color:var(--c)}
  .flecha{color:var(--tenue);transition:transform .16s ease;flex-shrink:0;
    margin-top:7px}
  details[open]>summary .flecha{transform:rotate(90deg)}

  /* ---------- tema ---------- */
  details.tema{margin:2px 0 2px 2px}
  details.tema>summary{list-style:none;cursor:pointer;display:flex;gap:11px;
    align-items:baseline;padding:10px 0;border-top:1px solid var(--regla)}
  details.tema>summary::-webkit-details-marker{display:none}
  .tema-num{font-weight:600;font-size:15px;color:var(--c);
    font-variant-numeric:tabular-nums;min-width:34px}
  .tema-nom{font-size:18px;font-weight:500;flex:1;line-height:1.4}
  .tema-cnt{font-size:14px;color:var(--tenue);font-variant-numeric:tabular-nums}
  details.tema>summary:hover .tema-nom{color:var(--c)}

  /* La descripción de eje y tema está escondida: se abre con el botón «i». */
  button.info{font:inherit;font-size:13px;font-weight:600;font-style:italic;font-family:var(--serif);
    width:24px;height:24px;border-radius:50%;border:1px solid #C9CED6;background:#fff;
    color:var(--tenue);cursor:pointer;padding:0;flex-shrink:0;align-self:center;
    transition:background .13s,color .13s,border-color .13s}
  button.info:hover,button.info[aria-expanded=true]{background:var(--c,var(--tinta));
    color:#fff;border-color:var(--c,var(--tinta))}
  .info-bloque{display:none}
  .info-bloque.abierta{display:block}
  .eje-desc{margin:4px 0 14px;font-size:16px;line-height:1.6;color:var(--suave);max-width:78ch}
  .tema-desc{margin:6px 0 8px;padding-left:46px;font-size:15.5px;line-height:1.55;
    color:var(--suave);max-width:82ch}
  .tema-kw{margin:0 0 10px;padding-left:46px;display:flex;flex-wrap:wrap;gap:6px}
  .tema-kw .chip{font-size:13.5px;background:#fff;box-shadow:inset 0 0 0 1px var(--regla);color:var(--suave)}

  /* ---------- estrategia ---------- */
  .lista{margin:0 0 8px;padding:0 0 0 46px}
  .est{display:flex;gap:12px;align-items:baseline;padding:9px 12px 9px 10px;
    cursor:pointer;border-radius:7px;position:relative;
    transition:background .11s}
  .est:hover{background:#F2F4F7}
  .est[aria-expanded=true]{background:#F2F4F7}
  .est-cod{font-size:14px;color:var(--tenue);font-variant-numeric:tabular-nums;
    min-width:44px;padding-top:3px;letter-spacing:.01em}
  .est[aria-expanded=true] .est-cod,.est:hover .est-cod{color:var(--c)}
  .est-nom{font-family:var(--serif);font-size:19px;line-height:1.38;flex:1}
  .est.senalada{background:var(--marca);box-shadow:inset 3px 0 0 var(--marca-borde)}
  .est.senalada:hover{background:#FBEFC5}
  .insignia{font-size:13px;font-weight:600;border-radius:5px;padding:2px 9px;
    white-space:nowrap;align-self:center;letter-spacing:.01em}
  .insignia.cercanas{background:#166534;color:#fff}
  .insignia.relacionadas{background:#DBEAFE;color:#1E40AF;box-shadow:inset 0 0 0 1px #A9C4F5}
  .insignia.descripcion{background:#fff;color:#5B6472;box-shadow:inset 0 0 0 1px #D2D7DE}

  /* ---------- ficha: sólo palabras clave ---------- */
  .ficha{display:none;margin:4px 0 16px 56px;padding:18px 22px 14px;
    background:#fff;border:1px solid #DDE1E8;border-radius:10px;
    border-left:3px solid var(--c);box-shadow:0 1px 2px rgba(21,24,29,.04)}
  .ficha.abierta{display:block}
  .rotulo{font-size:13px;color:var(--suave);font-weight:500;margin:0 0 8px}
  .chips{display:flex;flex-wrap:wrap;gap:6px;margin:0 0 6px}
  .chip{font-size:14.5px;background:#F2F4F7;color:#333A45;border-radius:6px;
    padding:4px 11px;line-height:1.45}
  .chip.coincide{background:var(--marca);color:#6B4F00;
    box-shadow:inset 0 0 0 1px var(--marca-borde)}
  mark{background:var(--marca);color:inherit;padding:0 1px;border-radius:2px;
    box-shadow:0 1px 0 var(--marca-borde)}
  .oculto{display:none !important}
  .nada{padding:32px 4px;color:var(--suave);font-size:16px;max-width:54ch}
  .nada b{color:var(--tinta);font-weight:500}
  @media (prefers-reduced-motion:reduce){*{transition:none !important}}
  @media (max-width:640px){
    .eje-nom{font-size:22px}.est-nom{font-size:18px}.tema-nom{font-size:17px}
    .eje-cnt{display:none}.eje-nom,.tema-nom,.est-nom{min-width:0}
    .barra{position:static}.niveles{margin-left:0;padding-left:0;border-left:0}
    button.ctrl{padding:8px 12px;font-size:14px}
    .lista{padding-left:6px}.ficha{margin-left:8px}.tema-desc,.tema-kw{padding-left:4px}
  }
</style></head><body><div id="raiz">

<div class="barra">
  <div class="campo">
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor"
      stroke-width="2.2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/>
      <path d="M20 20l-4.3-4.3"/></svg>
    <input type="search" id="q" placeholder="Buscar en el árbol: agua, vivienda, docente…"
      autocomplete="off" aria-label="Buscar en el árbol">
  </div>
  <button class="ctrl" id="exacta" type="button" aria-pressed="false"
    title="Coincidencia exacta: sólo palabras completas («deporte» no encuentra «deportivo»). También puedes escribir la búsqueda entre comillas.">Exacta</button>
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
const NIVELES = __NIVELES__;   /* {cercanas:[...], relacionadas:[...], descripcion:[...]} */
const COINC = __COINCIDENCIAS__;   /* {código: [{termino, campo}]} */
const TERMINOS = __TERMINOS__;

const ORDEN_NIVELES = ["cercanas", "relacionadas", "descripcion"];
const NIVEL = {};
ORDEN_NIVELES.forEach(k => (NIVELES[k] || []).forEach(c => { NIVEL[c] = k; }));
const ROTULO = {cercanas: "Más cercanas", relacionadas: "Relacionadas", descripcion: "En la descripción"};
const HAY_NIVELES = Object.keys(NIVEL).length > 0;

const sinTildes = s => s.normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").toLowerCase();
const esc = s => String(s==null?"":s).replace(/[&<>"]/g,
  c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));

/* Resalta en el texto los términos que vienen del chat. */
const esLetra = c => c !== undefined && /[a-z0-9]/.test(c);

/* `terminos` se resaltan donde aparezcan; `exactos`, sólo como palabra completa. */
function resaltar(texto, terminos, exactos = []){
  let html = esc(texto);
  if(!terminos.length && !exactos.length) return html;
  const plano = sinTildes(html);
  const tramos = [];
  for(const t of terminos){
    const tn = sinTildes(t);
    if(tn.length < 3) continue;
    let i = plano.indexOf(tn);
    while(i !== -1){ tramos.push([i, i+tn.length]); i = plano.indexOf(tn, i+tn.length); }
  }
  for(const t of exactos){
    const tn = sinTildes(t);
    if(tn.length < 3) continue;
    let i = plano.indexOf(tn);
    while(i !== -1){
      if(!esLetra(plano[i-1]) && !esLetra(plano[i+tn.length])) tramos.push([i, i+tn.length]);
      i = plano.indexOf(tn, i+1);
    }
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

const FLECHA = '<svg class="flecha" width="13" height="13" viewBox="0 0 24 24" '
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
  const chips = '<p class="rotulo">Palabras clave</p><div class="chips">' + e.kw.map(k =>
        '<span class="chip' + (chipCoincide(k, terminosKw) ? ' coincide' : '') + '" data-raw="'
        + esc(k) + '">' + esc(k) + '</span>').join("") + '</div>';
  return '<div class="ficha" id="f-' + esc(e.cod) + '" style="--c:' + color + '">' + chips + '</div>';
}

const BOTON_INFO = '<button class="info" type="button" aria-expanded="false" '
  + 'aria-label="Ver la descripción" title="Descripción">i</button>';

function dibujar(){
  const partes = [];
  for(const eje of EJES){
    const temas = eje.temas.map(t => {
      const ests = t.estrategias.map(e => {
        const nivel = NIVEL[e.cod];
        return '<div class="est' + (nivel?' senalada '+nivel:'') + '" role="button" tabindex="0"'
          + ' aria-expanded="false" data-cod="' + esc(e.cod) + '"'
          + ' data-buscar="' + esc(sinTildes(e.cod+" "+e.nombre+" "+t.nombre+" "+e.kw.join(" "))) + '">'
          + '<span class="est-cod">' + esc(e.cod) + '</span>'
          + '<span class="est-nom" data-raw="' + esc(e.nombre) + '">' + resaltar(e.nombre, TERMINOS) + '</span>'
          + (nivel ? '<span class="insignia ' + nivel + '">' + ROTULO[nivel] + '</span>' : "")
          + '</div>' + ficha(e, eje.color);
      }).join("");
      const n = t.estrategias.length;
      return '<details class="tema"><summary>' + FLECHA
        + '<span class="tema-num">' + esc(t.num) + '</span>'
        + '<span class="tema-nom" data-raw="' + esc(t.nombre) + '">' + resaltar(t.nombre, TERMINOS) + '</span>'
        + (t.desc ? BOTON_INFO : '')
        + '<span class="tema-cnt">' + n + '</span></summary>'
        + (t.desc ? '<div class="info-bloque"><p class="tema-desc">' + esc(t.desc) + '</p>'
          + (t.kw.length ? '<div class="tema-kw">' + t.kw.map(k => '<span class="chip">' + esc(k) + '</span>').join("") + '</div>' : '')
          + '</div>' : '')
        + '<div class="lista">' + ests + '</div></details>';
    }).join("");
    partes.push('<details class="eje" style="--c:' + eje.color + '"><summary>' + FLECHA
      + '<span class="eje-num">' + eje.num + '</span>'
      + '<span class="eje-nom" data-raw="' + esc(eje.nombre) + '">' + resaltar(eje.nombre, TERMINOS) + '</span>'
      + (eje.desc ? BOTON_INFO : '')
      + '<span class="eje-cnt">' + eje.n_est + ' estrategias</span></summary>'
      + (eje.desc ? '<div class="info-bloque"><p class="eje-desc">' + esc(eje.desc) + '</p></div>' : '')
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
  const inf = ev.target.closest("button.info");
  if(inf){
    ev.preventDefault();                       /* no pliega ni despliega el eje o tema */
    const d = inf.closest("details");
    const abierta = d.querySelector(":scope > .info-bloque").classList.toggle("abierta");
    inf.setAttribute("aria-expanded", String(abierta));
    if(abierta) d.open = true;
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

let ultimaBusqueda = "|false";
let EXACTA = false;

/* Lo escrito en el buscador: entre comillas o con «Exacta» activado, sólo palabras completas. */
function consulta(){
  let q = caja.value.trim(), exacto = EXACTA;
  const m = q.match(/^["“](.+)["”]$/);
  if(m){ q = m[1].trim(); exacto = true; }
  return {t: sinTildes(q), exacto, texto: q};
}

function contiene(texto, t, exacto){
  let i = texto.indexOf(t);
  while(i !== -1){
    if(!exacto || (!esLetra(texto[i-1]) && !esLetra(texto[i+t.length]))) return true;
    i = texto.indexOf(t, i+1);
  }
  return false;
}
const AUTO = [];   /* fichas que abrió la búsqueda, para cerrarlas al cambiarla */

function cerrarAuto(){
  AUTO.splice(0).forEach(e => {
    document.getElementById("f-" + e.dataset.cod).classList.remove("abierta");
    e.setAttribute("aria-expanded","false");
  });
}

/* Con pocas coincidencias se abre la ficha, para ver las palabras clave resaltadas. */
function abrirAuto(){
  document.querySelectorAll(".est:not(.oculto)").forEach(e => {
    const f = document.getElementById("f-" + e.dataset.cod);
    if(!f.classList.contains("abierta")){
      f.classList.add("abierta"); e.setAttribute("aria-expanded","true"); AUTO.push(e);
    }
  });
}

function filtrar(){
  const q = consulta(), t = q.t, exacto = q.exacto;
  const ests = document.querySelectorAll(".est");
  let visibles = 0;

  ests.forEach(e => {
    const pasa = (!t || contiene(e.dataset.buscar, t, exacto)) && pasaNivel(e);
    e.classList.toggle("oculto", !pasa);
    if(!pasa) document.getElementById("f-" + e.dataset.cod).classList.remove("abierta");
    document.getElementById("f-" + e.dataset.cod).classList.toggle("oculto", !pasa);
    if(pasa) visibles++;
  });

  /* Lo escrito en el buscador se resalta en nombres, temas, ejes, palabras clave y
     descripciones; al borrarlo quedan sólo las marcas del chat. */
  const clave = t + "|" + exacto;
  if(clave !== ultimaBusqueda){
    ultimaBusqueda = clave;
    cerrarAuto();
    document.querySelectorAll("[data-raw]").forEach(el => {
      const base = el.classList.contains("chip") ? [] : TERMINOS;
      el.innerHTML = !t ? resaltar(el.dataset.raw, base)
        : exacto ? resaltar(el.dataset.raw, base, [t])
        : resaltar(el.dataset.raw, base.concat([t]));
    });
  }
  if(t && visibles <= 8) abrirAuto();

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
      + (t ? " contienen «" + esc(q.texto) + "»" + (exacto ? " como palabra exacta" : "") : "")
      + (t && FILTRO.size ? " en " : "") + (!t ? " en " : "") + cuales;
    nada.classList.toggle("oculto", visibles > 0);
    if(visibles === 0){
      nada.innerHTML = t
        ? "Ninguna estrategia contiene <b>«" + esc(q.texto)
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
document.getElementById("exacta").addEventListener("click", ev => {
  EXACTA = !EXACTA;
  ev.currentTarget.setAttribute("aria-pressed", String(EXACTA));
  filtrar();
});
let temporizador;
caja.addEventListener("input", () => {
  clearTimeout(temporizador);
  temporizador = setTimeout(filtrar, 110);
});

document.getElementById("abrir").onclick = () =>
  document.querySelectorAll("details").forEach(d => d.open = true);
document.getElementById("cerrar").onclick = () => {
  document.querySelectorAll("details").forEach(d => d.open = false);
  document.querySelectorAll(".info-bloque.abierta").forEach(b => b.classList.remove("abierta"));
  document.querySelectorAll("button.info").forEach(b => b.setAttribute("aria-expanded", "false"));
  document.querySelectorAll(".ficha").forEach(f => f.classList.remove("abierta"));
  document.querySelectorAll(".est").forEach(e => e.setAttribute("aria-expanded","false"));
  /* Al quedar corto el árbol, vuelve al inicio para que no quede espacio en blanco. */
  window.scrollTo(0, 0);
};

dibujar();

/* Botones «Mostrar»: Más cercanas, Relacionadas, En la descripción y Todos. Se ve un solo
   grupo a la vez; pulsar de nuevo el grupo activo, o «Todos», vuelve a mostrar todo. Tras
   una respuesta del chat arranca en «Más cercanas». */
if(HAY_NIVELES){
  const grupo = document.createElement("div");
  grupo.className = "niveles";
  grupo.innerHTML = '<span class="rot">Mostrar:</span>'
    + ORDEN_NIVELES.map(c => {
      const n = document.querySelectorAll(".est." + c).length;
      return n ? '<button class="ctrl" type="button" data-n="' + c + '" aria-pressed="false">'
        + ROTULO[c] + ' <span class="n">(' + n + ')</span></button>' : "";
    }).join("")
    + '<button class="ctrl" type="button" data-n="" aria-pressed="false">Todos</button>';
  document.querySelector(".acciones").appendChild(grupo);
  const pintarEstado = () => grupo.querySelectorAll("button").forEach(b =>
    b.setAttribute("aria-pressed",
      String(b.dataset.n ? FILTRO.has(b.dataset.n) : FILTRO.size === 0)));
  if((NIVELES.cercanas || []).length) FILTRO.add("cercanas");
  pintarEstado();
  grupo.addEventListener("click", ev => {
    const b = ev.target.closest("button[data-n]");
    if(!b) return;
    const n = b.dataset.n;
    if(!n || FILTRO.has(n)) FILTRO.clear();
    else { FILTRO.clear(); FILTRO.add(n); }
    pintarEstado();
    filtrar();
    const destino = document.querySelector(FILTRO.size ? ".est.senalada:not(.oculto)" : ".est.cercanas");
    if(destino) destino.scrollIntoView({block:"center", behavior:"auto"});
  });
}
filtrar();

/* Lleva a la primera de «Más cercanas»: primero asegura que el árbol esté a la vista en la página y luego
   centra la estrategia dentro del árbol. */
function irALaPrimera(suave){
  const primera = document.querySelector(".est.cercanas");
  if(!primera) return;
  const quieto = !suave || matchMedia("(prefers-reduced-motion:reduce)").matches;
  try{ if(window.frameElement) window.frameElement.scrollIntoView({block:"nearest", behavior:"auto"}); }
  catch(e){}
  primera.scrollIntoView({block:"center", behavior: quieto ? "auto" : "smooth"});
}

/* Si el chat señaló estrategias, se abren sus ramas, se abre la ficha de las «Más cercanas»
   (todas por igual) y se baja a la primera en el orden del árbol. */
if(HAY_NIVELES){
  document.querySelectorAll(".est.senalada").forEach(e => {
    let p = e.parentElement;
    while(p){ if(p.tagName === "DETAILS") p.open = true; p = p.parentElement; }
  });
  document.querySelectorAll(".est.cercanas").forEach(e => alternar(e));
  setTimeout(() => irALaPrimera(true), 160);
  /* otra vez cuando ya cargaron las fuentes y el diseño se asentó */
  setTimeout(() => irALaPrimera(false), 900);
}
</script></body></html>
"""


def render(df, niveles=None, terminos=None, coincidencias=None) -> str:
    """Devuelve el HTML del árbol.

    niveles:       {'cercanas': [...], 'relacionadas': [...], 'descripcion': [...]} con los
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
