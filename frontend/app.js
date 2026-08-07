// ─── Estado global ────────────────────────────────────────────────────────────
const state = {
  stream: null,
  fotoDataUrl: null,
  fotoBase64: null,
  codigoConfirmado: null,
  nombreConfirmado: null,
  imagenReferencia: '',
  historial: [],
  evaluadorGuardado: '',
  gridDetectado: '',  // 'BC', 'PYC', 'YC', 'CREW', etc. — devuelto por Gemini
};

const CRITERIOS = [
  { key: 'color',   label: 'Color' },
  { key: 'aspecto', label: 'Aspecto' },
  { key: 'olor',    label: 'Olor' },
  { key: 'sabor',   label: 'Sabor' },
  { key: 'textura', label: 'Textura' },
];

const DESCRIPTORES = { 1: 'Deficiente', 2: 'Aceptable', 3: 'Excelente' };

let calificaciones = {};

// ─── Navegación ───────────────────────────────────────────────────────────────
function showScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}

// ─── Cámara ───────────────────────────────────────────────────────────────────
async function iniciarCamara() {
  const video = document.getElementById('video');
  const errorEl = document.getElementById('error-camara');
  errorEl.classList.add('hidden');
  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      video: { facingMode: 'environment', width: { ideal: 1280 }, height: { ideal: 720 } },
      audio: false,
    });
    video.srcObject = state.stream;
  } catch {
    errorEl.classList.remove('hidden');
    errorEl.textContent = 'No se pudo acceder a la cámara. Verifica que el sitio tenga permiso.';
  }
}

function detenerCamara() {
  if (state.stream) {
    state.stream.getTracks().forEach(t => t.stop());
    state.stream = null;
  }
}

function capturarFoto() {
  const video = document.getElementById('video');
  const canvas = document.getElementById('canvas');
  canvas.width  = video.videoWidth  || 1280;
  canvas.height = video.videoHeight || 720;
  canvas.getContext('2d').drawImage(video, 0, 0);
  state.fotoDataUrl = canvas.toDataURL('image/jpeg', 0.85);
  state.fotoBase64  = state.fotoDataUrl.split(',')[1];
  detenerCamara();
}

// ─── Análisis con backend ─────────────────────────────────────────────────────
async function analizarFoto() {
  showScreen('screen-analizando');
  try {
    const resp = await Promise.race([
      fetch('/api/identificar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ foto: state.fotoBase64 }),
      }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 25000)),
    ]);
    const data = await resp.json();
    mostrarConfirmacion(!!data.identificado, data.imagen_referencia || '', data.grid || '', data.candidatos || [], data.confianza || 0);
  } catch {
    // Timeout o error de red → dejar pasar con campo vacío
    mostrarConfirmacion(false, '', '', [], 0);
  }
}

// ─── Pantalla 3: Confirmar código ────────────────────────────────────────────
function mostrarConfirmacion(identificado, imagenReferencia, grid, candidatos, confianza) {
  state.imagenReferencia = imagenReferencia || '';
  state.gridDetectado = grid || '';

  document.getElementById('foto-preview').src = state.fotoDataUrl;
  document.getElementById('select-grid').value = grid || '';

  const hayCandidatos = candidatos.length > 0;
  document.getElementById('bloque-candidatos').classList.toggle('hidden', !hayCandidatos);
  document.getElementById('bloque-no-identificado').classList.toggle('hidden', hayCandidatos);

  if (hayCandidatos) {
    renderCandidatos(candidatos, identificado);
  } else {
    document.getElementById('input-codigo').value = '';
  }

  showScreen('screen-confirmar');
}

