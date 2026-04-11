/* ============================================
   TELEGRAM MINI APP — PISKA BOT
   Main Application Logic
   ============================================ */

// --- Telegram WebApp SDK ---
const tg = window.Telegram?.WebApp;
if (tg) {
    tg.ready();
    tg.expand();
    tg.enableClosingConfirmation();
    // Адаптируем цвета под тему Telegram
    document.documentElement.style.setProperty('--bg-primary', tg.themeParams.bg_color || '#1a1a2e');
    document.documentElement.style.setProperty('--bg-secondary', tg.themeParams.secondary_bg_color || '#16213e');
    document.documentElement.style.setProperty('--text-primary', tg.themeParams.text_color || '#ffffff');
    document.documentElement.style.setProperty('--text-secondary', tg.themeParams.hint_color || '#8892b0');
}

// --- API BASE URL ---
const API_BASE = window.location.origin + '/api';

// --- DEBUG UID (для локального тестирования без Telegram) ---
const DEBUG_UID = new URLSearchParams(window.location.search).get('uid') || '';

// --- STATE ---
let currentTab = 'home';
let appData = {
    wishes: [],
    quotes: [],
    memories: [],
    relationship: null,
    user: null,
};

// --- INIT ---
document.addEventListener('DOMContentLoaded', () => {
    loadAllData();
    switchTab('home');
});

// ============================================
//                API CALLS
// ============================================
async function apiGet(endpoint) {
    try {
        const headers = {};
        if (tg?.initData) {
            headers['X-Telegram-Init-Data'] = tg.initData;
        }
        const sep = endpoint.includes('?') ? '&' : '?';
        const url = DEBUG_UID ? `${API_BASE}${endpoint}${sep}uid=${DEBUG_UID}` : `${API_BASE}${endpoint}`;
        const resp = await fetch(url, { headers });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error(`API GET ${endpoint}:`, e);
        return null;
    }
}

async function apiPost(endpoint, body) {
    try {
        const headers = { 'Content-Type': 'application/json' };
        if (tg?.initData) {
            headers['X-Telegram-Init-Data'] = tg.initData;
        }
        const sep = endpoint.includes('?') ? '&' : '?';
        const url = DEBUG_UID ? `${API_BASE}${endpoint}${sep}uid=${DEBUG_UID}` : `${API_BASE}${endpoint}`;
        const resp = await fetch(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(body),
        });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error(`API POST ${endpoint}:`, e);
        return null;
    }
}

async function apiDelete(endpoint) {
    try {
        const headers = {};
        if (tg?.initData) {
            headers['X-Telegram-Init-Data'] = tg.initData;
        }
        const sep = endpoint.includes('?') ? '&' : '?';
        const url = DEBUG_UID ? `${API_BASE}${endpoint}${sep}uid=${DEBUG_UID}` : `${API_BASE}${endpoint}`;
        const resp = await fetch(url, { method: 'DELETE', headers });
        if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
        return await resp.json();
    } catch (e) {
        console.error(`API DELETE ${endpoint}:`, e);
        return null;
    }
}

// ============================================
//              LOAD DATA
// ============================================
async function loadAllData() {
    const [wishes, quotes, memories, relationship] = await Promise.all([
        apiGet('/wishes'),
        apiGet('/quotes'),
        apiGet('/memories'),
        apiGet('/relationship'),
    ]);
    appData.wishes = wishes?.data || [];
    appData.quotes = quotes?.data || [];
    appData.memories = memories?.data || [];
    appData.relationship = relationship?.data || null;

    updateRelationshipCounter();
    renderCurrentTab();
}

function updateRelationshipCounter() {
    const el = document.getElementById('relationship-counter');
    if (!appData.relationship?.days) {
        el.textContent = '💕';
        return;
    }
    el.textContent = `Вместе ${appData.relationship.days} дней 💕`;
}

