const statusEl = document.getElementById('recent-status');
const daysEl = document.getElementById('recent-days');
const refreshBtn = document.getElementById('refresh-btn');
const backendVersionEl = document.getElementById('backend-version');

const AUTO_REFRESH_MS = 20000;

function escapeHtml(text) {
  return String(text || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}

function renderBadge(version, commit) {
  if (!backendVersionEl) return;
  const shortCommit = String(commit || '').trim().slice(0, 7);
  backendVersionEl.textContent = shortCommit
    ? `backend ${version} · ${shortCommit}`
    : `backend ${version}`;
  backendVersionEl.classList.remove('version-badge--error');
}

function renderRow(item) {
  const fallback = 'N/E';
  return `
    <tr>
      <td>${escapeHtml(item.fecha || fallback)}</td>
      <td>${escapeHtml(item.cliente || fallback)}</td>
      <td>${escapeHtml(item.descripcion || fallback)}</td>
      <td>${escapeHtml(item.marca || fallback)}</td>
      <td>${escapeHtml(item.referencia_modelo || fallback)}</td>
      <td>${escapeHtml(item.referencia_externa || fallback)}</td>
      <td>${escapeHtml(item.referencia_interna || fallback)}</td>
      <td>${escapeHtml(item.informe || fallback)}</td>
      <td>${escapeHtml(item.cotizacion || fallback)}</td>
      <td>${escapeHtml(item.estado || fallback)}</td>
      <td>${escapeHtml(item.numero || fallback)}</td>
    </tr>
  `;
}

function renderDays(days) {
  if (!Array.isArray(days) || days.length === 0) {
    daysEl.innerHTML = '<p class="empty-state">No hay informacion disponible por ahora.</p>';
    return;
  }

  daysEl.innerHTML = days.map((day) => {
    const items = Array.isArray(day.items) ? day.items : [];
    const rowsHtml = items.length > 0
      ? items.map(renderRow).join('')
      : '<tr><td colspan="11" class="empty-cell">No hay muestras para este dia.</td></tr>';

    return `
      <section class="day-block" data-day="${escapeHtml(day.key || '')}">
        <header class="day-block__header">
          <h2>${escapeHtml(day.label || 'Dia')}</h2>
          <span>${items.length} muestras</span>
        </header>
        <div class="day-table-wrap">
          <table class="day-table" role="table" aria-label="Muestras recientes de ${escapeHtml(day.label || 'dia')}">
            <thead>
              <tr>
                <th>Fecha</th>
                <th>Cliente</th>
                <th>Descripcion</th>
                <th>Marca</th>
                <th>Referencia / Modelo</th>
                <th>Referencia externa</th>
                <th>Referencia interna</th>
                <th>Informe</th>
                <th>Cotizacion</th>
                <th>Estado</th>
                <th>N° muestras</th>
              </tr>
            </thead>
            <tbody>${rowsHtml}</tbody>
          </table>
        </div>
      </section>
    `;
  }).join('');
}

async function loadRecientes() {
  const now = new Date();
  const stamp = `${now.toLocaleDateString('es-CO')} ${now.toLocaleTimeString('es-CO')}`;
  statusEl.textContent = `Actualizando... (${stamp})`;
  if (refreshBtn) {
    refreshBtn.disabled = true;
    refreshBtn.textContent = 'Actualizando...';
  }

  try {
    const res = await fetch(`/api/recentes?limit=20&t=${Date.now()}`, { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (!res.ok || !data.ok) {
      throw new Error(data.error || 'No se pudo cargar la vista de recientes.');
    }

    renderDays(data.days || []);
    renderBadge(data.version, data.deploy_commit);

    const source = data.source ? ` · fuente: ${data.source}` : '';
    statusEl.textContent = `Actualizado: ${stamp}${source}`;
  } catch (error) {
    statusEl.textContent = `Error al actualizar: ${error.message}`;
    daysEl.innerHTML = '<p class="empty-state">No fue posible cargar las muestras recientes. Intenta de nuevo.</p>';
    if (backendVersionEl) {
      backendVersionEl.classList.add('version-badge--error');
    }
  } finally {
    if (refreshBtn) {
      refreshBtn.disabled = false;
      refreshBtn.textContent = 'Actualizar';
    }
  }
}

if (refreshBtn) {
  refreshBtn.addEventListener('click', () => {
    loadRecientes();
  });
}

loadRecientes();
window.setInterval(loadRecientes, AUTO_REFRESH_MS);
