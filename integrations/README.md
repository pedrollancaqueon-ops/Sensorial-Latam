# Integraciones

## Google Sheets — escritura de evaluaciones
- Una fila por evaluación
- Columnas: fecha/hora, evaluador, vuelo/ruta, producto, proveedor, apariencia, aroma, sabor, textura, temperatura, comentarios, URL foto, código IA, ¿IA corregida?
- Acceso: service account o Apps Script (pendiente definir)

## Google Drive — imágenes
- Subida de la foto del plato al enviar el formulario
- Consulta de imágenes del catálogo para el matching

## BigQuery
- ✅ No requerido en el flujo principal — el catálogo vive en el Sheet índice
- Puede usarse en el futuro para filtrar por vuelo si se agrega ese campo

## Gemini Vision API (Google AI)
- Modelo: `gemini-1.5-pro` con soporte de visión
- Credencial: misma service account del proyecto Panel Carguio APV — sin key nueva
- Uso: recibe foto del plato + imágenes de referencia del catálogo → devuelve el código que mejor calza
- Fallback: si Gemini no identifica con confianza → campo vacío para que el usuario escriba el código manual
