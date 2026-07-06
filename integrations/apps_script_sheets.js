/**
 * Apps Script — Webhook + Reporte QA LATAM
 *
 * PASOS PARA DESPLEGAR:
 * 1. Abre tu Google Sheet → Extensions > Apps Script
 * 2. Pega este código completo y guarda
 * 3. Deploy > Manage deployments > editar deployment existente > New version > Deploy
 *    (NO crear uno nuevo — la URL del webhook debe mantenerse igual)
 * 4. El menú "LATAM QA" aparecerá en el Sheet al recargar
 */

const SPREADSHEET_ID  = "1G2xd9D5a4_8JJkf7I3ZkAQMd-zqc30EFBOKuXeQm4bY";
const SHEET_NAME      = "Evaluaciones";
const DRIVE_FOLDER_ID = "1K-cPBr3VU4_yZDLjWl-Z3Ug5pkcK1BEa";
const RENDER_URL      = "https://sensorial-latam.onrender.com";

const EMAIL_LATAM   = "pedro.llancaqueon@gmail.com";
const EMAIL_COCINA  = "pe.llancaqueo@duocuc.cl";

const COLUMNS = [
  "fecha", "evaluador", "proveedor", "codigo", "nombre",
  "color", "aspecto", "olor", "sabor", "textura",
  "promedio", "comentarios", "foto_url", "imagen_referencia"
];

const SCORES = ["color", "aspecto", "olor", "sabor", "textura"];

// ── Menú personalizado ────────────────────────────────────────────────────────

function onOpen() {
  SpreadsheetApp.getUi()
    .createMenu("LATAM QA")
    .addItem("Enviar Reporte de Sesión", "enviarReporteQA")
    .addToUi();
}

// ── Webhook receptor de evaluaciones ─────────────────────────────────────────

