# Despliegue en Streamlit Community Cloud

- **URL:** https://chatbot-pnd.streamlit.app
- **Plataforma:** Streamlit Community Cloud (se identifica por el dominio `*.streamlit.app`).
- **Redeploy:** la plataforma redeploya automáticamente cada vez que llega un push a la
  rama que la app está siguiendo (normalmente `main` en el panel de Streamlit Cloud). No
  hace falta usar "Reboot app" a mano salvo que la app quede en mal estado (p. ej. tras
  cambiar un secreto).

## Límites a tener en cuenta

- Streamlit reconoce como máximo **5 actualizaciones desde GitHub por minuto**. Pushes muy
  seguidos pueden no sincronizarse todos.
- No hay un número fijo publicado de reboots/redeploys permitidos, pero **rebootear o
  redeployar muchas veces en poco tiempo** (frecuente cuando se depura algo como una
  variable de entorno o un secreto) puede activar el bloqueo por **"fair-use limits"**
  (error 403). La cuenta queda bloqueada hasta que soporte de Streamlit lo revisa
  manualmente — puede tardar días.
- Recursos por app (cifra puede cambiar sin aviso de Streamlit): del orden de 2.7GB RAM,
  2 núcleos, 50GB de almacenamiento compartido.
- Las apps gratuitas se "duermen" tras 7 días sin tráfico y se reactivan solas al abrir la
  URL.

## Buenas prácticas para este repo

1. **Agrupar los ajustes:** reunir varios cambios en un solo commit/push a `main` en vez de
   pushear cada ajuste chiquito por separado.
2. **Probar localmente primero:** correr `streamlit run app.py` antes de pushear, para no
   depender de redeploys sucesivos en producción para depurar.
3. **No usar "Reboot app" repetidamente:** si algo falla tras un push, esperar un par de
   minutos antes de rebootear de nuevo; evitar varios reboots consecutivos en pocos minutos.
4. **Iterar en una rama aparte** cuando se necesiten varios intentos rápidos, y mergear a
   `main` solo cuando el cambio esté listo — así cada push a `main` representa un ajuste
   terminado, no un experimento.
5. **Si la cuenta se bloquea por fair-use:** dejar de pushear/rebootear y seguir el proceso
   de soporte de Streamlit (desde el panel de la app o discuss.streamlit.io) en vez de
   reintentar varias veces, porque los reintentos repetidos agravan el bloqueo.
