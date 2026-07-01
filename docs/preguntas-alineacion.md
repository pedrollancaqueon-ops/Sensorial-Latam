# Preguntas de Alineación — App Evaluación Sensorial LATAM

Antes de construir, necesitamos resolver estas definiciones. Están agrupadas por área.

---

## 1. Backend y arquitectura

1. **¿Node o Python para el backend?**
   El spec menciona ambos en la Opción B. ¿Alguna preferencia? Node encaja mejor con el frontend React (mismo stack), Python es más cómodo si ya lo usas para scripts de BigQuery.

2. **¿Apps Script (Opción A) o backend propio (Opción B)?**
   Apps Script es más rápido de arrancar pero no puede llamar a la API de Claude directamente para el matching de imágenes. Si vas por Opción A, igual necesitas un microservicio aparte para Claude. ¿Vale la pena ese split, o conviene ir directo a la Opción B con un backend único?

3. **¿Dónde corre el backend?**
   ¿Render.com (ya lo usas) o algo diferente? ¿Hay restricciones de dominio o VPN para que el personal LATAM lo acceda?

4. **¿La app necesita autenticación de usuarios?**
   ¿El evaluador ingresa su nombre libre (campo de texto), o hay un login con cuenta LATAM / Google? Si es solo campo de texto, ¿hay riesgo de que alguien falsee el evaluador?

---

## 2. Integración con Google

5. **Service account o Apps Script para escribir a Sheets?**
   El spec lo deja abierto. Si ya tienes una service account para otro proyecto, reutilizarla es lo más rápido. Si no, Apps Script evita crear credenciales nuevas pero requiere el split de backend mencionado arriba.

6. **¿Cuál es el Google Sheet / Spreadsheet ID donde se guardan las respuestas?**
   ¿Existe ya, o hay que crearlo? ¿Cómo se llaman las columnas / en qué hoja se escribe?

7. **¿El Sheet índice del catálogo ya existe?**
   Estructura esperada: `Código | Nombre del plato | Tipo de servicio | Restricción | ID imagen en Drive`. ¿Está armado o hay que definirlo con Pedro?

8. **¿La carpeta de Drive con imágenes de referencia ya existe?**
   Si no existe, ¿quién la arma y con qué criterio de nombres? (ej. `SERV_001.jpg`, `GF_LUNCH_MAD.jpg`).

9. **¿Un código de servicio puede tener más de una foto de referencia?**
   Si sí, ¿las mandamos todas a Claude o solo una? Mandarlo todo aumenta la precisión pero también el costo y la latencia.

---

## 3. BigQuery y catálogo

10. **¿Qué proyecto / dataset / tabla en BigQuery tiene los códigos por vuelo?**
    El spec menciona `catering_services.cat_meal_flight`. ¿Es el nombre real o un ejemplo? Necesitamos el project ID, dataset y tabla exactos.

11. **¿Con qué credencial se conecta al backend a BigQuery?**
    ¿La misma service account que Sheets, o una diferente? ¿El entorno de Render puede tener esa key como variable de entorno?

12. **¿Qué devuelve `cat_meal_flight` para un vuelo dado?**
    ¿Solo el código de servicio, o también el nombre del plato? Necesitamos saber qué columnas vienen para armar la query y el join con el Sheet índice.

13. **¿Qué pasa si el vuelo/ruta no se ha ingresado todavía?**
    En el flujo, el usuario fotografía primero y el vuelo es opcional. ¿Cómo acotar el catálogo si no hay vuelo? ¿Se manda el catálogo completo (puede ser lento) o se fuerza a ingresar el vuelo antes de tomar la foto?

---

## 4. API de Claude / identificación

14. **¿Qué API key de Anthropic se usa?**
    ¿Key propia de LATAM, la del acceso vía Codeen/Cosmos Bridge, o una personal? Esto afecta límites de rate, costo y quién administra el acceso.

15. **¿Qué modelo de Claude para el matching visual?**
    `claude-opus-4-8` es el más preciso pero el más caro. `claude-sonnet-4-6` (el actual en este CLI) es un buen balance. ¿Hay restricción de costo por evaluación?

16. **¿Qué nivel de confianza se considera "identificación válida"?**
    Si Claude devuelve el código con baja confianza, ¿mostramos igualmente la sugerencia (con un "¿Es este?") o directamente dejamos el campo vacío para que el usuario escriba?

17. **¿Dónde se guarda la foto del plato?**
    El spec dice que sube a Drive y guarda el link. ¿A qué carpeta de Drive? ¿Con qué nombre de archivo? ¿Pública o solo accesible con la service account?

---

## 5. Frontend y UX

18. **¿Colores exactos de la marca LATAM?**
    Rojo (`#E31837`), azul oscuro (`#00175A`) y blanco son los principales. ¿Hay guía de marca oficial a seguir o con esos tres colores es suficiente?

19. **¿El formulario de evaluador es un dropdown o texto libre?**
    Si es dropdown, ¿hay una lista fija de evaluadores o viene de alguna fuente (Sheets, BigQuery)?

20. **¿La app necesita funcionar offline o con mala conexión?**
    En la cabina / catering puede haber señal intermitente. ¿Se guarda el borrador localmente si falla el envío, o se asume conexión estable?

21. **¿Cuántas evaluaciones se esperan por turno / por día?**
    Esto afecta si necesitamos paginación, historial de evaluaciones anteriores en la misma sesión, o si con "evaluar otro plato" alcanza.

22. **¿La app necesita mostrar un historial de evaluaciones previas?**
    ¿O es solo captura — una evaluación a la vez sin ver las anteriores?

---

## 6. Reglas de negocio y validaciones

23. **¿Qué pasa con una foto de pésima calidad (muy oscura, movida)?**
    ¿Se avisa al usuario antes de mandarla a Claude, o se deja que Claude intente igual?

24. **¿El evaluador puede corregir el plato identificado por la IA?**
    El spec dice que sí (campo editable), pero ¿eso queda registrado de alguna forma para medir la precisión del matching?

25. **¿Hay platos que no deben evaluarse nunca (ej. bebidas, snacks)?**
    ¿El catálogo los excluye de antemano, o pueden aparecer como candidatos?

26. **¿Quién puede ver / exportar los datos de Sheets?**
    ¿Solo el equipo de calidad, o también los proveedores (FRA, GG MAD)? Esto afecta si necesitamos permisos distintos en el Sheet.

---

## Pendientes ya identificados en el spec

- [ ] Confirmar nombre/formato exacto del catálogo con Pedro
- [ ] Definir si la carpeta Drive de imágenes existe o hay que armarla
- [ ] Elegir entre Opción A (Apps Script + microservicio) u Opción B (backend único)
- [ ] Confirmar API key de Anthropic a usar
- [ ] Definir Spreadsheet ID del Sheet de respuestas
- [ ] Definir si un código puede tener más de una imagen de referencia
