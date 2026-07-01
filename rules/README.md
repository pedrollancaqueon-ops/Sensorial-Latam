# Reglas de Negocio y Validaciones

## Campos obligatorios
- Foto del plato
- Evaluador
- Producto confirmado (puede ser editado por el usuario)
- Los 5 criterios sensoriales (1–5): apariencia, aroma, sabor, textura, temperatura

## Identificación por IA
- Si Claude devuelve código con baja confianza → mostrar campo vacío (no pre-llenar con sugerencia dudosa)
- Si la llamada a Claude falla o supera el timeout → mostrar mensaje claro + dejar pasar al formulario con producto vacío
- Nunca bloquear al usuario en el loader

## Flujo de error
- Sin conexión → aviso claro, no loader infinito
- Foto de mala calidad → TBD (¿avisar antes de enviar o dejar que Claude intente?)
- Error al guardar en Sheets → mostrar error y permitir reintentar

## Experiencia de evaluación múltiple
- Se puede evaluar varios platos seguidos sin recargar la página
- Al confirmar envío, mostrar confirmación visual (no solo alert de JS)
- Limpiar formulario y volver a la cámara tras envío exitoso

## Registro de correcciones de IA
- Si el usuario edita el plato sugerido por la IA, se registra en una columna separada (ej. `ia_corregida: true/false`)
- Permite medir la precisión del matching en el tiempo

## Pendiente
- ¿Qué umbral de confianza define "identificación válida"? Ver pregunta 16 en docs/preguntas-alineacion.md
- ¿Qué hacer con fotos oscuras o movidas? Ver pregunta 23
