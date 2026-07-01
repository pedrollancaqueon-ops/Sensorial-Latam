/**
 * Apps Script — Webhook receptor para evaluaciones sensoriales LATAM
 *
 * PASOS PARA DESPLEGAR:
 * 1. Abre tu Google Sheet
 * 2. Extensions > Apps Script
 * 3. Pega este código y guarda
 * 4. Deploy > New deployment > Web app
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 5. Copia la URL del deployment
 * 6. Pégala en .env como: SHEETS_WEBHOOK_URL=https://script.google.com/...
 */

const SPREADSHEET_ID = "1G2xd9D5a4_8JJkf7I3ZkAQMd-zqc30EFBOKuXeQm4bY";
const SHEET_NAME = "Evaluaciones";

const COLUMNS = [
  "fecha", "evaluador", "proveedor", "codigo", "nombre",
  "apariencia", "aroma", "sabor", "textura", "temperatura",
  "promedio", "comentarios"
];

function doPost(e) {
  try {
    const data   = JSON.parse(e.postData.contents);
    const ss     = SpreadsheetApp.openById(SPREADSHEET_ID);
    let   sheet  = ss.getSheetByName(SHEET_NAME);

    // Crear hoja con cabeceras si no existe
    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(COLUMNS.map(c => c.toUpperCase()));
      sheet.getRange(1, 1, 1, COLUMNS.length)
           .setFontWeight("bold")
           .setBackground("#00175A")
           .setFontColor("#FFFFFF");
    }

    const scores   = ["apariencia", "aroma", "sabor", "textura", "temperatura"];
    const promedio = scores.reduce((s, k) => s + (Number(data[k]) || 0), 0) / scores.length;

    const row = COLUMNS.map(col => {
      if (col === "promedio") return Math.round(promedio * 10) / 10;
      return data[col] !== undefined ? data[col] : "";
    });

    sheet.appendRow(row);

    return ContentService
      .createTextOutput(JSON.stringify({ ok: true }))
      .setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService
      .createTextOutput(JSON.stringify({ ok: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

// Test manual desde el editor
function testPost() {
  const fake = {
    postData: {
      contents: JSON.stringify({
        fecha: new Date().toISOString(),
        evaluador: "Test User",
        proveedor: "Gategourmet SCL",
        codigo: "HLDL",
        nombre: "Plato Carne",
        apariencia: 4, aroma: 3, sabor: 5, textura: 4, temperatura: 4,
        comentarios: "Prueba"
      })
    }
  };
  Logger.log(doPost(fake).getContent());
}
