# App de Evaluación Sensorial de Comidas — Spec para Claude Code

## Objetivo
App web para que personal de LATAM registre evaluaciones sensoriales de comidas (catering a bordo). El flujo arranca con la cámara: el usuario fotografía el plato, la app lo identifica comparándolo contra un catálogo conocido de códigos de servicio (no es reconocimiento abierto de "cualquier comida del mundo"), y recién ahí se abre el formulario de calificación.

## Usuarios
Personal LATAM (catering / calidad), multiusuario, uso interno.

## Flujo completo
1. **Captura:** el usuario abre la cámara desde el navegador y fotografía el plato
2. **Carga:** mientras la foto se envía y se analiza, se muestra un estado de "Analizando plato..." (spinner o animación breve) — esto toma 1–3 segundos, no es instantáneo
3. **Identificación por matching:** la foto se compara contra un set acotado de imágenes de referencia del catálogo (ver sección siguiente) usando un modelo con visión (Claude), que elige cuál código calza mejor
4. **Confirmación:** la app muestra el nombre sugerido (ej. "Pollo al curry con arroz") — el usuario lo confirma o lo corrige manualmente
5. **Calificación:** se abre el formulario sensorial con el producto ya prellenado
6. **Guardado:** todo (foto + identificación + calificación) se escribe en Google Sheets

## Campos del formulario
- Fecha y hora (autocompletado)
- Evaluador (nombre / usuario)
- Vuelo o ruta (opcional)
- Producto / plato evaluado (prellenado por IA, editable)
- Proveedor (ej. FRA, GG MAD, etc.)
- Criterios sensoriales, escala 1–5 con descriptores visuales (no solo número):
  - Apariencia / presentación
  - Aroma
  - Sabor
  - Textura
  - Temperatura de servicio
- Comentarios libres
- Foto del plato (la misma que se usó para identificar — sube a Drive y guarda el link en la fila)

## Catálogo de referencia y matching
Esta es la parte clave de tu idea: no le pides a la IA que adivine entre cualquier comida del mundo, sino que **elija entre las opciones reales de tu catálogo** (códigos de cena, almuerzo, frío, especiales: gluten free, vegetariano, vegetariano sin lácteos, etc.).

**Dónde vive el catálogo:**
- **Google Drive** (carpeta con las imágenes de referencia, una por código) como fuente de verdad
- **Un Google Sheet índice** al estilo de los que ya usas: columnas `Código | Nombre del plato | Tipo de servicio | Restricción | ID imagen en Drive`. Es el mismo patrón Sheets-como-capa-intermedia de tus otros proyectos.

**Por qué no conviene una carpeta local "que lee Claude Code":**
Claude Code solo construye la app en tu computador — esa carpeta no existe cuando la app ya está corriendo en Render. La pregunta real es si el catálogo se consulta en vivo desde Drive o si se "hornea" dentro del código en cada deploy. Conviene Drive en vivo porque tus catálogos cambian (igual que viste con GG MAD cambiando de formato) — si lo horneas, cada código nuevo te obliga a redesplegar la app entera.

**Cómo acotar el catálogo en cada foto (clave para que funcione bien):**
Comparar contra cientos de códigos cada vez sería lento e impreciso. En vez de eso:
1. El backend usa el vuelo/ruta ya ingresado en el formulario para consultar `catering_services.cat_meal_flight` en BigQuery
2. Eso devuelve solo los códigos asignados a ESE vuelo (normalmente entre 5 y 15, incluyendo especiales)
3. El backend busca en el Sheet índice las imágenes de referencia de solo esos códigos
4. Se le manda a Claude la foto capturada + esas pocas imágenes candidatas, pidiéndole que elija cuál calza
5. Vuelve el código + nombre, y se prellena el formulario

**¿Esto es un MCP?**
No. MCP es para cuando un agente conversacional decide dinámicamente qué herramienta usar en medio de una conversación. Acá el flujo es fijo y conocido de antemano: BigQuery → Drive/Sheet → API de Claude → Sheets. Son llamadas directas a APIs encadenadas en el backend, sin necesidad de un agente intermedio — más simple, más rápido y más barato.


**Frontend:** React + Tailwind, mobile-first (se va a usar desde el celular, cámara incluida). Evitar el look "template" — usar colores LATAM, tipografía limpia, transiciones suaves al enviar.

**Cámara:** API nativa del navegador (`getUserMedia`) — funciona en móvil sin instalar nada, pero requiere HTTPS (Render ya lo da gratis).

**Identificación de comida:** la foto capturada, junto con las imágenes candidatas del catálogo (acotadas por vuelo), se mandan en base64 al backend, que llama a la API de Claude pidiéndole que elija cuál código calza. El resultado vuelve al frontend y prellena el campo "Producto evaluado".

**Backend — dos opciones:**
- **Opción A (rápida):** Apps Script Web App que recibe la foto + datos y escribe a Google Sheets — mismo patrón que ya usas en Panel Carguio APV. La llamada a la API de Claude para identificar la comida puede ir en un endpoint Node/Python aparte (Apps Script no es ideal para eso).
- **Opción B (más robusta):** Backend Node o Python único que maneja tanto la identificación con Claude como la escritura a Sheets vía service account.

**Hosting:** Render.com (ya lo usas) o Vercel para el frontend.

## Validaciones
- Campos obligatorios: foto, evaluador, producto confirmado, los 5 criterios sensoriales
- Si la IA no logra identificar el plato con confianza, mostrar el campo vacío para que el usuario lo escriba manual
- Si la llamada a la IA falla o se demora demasiado (timeout, sin conexión), mostrar un mensaje claro y dejar pasar directo al formulario con el campo de producto vacío — nunca dejar al usuario atascado en el loader
- Confirmación visual al enviar (no solo un alert)
- Que se pueda evaluar varios platos seguidos sin recargar la página

## Cómo arrancar con Claude Code
1. Crear una carpeta nueva para el proyecto
2. Abrir terminal ahí y correr `claude`
3. Pegarle este documento completo como primer mensaje, pidiendo que primero arme la pantalla de cámara + captura de foto (sin backend todavía)
4. Luego pedir la integración con la API de Claude para identificar el plato
5. Después conectar el formulario de calificación
6. Al final, conectar todo a Google Sheets

## Pendiente por definir
- ¿Service account propio para Sheets, o reutilizas el flujo de Apps Script que ya tienes funcionando?
- ¿Nombre del Google Sheet / spreadsheet ID donde guardar las respuestas?
- ¿Tienes una API key de Anthropic propia, o usas el acceso vía Codeen/Cosmos Bridge que ya usas para ChatGPT Enterprise/Claude en LATAM?
- Verificar la estructura real del catálogo de códigos (Pedro mencionó que falta confirmar nombres/formato exacto) antes de armar el Sheet índice
- ¿La carpeta de Drive con las imágenes de referencia ya existe, o hay que armarla desde cero?
- ¿Un código de servicio puede tener más de una foto de referencia (ej. distintos ángulos o presentaciones)?