// ============================================
//              TAB SWITCHING
// ============================================
function switchTab(tab) {
    currentTab = tab;

    // Update tab bar
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-tab="${tab}"]`)?.classList.add('active');

    // Toggle chat input
    const chatInput = document.querySelector('.chat-input-wrap');
    if (chatInput) chatInput.classList.toggle('visible', tab === 'ai');

    renderCurrentTab();
}

function renderCurrentTab() {
    const content = document.getElementById('content');
    switch (currentTab) {
        case 'home': renderHome(content); break;
        case 'memories': renderMemories(content); break;
        case 'wishlist': renderWishlist(content); break;
        case 'quotes': renderQuotes(content); break;
        case 'ai': renderAI(content); break;
    }
}

// ============================================
//              HOME TAB
// ============================================
function renderHome(container) {
    const rel = appData.relationship;
    const daysText = rel?.days || '—';
    const dateText = rel?.start_date ? formatDateShort(rel.start_date) : 'Не установлена';

    // Кнопка изменить дату
    const dateAction = rel?.start_date
        ? `<div class="relationship-edit" onclick="openSetDateModal()">✏️ Изменить дату</div>`
        : `<button class="btn btn-primary" style="margin-top:12px;max-width:200px;margin-left:auto;margin-right:auto" onclick="openSetDateModal()">💕 Установить дату</button>`;

    container.innerHTML = `
        <!-- Отношения -->
        <div class="card relationship-card">
            <div class="relationship-days">${daysText}</div>
            <div class="relationship-label">дней вместе</div>
            <div class="relationship-date">С ${dateText}</div>
            ${dateAction}
        </div>

        <!-- Статистика -->
        <div class="stats-row">
            <div class="stat-card">
                <div class="stat-number">${appData.memories.length}</div>
                <div class="stat-label">Воспоминаний</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${appData.wishes.length}</div>
                <div class="stat-label">Хотелок</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">${appData.quotes.length}</div>
                <div class="stat-label">Цитат</div>
            </div>
            <div class="stat-card" onclick="switchTab('ai')">
                <div class="stat-number">🤖</div>
                <div class="stat-label">Спросить ИИ</div>
            </div>
        </div>

        <!-- Быстрые действия -->
        <div class="section-title">Быстрые действия</div>

        <div class="card" onclick="switchTab('memories')">
            <div class="card-header">
                <div class="card-icon pink">📸</div>
                <div>
                    <div class="card-title">Добавить воспоминание</div>
                    <div class="card-subtitle">Фото, видео или текст</div>
                </div>
            </div>
        </div>

        <div class="card" onclick="openAddModal('wish')">
            <div class="card-header">
                <div class="card-icon blue">🎁</div>
                <div>
                    <div class="card-title">В виш-лист</div>
                    <div class="card-subtitle">Добавь свою хотелку</div>
                </div>
            </div>
        </div>

        <div class="card" onclick="openAddModal('quote')">
            <div class="card-header">
                <div class="card-icon green">🤣</div>
                <div>
                    <div class="card-title">В цитаты</div>
                    <div class="card-subtitle">Запомни смешное</div>
                </div>
            </div>
        </div>

        <div class="card" onclick="openSecretMessage()">
            <div class="card-header">
                <div class="card-icon purple">💌</div>
                <div>
                    <div class="card-title">Тайное сообщение</div>
                    <div class="card-subtitle">Отправь анонимно</div>
                </div>
            </div>
        </div>

        <div class="card" onclick="generateFact()">
            <div class="card-header">
                <div class="card-icon orange">✨</div>
                <div>
                    <div class="card-title">Факт про Майю</div>
                    <div class="card-subtitle">ИИ расскажет что-то милое</div>
                </div>
            </div>
        </div>
    `;
}

// ============================================
//              MEMORIES TAB
// ============================================
function renderMemories(container) {
    if (appData.memories.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-emoji">📸</div>
                <div class="empty-state-text">Пока нет воспоминаний.<br>Добавь первое!</div>
                <br>
                <button class="btn btn-primary" onclick="openAddMemoryModal()">📸 Добавить</button>
            </div>
        `;
        return;
    }

    let html = `<div class="section-title">📸 Воспоминания (${appData.memories.length})</div>`;
    html += '<div class="memory-grid">';

    appData.memories.forEach((m, i) => {
        const fileType = m.file_type;
        const text = m.text || '';
        const date = m.event_date ? formatDateShort(m.event_date) : formatDate(m.timestamp);

        if (fileType === 'photo' && m.file_url) {
            html += `
                <div class="memory-cell" onclick="openMemoryDetail(${i})">
                    <img src="${m.file_url}" alt="memory" loading="lazy">
                    <div class="memory-cell-overlay">${date}</div>
                </div>
            `;
        } else {
            const emoji = {video: '🎥', audio: '🎵', document: '📄'}[fileType] || '✍️';
            const preview = text.substring(0, 60) || `${emoji} ${fileType || 'текст'}`;
            html += `
                <div class="memory-cell memory-cell-text" onclick="openMemoryDetail(${i})">
                    <div>
                        <div style="font-size:24px;margin-bottom:8px">${emoji}</div>
                        <div>${preview}</div>
                        <div style="font-size:10px;color:var(--text-secondary);margin-top:6px">${date}</div>
                    </div>
                </div>
            `;
        }
    });

    html += '</div>';
    html += `<button class="btn-add" onclick="openAddMemoryModal()">+</button>`;

    container.innerHTML = html;
}

