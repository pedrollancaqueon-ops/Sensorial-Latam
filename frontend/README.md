# Frontend

App React + Tailwind, mobile-first. El usuario la usa desde el celular con cámara.

## Flujo de pantallas
1. Pantalla de cámara → captura foto
2. Estado "Analizando plato..." (1–3 seg)
3. Confirmación del plato identificado
4. Formulario de evaluación sensorial (5 criterios 1–5 + comentarios)
5. Confirmación visual de envío exitoso

## Stack
- React (Vite)
- Tailwind CSS
- API nativa del navegador: `getUserMedia` para la cámara (requiere HTTPS)
- Hosting: Render.com o Vercel

## Paleta LATAM
- Rojo: `#E31837`
- Azul oscuro: `#00175A`
- Blanco: `#FFFFFF`

## Pendiente
- Confirmar lista de evaluadores (dropdown o texto libre) — ver pregunta 19 en docs/preguntas-alineacion.md
