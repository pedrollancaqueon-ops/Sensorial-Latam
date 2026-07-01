# Backend

Servidor que maneja:
- Llamada a la API de Claude con la foto + imágenes candidatas del catálogo
- Consulta a BigQuery para acotar el catálogo por vuelo
- Consulta al Sheet índice del catálogo para obtener imágenes de referencia
- Escritura de evaluaciones a Google Sheets
- Subida de la foto del plato a Google Drive

## Stack definido
- **Python (FastAPI)** — Opción B (backend único)
- Hosting: Render.com
- Credenciales: service account de Google (Sheets + Drive + BigQuery)

## Decisiones de UX
- Evaluador: campo de texto libre (sin login por ahora)