// ============================================
//              WISHLIST TAB
// ============================================
function renderWishlist(container) {
    if (appData.wishes.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-emoji">🎁</div>
                <div class="empty-state-text">Виш-лист пуст.<br>Добавь первую хотелку!</div>
                <br>
                <button class="btn btn-primary" onclick="openAddModal('wish')">🎁 Добавить</button>
            </div>
        `;
        return;
    }

    let html = `<div class="section-title">🎁 Виш-лист (${appData.wishes.length})</div>`;
    appData.wishes.forEach((wish, i) => {
        html += `
            <div class="list-item">
                <div class="list-item-number">${i + 1}</div>
                <div class="list-item-text">${escapeHtml(wish)}</div>
                <button class="list-item-delete" onclick="deleteItem('wish', ${i})">🗑️</button>
            </div>
        `;
    });
    html += `<button class="btn-add" onclick="openAddModal('wish')">+</button>`;
    container.innerHTML = html;
}

// ============================================
//              QUOTES TAB
// ============================================
function renderQuotes(container) {
    if (appData.quotes.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-emoji">🤣</div>
                <div class="empty-state-text">Нет цитат.<br>Запомни что-то смешное!</div>
                <br>
                <button class="btn btn-primary" onclick="openAddModal('quote')">🤣 Добавить</button>
            </div>
        `;
        return;
    }

    let html = `<div class="section-title">🤣 Цитаты (${appData.quotes.length})</div>`;
    appData.quotes.forEach((quote, i) => {
        html += `
            <div class="list-item">
                <div class="list-item-number">${i + 1}</div>
                <div class="list-item-text">"${escapeHtml(quote)}"</div>
                <button class="list-item-delete" onclick="deleteItem('quote', ${i})">🗑️</button>
            </div>
        `;
    });
    html += `<button class="btn-add" onclick="openAddModal('quote')">+</button>`;
    container.innerHTML = html;
}

// ============================================
//              AI TAB
// ============================================
let chatHistory = [];

function renderAI(container) {
    let html = '<div class="chat-messages" id="chatMessages">';

    if (chatHistory.length === 0) {
        html += `
            <div class="chat-msg bot">
                Привет! 👋 Я ИИ-помощник. Спроси меня что угодно!
            </div>
        `;
    }

    chatHistory.forEach(msg => {
        html += `<div class="chat-msg ${msg.role}">${escapeHtml(msg.text)}</div>`;
    });

    html += '</div>';

    // Remove old chat input if exists
    document.querySelector('.chat-input-wrap')?.remove();

    // Add chat input
    const inputWrap = document.createElement('div');
    inputWrap.className = 'chat-input-wrap visible';
    inputWrap.innerHTML = `
        <input class="chat-input" id="chatInput" type="text" placeholder="Напиши сообщение..." 
               onkeydown="if(event.key==='Enter')sendAIMessage()">
        <button class="chat-send" onclick="sendAIMessage()">➤</button>
    `;
    document.body.appendChild(inputWrap);

    container.innerHTML = html;
    scrollChatBottom();
}

