const form = document.getElementById('chat-form');
const input = document.getElementById('message');
const chat = document.getElementById('chat');
const sendBtn = document.getElementById('send-btn');
const backendVersionEl = document.getElementById('backend-version');

async function initBackendVersionBadge() {
  if (!backendVersionEl) return;

  try {
    const res = await fetch('/health', { cache: 'no-store' });
    const data = await res.json().catch(() => ({}));
    if (res.ok && data && data.version) {
      backendVersionEl.textContent = `backend ${data.version}`;
      backendVersionEl.classList.remove('version-badge--error');
      return;
    }
  } catch (_err) {
    // Sin accion: el badge se marcara como error abajo.
  }

  backendVersionEl.textContent = 'backend no detectado';
  backendVersionEl.classList.add('version-badge--error');
}

function addBubble(role, text) {
  const article = document.createElement('article');
  article.className = `bubble ${role}`;

  const title = document.createElement('h2');
  title.textContent = role === 'user' ? 'Tu' : 'Asistente';

  const p = document.createElement('p');
  p.textContent = text;

  article.appendChild(title);
  article.appendChild(p);
  chat.appendChild(article);
  chat.scrollTop = chat.scrollHeight;
}

function addBotReplyAsBubbles(reply) {
  const text = String(reply || '').trim();
  if (!text) return;
  const normalized = text.replace(
    'Evolution API no está configurada. Define la variable de entorno EVOLUTION_API_KEY y revisa EVOLUTION_API_URL.',
    'No encontré esa muestra ahora. Prueba con cliente, referencia o informe y te ayudo al instante.'
  );
  addBubble('bot', normalized);
}

async function sendMessage(message) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message })
  });

  const data = await res.json().catch(() => ({}));
  if (!res.ok || !data.ok) {
    throw new Error(data.error || 'No se pudo procesar la consulta.');
  }
  return {
    reply: data.reply,
    replies: Array.isArray(data.replies) ? data.replies : null
  };
}

form.addEventListener('submit', async (event) => {
  event.preventDefault();

  const message = input.value.trim();
  if (!message) return;

  addBubble('user', message);
  input.value = '';
  input.focus();

  sendBtn.disabled = true;
  sendBtn.textContent = 'Enviando...';

  try {
    const result = await sendMessage(message);
    if (Array.isArray(result.replies) && result.replies.length > 0) {
      result.replies.forEach((item) => addBotReplyAsBubbles(item));
    } else {
      // Fallback minimo para compatibilidad.
      addBotReplyAsBubbles(result.reply);
    }
  } catch (err) {
    addBubble('bot', `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = 'Enviar';
  }
});

initBackendVersionBadge();