function renderCandidatos(candidatos, identificado) {
  // Encabezado según confianza
  const titulo = document.querySelector('#bloque-candidatos > p:first-child');
  const subtitulo = document.querySelector('#bloque-candidatos > p:last-child');
  if (!identificado) {
    titulo.textContent = 'Baja confianza — ¿alguno de estos es correcto?';
    titulo.className = 'text-[11px] text-amber-500 uppercase tracking-wider';
    subtitulo.textContent = 'La IA no está segura. Selecciona si corresponde o ingresa el código manualmente.';
  } else {
    titulo.textContent = 'Selecciona el código correcto';
    titulo.className = 'text-[11px] text-gray-400 uppercase tracking-wider';
    subtitulo.textContent = 'Edita el campo de abajo si ninguno es correcto';
  }

  const lista = document.getElementById('candidatos-lista');
  lista.innerHTML = candidatos.map((c, i) => {
    const badge = c.confianza >= 0.65
      ? `<span class="candidato-badge text-[10px] bg-green-100 text-green-700 px-2 py-0.5 rounded-full">coincidencia</span>`
      : c.confianza >= 0.42
        ? `<span class="candidato-badge text-[10px] bg-gray-100 text-gray-500 px-2 py-0.5 rounded-full">verificar</span>`
        : `<span class="candidato-badge text-[10px] bg-amber-100 text-amber-600 px-2 py-0.5 rounded-full">incierto</span>`;
    return `
      <button type="button"
        class="candidato-btn${i === 0 ? ' selected' : ''} w-full text-left border-2 border-gray-200 bg-white rounded-2xl px-4 py-3 active:scale-[0.98]"
        data-codigo="${c.codigo}" data-nombre="${c.nombre || ''}">
        <div class="flex items-center justify-between gap-2">
          <span class="font-mono font-black text-xl text-latam-blue">${c.codigo}</span>
          ${badge}
        </div>
        ${c.nombre ? `<span class="candidato-nombre block text-sm text-gray-400 mt-0.5">${c.nombre}</span>` : ''}
      </button>`;
  }).join('');

  seleccionarCandidato(candidatos[0].codigo, candidatos[0].nombre || '');

  lista.querySelectorAll('.candidato-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      lista.querySelectorAll('.candidato-btn').forEach(b => b.classList.remove('selected'));
      btn.classList.add('selected');
      seleccionarCandidato(btn.dataset.codigo, btn.dataset.nombre);
    });
  });
}

function seleccionarCandidato(codigo, nombre) {
  document.getElementById('input-codigo').value = codigo;
}

// ─── Pantalla 4: Formulario ───────────────────────────────────────────────────
function abrirFormulario() {
  const codigo = state.codigoConfirmado;
  const nombre = state.nombreConfirmado;

  document.getElementById('form-codigo').textContent = codigo;
  document.getElementById('form-nombre').textContent = nombre;
  document.getElementById('form-thumb').src = state.fotoDataUrl;
  document.getElementById('error-formulario').classList.add('hidden');
  document.getElementById('input-comentarios').value = '';

  if (state.evaluadorGuardado) {
    document.getElementById('input-evaluador').value = state.evaluadorGuardado;
  }

  // Inicializar calificaciones
  CRITERIOS.forEach(c => { calificaciones[c.key] = null; });

  // Renderizar criterios
  const container = document.getElementById('criterios-container');
  container.innerHTML = CRITERIOS.map(c => `
    <div>
      <p class="text-sm font-semibold text-gray-700 mb-2">${c.label}</p>
      <div class="flex gap-1.5" role="group" aria-label="${c.label}">
        ${[1,2,3].map(n => `
          <button type="button" role="button" aria-pressed="false"
            class="rating-btn flex-1 border-2 border-gray-200 rounded-xl py-2.5 text-center"
            data-key="${c.key}" data-val="${n}">
            <span class="block text-base font-black text-gray-700">${n}</span>
            <span class="descriptor block text-[9px] text-gray-400 leading-tight mt-0.5">${DESCRIPTORES[n]}</span>
          </button>
        `).join('')}
      </div>
    </div>
  `).join('');

  container.querySelectorAll('.rating-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.key;
      const val = parseInt(btn.dataset.val);
      calificaciones[key] = val;

      // Actualizar aria-pressed en el grupo
      container.querySelectorAll(`[data-key="${key}"]`).forEach(b => {
        b.setAttribute('aria-pressed', b.dataset.val === String(val) ? 'true' : 'false');
      });
    });
  });

  showScreen('screen-formulario');
}

// ─── Envío ────────────────────────────────────────────────────────────────────
async function enviarEvaluacion() {
  const evaluador = document.getElementById('input-evaluador').value.trim();
  const errorEl = document.getElementById('error-formulario');

  if (!evaluador) {
    errorEl.classList.remove('hidden');
    errorEl.textContent = 'Ingresa tu nombre para continuar.';
    document.getElementById('input-evaluador').focus();
    return;
  }

  const faltantes = CRITERIOS.filter(c => calificaciones[c.key] === null).map(c => c.label);
  if (faltantes.length) {
    errorEl.classList.remove('hidden');
    errorEl.textContent = `Completa: ${faltantes.join(', ')}`;
    return;
  }

  errorEl.classList.add('hidden');
  state.evaluadorGuardado = evaluador;
  showScreen('screen-enviando');

  const payload = {
    evaluador,
    codigo:     state.codigoConfirmado,
    nombre:     state.nombreConfirmado,
    grid:       document.getElementById('select-grid').value || state.gridDetectado,
    proveedor:          'Gategourmet SCL',
    foto:               state.fotoBase64,
    imagen_referencia:  state.imagenReferencia,
    comentarios: document.getElementById('input-comentarios').value.trim(),
    fecha:      new Date().toISOString(),
    ...Object.fromEntries(CRITERIOS.map(c => [c.key, calificaciones[c.key]])),
  };

  try {
    await Promise.race([
      fetch('/api/guardar', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      }),
      new Promise((_, reject) => setTimeout(() => reject(new Error('timeout')), 25000)),
    ]);
  } catch {
    // Registramos en historial local aunque falle el backend
  }

  registrarEnHistorial(payload);

  document.getElementById('exito-detalle').textContent =
    `${payload.codigo} · ${evaluador} · ${new Date(payload.fecha).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' })}`;
  showScreen('screen-exito');
}

