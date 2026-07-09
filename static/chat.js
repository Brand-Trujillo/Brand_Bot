const form = document.getElementById('chat-form');
const input = document.getElementById('message');
const chat = document.getElementById('chat');
const sendBtn = document.getElementById('send-btn');

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
  return data.reply;
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
    const reply = await sendMessage(message);
    addBubble('bot', reply);
  } catch (err) {
    addBubble('bot', `Error: ${err.message}`);
  } finally {
    sendBtn.disabled = false;
    sendBtn.textContent = 'Enviar';
  }
});