async function sendAIMessage() {
    const input = document.getElementById('chatInput');
    const text = input?.value?.trim();
    if (!text) return;

    input.value = '';
    chatHistory.push({ role: 'user', text });
    renderAI(document.getElementById('content'));

    // Show typing
    const messagesDiv = document.getElementById('chatMessages');
    const typingDiv = document.createElement('div');
    typingDiv.className = 'chat-msg bot';
    typingDiv.id = 'typing';
    typingDiv.textContent = '✍️ Думаю...';
    messagesDiv.appendChild(typingDiv);
    scrollChatBottom();

    const result = await apiPost('/ai', { message: text });

    document.getElementById('typing')?.remove();

    const reply = result?.reply || '❌ Ошибка ИИ';
    chatHistory.push({ role: 'bot', text: reply });
    renderAI(document.getElementById('content'));
}

function scrollChatBottom() {
    const el = document.getElementById('chatMessages');
    if (el) el.scrollTop = el.scrollHeight;
}

// ============================================
//              MODALS
// ============================================
function openAddModal(type) {
    const titles = { wish: '🎁 Новая хотелка', quote: '🤣 Новая цитата' };
    const placeholders = { wish: 'Что хочешь?', quote: 'Что сказали смешного?' };

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-handle"></div>
            <div class="modal-title">${titles[type]}</div>
            <textarea class="modal-input" id="modalInput" placeholder="${placeholders[type]}" rows="3"></textarea>
            <button class="btn btn-primary" onclick="submitAdd('${type}')">Добавить</button>
            <br><br>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Отмена</button>
        </div>
    `;

    document.body.appendChild(overlay);
    setTimeout(() => document.getElementById('modalInput')?.focus(), 300);
}

async function submitAdd(type) {
    const input = document.getElementById('modalInput');
    const text = input?.value?.trim();
    if (!text) return;

    const endpoint = type === 'wish' ? '/wishes' : '/quotes';
    const result = await apiPost(endpoint, { text });

    document.querySelector('.modal-overlay')?.remove();

    if (result?.ok) {
        if (type === 'wish') appData.wishes.push(text);
        else appData.quotes.push(text);
        renderCurrentTab();
        showToast(`✅ Добавлено!`);
    } else {
        showToast('❌ Ошибка');
    }
}

function openAddMemoryModal() {
    const today = new Date().toISOString().split('T')[0];
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-handle"></div>
            <div class="modal-title">📸 Новое воспоминание</div>
            <textarea class="modal-input" id="memoryText" placeholder="Опиши воспоминание..." rows="3"></textarea>
            <div style="margin-bottom:12px">
                <label style="font-size:13px;color:var(--text-secondary);display:block;margin-bottom:6px">📅 Когда это было?</label>
                <input type="date" id="memoryEventDate" value="${today}" max="${today}" class="modal-input" style="min-height:auto;padding:12px 16px">
            </div>
            <input type="file" id="memoryFile" accept="image/*,video/*" style="margin-bottom:12px;color:var(--text-secondary)">
            <button class="btn btn-primary" onclick="submitMemory()">Сохранить 💕</button>
            <br><br>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Отмена</button>
        </div>
    `;

    document.body.appendChild(overlay);
}