// ─── Historial ────────────────────────────────────────────────────────────────
function registrarEnHistorial(ev) {
  state.historial.unshift(ev);
  const badge = document.getElementById('historial-badge');
  badge.textContent = state.historial.length;
  badge.classList.remove('hidden');
}

function renderizarHistorial() {
  const lista  = document.getElementById('historial-lista');
  const vacio  = document.getElementById('historial-vacio');

  if (!state.historial.length) {
    lista.innerHTML = '';
    vacio.classList.remove('hidden');
    return;
  }

  vacio.classList.add('hidden');
  lista.innerHTML = state.historial.map(ev => {
    const hora = new Date(ev.fecha).toLocaleTimeString('es-CL', { hour: '2-digit', minute: '2-digit' });
    const promedioNum = CRITERIOS.reduce((s, c) => s + ev[c.key], 0) / CRITERIOS.length;
    const promedio = promedioNum.toFixed(1);
    return `
      <div class="bg-white rounded-2xl p-3 shadow-sm border border-gray-100 flex gap-3 items-start">
        <img src="data:image/jpeg;base64,${ev.foto}"
          class="w-16 h-16 rounded-xl object-cover flex-shrink-0">
        <div class="flex-1 min-w-0">
          <div class="flex items-baseline gap-2">
            <p class="font-black text-latam-blue text-lg font-mono">${ev.codigo}</p>
            <span class="text-xs text-gray-400">${hora}</span>
          </div>
          <p class="text-xs text-gray-500 truncate">${ev.evaluador}</p>
          <div class="flex gap-1 mt-1.5 flex-wrap">
            ${CRITERIOS.map(c => `
              <span class="text-[10px] bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded-md">
                ${c.label.split('/')[0].trim().split(' ')[0]}: <strong>${ev[c.key]}</strong>
              </span>
            `).join('')}
            <span class="text-[10px] bg-latam-blue/10 text-latam-blue font-bold px-1.5 py-0.5 rounded-md">
              Prom: ${promedio}
            </span>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

// ─── Eventos ──────────────────────────────────────────────────────────────────
document.getElementById('btn-capturar').addEventListener('click', () => {
  capturarFoto();
  analizarFoto();
});

document.getElementById('btn-confirmar-codigo').addEventListener('click', () => {
  const codigo = document.getElementById('input-codigo').value.trim().toUpperCase();
  if (!codigo) {
    document.getElementById('input-codigo').focus();
    document.getElementById('input-codigo').classList.add('border-red-400');
    return;
  }
  document.getElementById('input-codigo').classList.remove('border-red-400');
  state.codigoConfirmado = codigo;
  // Tomar el nombre del candidato seleccionado, o del campo si fue editado manualmente
  const btnSeleccionado = document.querySelector('.candidato-btn.selected');
  state.nombreConfirmado = (btnSeleccionado && btnSeleccionado.dataset.codigo === codigo)
    ? (btnSeleccionado.dataset.nombre || '')
    : '';
  abrirFormulario();
});

document.getElementById('btn-retomar-foto').addEventListener('click', () => {
  showScreen('screen-camara');
  iniciarCamara();
});

document.getElementById('btn-enviar').addEventListener('click', enviarEvaluacion);

document.getElementById('btn-nueva').addEventListener('click', () => {
  showScreen('screen-camara');
  iniciarCamara();
});

document.getElementById('btn-historial').addEventListener('click', () => {
  renderizarHistorial();
  showScreen('screen-historial');
});

document.getElementById('btn-cerrar-historial').addEventListener('click', () => {
  showScreen('screen-camara');
  if (!state.stream) iniciarCamara();
});

// ─── Arranque ─────────────────────────────────────────────────────────────────
iniciarCamara();