function doPost(e) {
  try {
    const data = JSON.parse(e.postData.contents);
    const ss   = SpreadsheetApp.openById(SPREADSHEET_ID);
    let sheet  = ss.getSheetByName(SHEET_NAME);

    if (!sheet) {
      sheet = ss.insertSheet(SHEET_NAME);
      sheet.appendRow(COLUMNS.map(c => c.toUpperCase()));
      sheet.getRange(1, 1, 1, COLUMNS.length)
           .setFontWeight("bold")
           .setBackground("#00175A")
           .setFontColor("#FFFFFF");
    }

    // Subir foto a Drive
    let foto_url = "";
    if (data.foto) {
      try {
        const folder    = DriveApp.getFolderById(DRIVE_FOLDER_ID);
        const timestamp = new Date().getTime();
        const filename  = `${data.codigo}_${timestamp}.jpg`;
        const decoded   = Utilities.base64Decode(data.foto);
        const blob      = Utilities.newBlob(decoded, "image/jpeg", filename);
        const file      = folder.createFile(blob);
        foto_url        = file.getDownloadUrl();
      } catch (driveErr) {
        console.log("Drive upload error: " + driveErr.message);
      }
    }

    const promedio = SCORES.reduce((s, k) => s + (Number(data[k]) || 0), 0) / SCORES.length;

    data.foto_url = foto_url;
    const row = COLUMNS.map(col => {
      if (col === "promedio") return Math.round(promedio * 100) / 100;
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

// ── Reporte QA ────────────────────────────────────────────────────────────────

function enviarReporteQA() {
  const ss    = SpreadsheetApp.openById(SPREADSHEET_ID);
  const sheet = ss.getSheetByName(SHEET_NAME);
  if (!sheet) { SpreadsheetApp.getUi().alert("No hay datos en el Sheet."); return; }

  const allData = sheet.getDataRange().getValues();
  if (allData.length < 2) { SpreadsheetApp.getUi().alert("No hay evaluaciones."); return; }

  // Índices de columnas
  const col = {};
  COLUMNS.forEach((c, i) => { col[c] = i; });

  // Filas de hoy (fecha local Chile)
  const hoy = Utilities.formatDate(new Date(), "America/Santiago", "yyyy-MM-dd");
  const rows = allData.slice(1).filter(r => {
    const f = String(r[col.fecha]);
    return f.startsWith(hoy);
  });

  if (rows.length === 0) {
    SpreadsheetApp.getUi().alert("No hay evaluaciones de hoy para reportar.");
    return;
  }

  // Estadísticas de sesión
  const total      = rows.length;
  const promedios  = rows.map(r => Number(r[col.promedio]) || 0);
  const promGeneral = promedios.reduce((s, v) => s + v, 0) / total;
  const conObs     = rows.filter(r => Number(r[col.promedio]) < 3);
  const evaluadores = [...new Set(rows.map(r => r[col.evaluador]))].join(", ");

  // Construir HTML
  const inlineImages = {};
  let seccionesObs   = "";

  conObs.forEach((row, i) => {
    const codigo    = row[col.codigo];
    const nombre    = row[col.nombre];
    const promedio  = Number(row[col.promedio]).toFixed(2);
    const comentarios = row[col.comentarios] || "";
    const foto_url  = row[col.foto_url] || "";
    const img_ref   = row[col.imagen_referencia] || "";

    // Foto capturada desde Drive
    let sampleCid = "";
    if (foto_url) {
      try {
        const fileId   = foto_url.match(/id=([^&]+)/)?.[1];
        if (fileId) {
          const blob = DriveApp.getFileById(fileId).getBlob().setName(`sample_${i}`);
          inlineImages[`sample_${i}`] = blob;
          sampleCid = `sample_${i}`;
        }
      } catch(e) { console.log("Error foto Drive: " + e.message); }
    }

    // Foto de referencia del catálogo desde Render
    let refCid = "";
    if (img_ref) {
      try {
        const refUrl = `${RENDER_URL}/${img_ref}`.replace(/ /g, "%20");
        const blob   = UrlFetchApp.fetch(refUrl, {muteHttpExceptions: true})
                         .getBlob().setName(`ref_${i}`);
        inlineImages[`ref_${i}`] = blob;
        refCid = `ref_${i}`;
      } catch(e) { console.log("Error imagen referencia: " + e.message); }
    }

    const scoreColor   = _scoreCell(row[col.color]);
    const scoreAspecto = _scoreCell(row[col.aspecto]);
    const scoreOlor    = _scoreCell(row[col.olor]);
    const scoreSabor   = _scoreCell(row[col.sabor]);
    const scoreTextura = _scoreCell(row[col.textura]);

    seccionesObs += `
    <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;border:1px solid #e5e7eb;border-radius:8px;overflow:hidden;">
      <tr><td style="background:#E31837;padding:12px 16px;">
        <span style="color:white;font-weight:bold;font-size:15px;">${codigo}</span>
        <span style="color:rgba(255,255,255,0.8);font-size:13px;"> — ${nombre}</span>
        <span style="float:right;color:white;font-weight:bold;">Promedio: ${promedio}/3.0</span>
      </td></tr>
      <tr><td style="padding:16px;">
        <table width="100%" cellpadding="0" cellspacing="0">
          <tr>
            <td width="50%" style="padding-right:8px;vertical-align:top;">
              <p style="margin:0 0 6px;font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;">Foto tomada (sample)</p>
              ${sampleCid ? `<img src="cid:${sampleCid}" width="240" height="180" style="object-fit:cover;border-radius:6px;display:block;">` : '<p style="color:#9ca3af;font-size:12px;">No disponible</p>'}
            </td>
            <td width="50%" style="padding-left:8px;vertical-align:top;">
              <p style="margin:0 0 6px;font-size:12px;color:#6b7280;font-weight:600;text-transform:uppercase;">Referencia catálogo (specs)</p>
              ${refCid ? `<img src="cid:${refCid}" width="240" height="180" style="object-fit:cover;border-radius:6px;display:block;">` : '<p style="color:#9ca3af;font-size:12px;">No disponible</p>'}
            </td>
          </tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 16px 16px;">
        <table width="100%" cellpadding="8" cellspacing="0" style="border-collapse:collapse;text-align:center;font-size:13px;">
          <tr style="background:#f9fafb;">
            <th style="border:1px solid #e5e7eb;">Color</th>
            <th style="border:1px solid #e5e7eb;">Aspecto</th>
            <th style="border:1px solid #e5e7eb;">Olor</th>
            <th style="border:1px solid #e5e7eb;">Sabor</th>
            <th style="border:1px solid #e5e7eb;">Textura</th>
          </tr>
          <tr>
            <td style="border:1px solid #e5e7eb;">${scoreColor}</td>
            <td style="border:1px solid #e5e7eb;">${scoreAspecto}</td>
            <td style="border:1px solid #e5e7eb;">${scoreOlor}</td>
            <td style="border:1px solid #e5e7eb;">${scoreSabor}</td>
            <td style="border:1px solid #e5e7eb;">${scoreTextura}</td>
          </tr>
        </table>
        ${comentarios ? `
        <table width="100%" cellpadding="0" cellspacing="0" style="margin-top:12px;">
          <tr><td style="background:#fff7ed;border-left:4px solid #E31837;padding:10px 14px;border-radius:4px;font-size:13px;color:#374151;">
            <strong>Observación:</strong> ${comentarios}
          </td></tr>
        </table>` : ""}
      </td></tr>
    </table>`;
  });

  const fechaLegible = Utilities.formatDate(new Date(), "America/Santiago", "dd/MM/yyyy");

  const html = `<!DOCTYPE html><html><body style="margin:0;padding:0;font-family:Arial,sans-serif;background:#f3f4f6;">
  <table width="100%" cellpadding="0" cellspacing="0" style="max-width:680px;margin:0 auto;background:white;">

    <!-- Header -->
    <tr><td style="background:#00175A;padding:24px 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td>
            <p style="margin:0;color:white;font-size:20px;font-weight:bold;">LATAM Airlines</p>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:13px;">Reporte de Control de Calidad — Catering</p>
          </td>
          <td style="text-align:right;vertical-align:top;">
            <p style="margin:0;color:white;font-size:13px;">${fechaLegible}</p>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.7);font-size:12px;">${evaluadores}</p>
          </td>
        </tr>
      </table>
    </td></tr>

    <!-- Score general -->
    <tr><td style="padding:24px 32px;background:#f9fafb;border-bottom:1px solid #e5e7eb;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="text-align:center;padding:12px;">
            <p style="margin:0;font-size:36px;font-weight:bold;color:${promGeneral >= 2.5 ? "#16a34a" : promGeneral >= 2 ? "#d97706" : "#dc2626"};">${promGeneral.toFixed(2)}<span style="font-size:16px;color:#6b7280;">/3.0</span></p>
            <p style="margin:4px 0 0;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Score General</p>
          </td>
          <td style="text-align:center;padding:12px;">
            <p style="margin:0;font-size:36px;font-weight:bold;color:#00175A;">${total}</p>
            <p style="margin:4px 0 0;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Servicios evaluados</p>
          </td>
          <td style="text-align:center;padding:12px;">
            <p style="margin:0;font-size:36px;font-weight:bold;color:#E31837;">${conObs.length}</p>
            <p style="margin:4px 0 0;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Con observaciones</p>
          </td>
          <td style="text-align:center;padding:12px;">
            <p style="margin:0;font-size:36px;font-weight:bold;color:#16a34a;">${total - conObs.length}</p>
            <p style="margin:4px 0 0;font-size:12px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Sin observaciones</p>
          </td>
        </tr>
      </table>
    </td></tr>

    <!-- Cuerpo -->
    <tr><td style="padding:24px 32px;">
      ${conObs.length > 0 ? `
      <p style="font-size:15px;font-weight:bold;color:#111827;margin:0 0 16px;">Servicios con observaciones</p>
      ${seccionesObs}` : `
      <table width="100%" cellpadding="24" cellspacing="0" style="background:#f0fdf4;border-radius:8px;text-align:center;">
        <tr><td>
          <p style="font-size:32px;margin:0;">✅</p>
          <p style="color:#16a34a;font-weight:bold;font-size:16px;margin:8px 0 0;">Todos los servicios evaluados con score perfecto</p>
        </td></tr>
      </table>`}
    </td></tr>

    <!-- Footer -->
    <tr><td style="background:#00175A;padding:20px 32px;text-align:center;">
      <p style="margin:0;color:rgba(255,255,255,0.6);font-size:12px;">LATAM Airlines — Dirección de Calidad de Catering · Generado automáticamente</p>
    </td></tr>

  </table>
  </body></html>`;

  MailApp.sendEmail({
    to:           `${EMAIL_LATAM},${EMAIL_COCINA}`,
    subject:      `Reporte QA Catering LATAM — ${fechaLegible} — Score ${promGeneral.toFixed(2)}/3.0`,
    htmlBody:     html,
    inlineImages: inlineImages,
  });

  SpreadsheetApp.getUi().alert(`✅ Reporte enviado a:\n${EMAIL_LATAM}\n${EMAIL_COCINA}`);
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function _scoreCell(val) {
  const n = Number(val);
  const color = n === 3 ? "#16a34a" : n === 2 ? "#d97706" : "#dc2626";
  return `<span style="font-weight:bold;color:${color};">${n}</span>`;
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
        color: 3, aspecto: 2, olor: 3, sabor: 3, textura: 2,
        comentarios: "Prueba",
        imagen_referencia: "",
        foto: "",
      })
    }
  };
  Logger.log(doPost(fake).getContent());
}