async function submitMemory() {
    const text = document.getElementById('memoryText')?.value?.trim() || '';
    const file = document.getElementById('memoryFile')?.files?.[0];
    const eventDate = document.getElementById('memoryEventDate')?.value || '';

    if (!text && !file) {
        showToast('⚠️ Добавь текст или файл');
        return;
    }

    const formData = new FormData();
    formData.append('text', text);
    formData.append('event_date', eventDate);
    if (file) formData.append('file', file);

    try {
        const headers = {};
        if (tg?.initData) headers['X-Telegram-Init-Data'] = tg.initData;

        const memUrl = DEBUG_UID ? `${API_BASE}/memories?uid=${DEBUG_UID}` : `${API_BASE}/memories`;
        const resp = await fetch(memUrl, {
            method: 'POST',
            headers,
            body: formData,
        });
        const result = await resp.json();

        document.querySelector('.modal-overlay')?.remove();

        if (result?.ok) {
            await loadAllData();
            showToast('✅ Воспоминание сохранено! 💕');
        } else {
            showToast('❌ Ошибка');
        }
    } catch (e) {
        showToast('❌ Ошибка сети');
    }
}

// ============================================
//              DELETE
// ============================================
async function deleteItem(type, index) {
    if (!confirm('Удалить?')) return;

    const endpoint = type === 'wish' ? `/wishes/${index}` :
                     type === 'quote' ? `/quotes/${index}` :
                     `/memories/${index}`;

    const result = await apiDelete(endpoint);

    if (result?.ok) {
        if (type === 'wish') appData.wishes.splice(index, 1);
        else if (type === 'quote') appData.quotes.splice(index, 1);
        else appData.memories.splice(index, 1);
        renderCurrentTab();
        showToast('✅ Удалено');
    } else {
        showToast('❌ Ошибка');
    }
}

// ============================================
//              SPECIAL ACTIONS
// ============================================

// --- Установка даты отношений (общая для всех!) ---
function openSetDateModal() {
    const current = appData.relationship?.start_date || '';
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-handle"></div>
            <div class="modal-title">💕 Дата начала отношений</div>
            <p style="color:var(--text-secondary);font-size:13px;margin-bottom:12px;text-align:center">
                Эту дату увидят все пользователи бота
            </p>
            <input type="date" id="relDate" value="${current}" class="modal-input" style="min-height:auto;padding:12px 16px">
            <button class="btn btn-primary" onclick="submitRelDate()">💕 Сохранить</button>
            <br><br>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Отмена</button>
        </div>
    `;
    document.body.appendChild(overlay);
}

async function submitRelDate() {
    const date = document.getElementById('relDate')?.value;
    if (!date) { showToast('⚠️ Выбери дату'); return; }

    const result = await apiPost('/relationship', { date });
    document.querySelector('.modal-overlay')?.remove();

    if (result?.ok) {
        await loadAllData();
        showToast('✅ Дата сохранена! 💕');
    } else {
        showToast('❌ Ошибка');
    }
}

async function generateFact() {
    showToast('✨ Генерирую факт...');
    const result = await apiGet('/fact');
    if (result?.fact) {
        showFactModal(result.fact);
    } else {
        showToast('❌ Ошибка ИИ');
    }
}

function showFactModal(text) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-handle"></div>
            <div class="modal-title">✨ Факт про Майю</div>
            <p style="font-size:15px;line-height:1.6;color:var(--text-primary);margin-bottom:16px">${escapeHtml(text)}</p>
            <button class="btn btn-primary" onclick="this.closest('.modal-overlay').remove()">💕 Круто!</button>
        </div>
    `;
    document.body.appendChild(overlay);
}

function openSecretMessage() {
    const users = [
        { id: 7118929376, name: 'Тёма', emoji: '👦' },
        { id: 1428288113, name: 'Артём', emoji: '🧑' },
        { id: 8481047835, name: 'Майя', emoji: '👩' },
    ];

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    let recipientBtns = users.map(u => `
        <button class="recipient-btn" onclick="selectSecretRecipient(${u.id}, '${u.name}')">
            <div class="recipient-avatar">${u.emoji}</div>
            <div>${u.name}</div>
        </button>
    `).join('');

    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-handle"></div>
            <div class="modal-title">💌 Тайное сообщение</div>
            <p style="color:var(--text-secondary);margin-bottom:16px;text-align:center">Кому отправить?</p>
            <div class="secret-recipients">${recipientBtns}</div>
            <br>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Отмена</button>
        </div>
    `;
    document.body.appendChild(overlay);
}

function selectSecretRecipient(userId, name) {
    document.querySelector('.modal-overlay')?.remove();

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = `
        <div class="modal">
            <div class="modal-handle"></div>
            <div class="modal-title">💌 Для ${name}</div>
            <textarea class="modal-input" id="secretText" placeholder="Напиши тайное сообщение..." rows="3"></textarea>
            <button class="btn btn-primary" onclick="sendSecret(${userId})">Отправить 💌</button>
            <br><br>
            <button class="btn btn-secondary" onclick="this.closest('.modal-overlay').remove()">Отмена</button>
        </div>
    `;
    document.body.appendChild(overlay);
    setTimeout(() => document.getElementById('secretText')?.focus(), 300);
}

async function sendSecret(toUserId) {
    const text = document.getElementById('secretText')?.value?.trim();
    if (!text) return;

    const result = await apiPost('/secret', { to_user_id: toUserId, text });
    document.querySelector('.modal-overlay')?.remove();

    if (result?.ok) {
        showToast('✅ Тайное сообщение отправлено! 💌');
    } else {
        showToast('❌ Ошибка отправки');
    }
}

function openMemoryDetail(index) {
    const m = appData.memories[index];
    if (!m) return;

    const eventDate = m.event_date ? formatDateShort(m.event_date) : null;
    const createdDate = formatDate(m.timestamp);
    const dateDisplay = eventDate
        ? `<div style="font-size:16px;font-weight:600;color:var(--accent-light);margin-bottom:4px">📅 ${eventDate}</div>
           <div style="font-size:11px;color:var(--text-secondary);margin-bottom:12px">Добавлено: ${createdDate}</div>`
        : `<div style="font-size:14px;color:var(--text-secondary);margin-bottom:8px">${createdDate}</div>`;

    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = (e) => { if (e.target === overlay) overlay.remove(); };

    let mediaHtml = '';
    if (m.file_type === 'photo' && m.file_url) {
        mediaHtml = `<img src="${m.file_url}" style="width:100%;border-radius:12px;margin-bottom:12px">`;
    }

    overlay.innerHTML = `
        <div class="modal" style="max-height:90vh;overflow-y:auto">
            <div class="modal-handle"></div>
            ${mediaHtml}
            ${dateDisplay}
            ${m.text ? `<p style="font-size:15px;line-height:1.6;margin-bottom:16px">${escapeHtml(m.text)}</p>` : ''}
            <button class="btn btn-secondary" onclick="deleteItem('memory', ${index}); this.closest('.modal-overlay').remove()">🗑️ Удалить</button>
            <br><br>
            <button class="btn btn-primary" onclick="this.closest('.modal-overlay').remove()">Закрыть</button>
        </div>
    `;
    document.body.appendChild(overlay);
}

// ============================================
//              UTILS
// ============================================
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoString) {
    try {
        const d = new Date(isoString);
        return d.toLocaleDateString('ru-RU', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch {
        return '—';
    }
}

function formatDateShort(dateStr) {
    try {
        // Handle both "2026-01-28" and ISO strings
        const d = new Date(dateStr + (dateStr.length === 10 ? 'T00:00:00' : ''));
        const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                        'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    } catch {
        return dateStr || '—';
    }
}

function showToast(text) {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = text;
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        left: 50%;
        transform: translateX(-50%);
        background: var(--bg-card);
        color: var(--text-primary);
        padding: 12px 24px;
        border-radius: 12px;
        font-size: 14px;
        font-weight: 600;
        z-index: 999;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        animation: fadeIn 0.2s ease;
        border: 1px solid rgba(255,255,255,0.1);
    `;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 2500);
}
