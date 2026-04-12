/* ============================================
   TELEGRAM MINI APP — PISKA BOT
   Main Application Logic
   v4.1.1 — Android Compatible (no optional chaining)
   ============================================ */

// --- Helper: safe property access ---
function _g(obj) {
    for (var i = 1; i < arguments.length; i++) {
        if (obj == null) return undefined;
        obj = obj[arguments[i]];
    }
    return obj;
}

// --- Safe element remove helper ---
function _removeEl(selector) {
    var el = document.querySelector(selector);
    if (el) el.remove();
}

function _removeById(id) {
    var el = document.getElementById(id);
    if (el) el.remove();
}

// --- Safe element focus helper ---
function _focusEl(id) {
    var el = document.getElementById(id);
    if (el) el.focus();
}

// --- Telegram WebApp SDK ---
var tg = null;
try {
    tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (tg) {
        tg.ready();
        tg.expand();
        if (typeof tg.enableClosingConfirmation === 'function') {
            tg.enableClosingConfirmation();
        }
        // Адаптируем цвета под тему Telegram
        if (tg.themeParams) {
            document.documentElement.style.setProperty('--bg-primary', tg.themeParams.bg_color || '#1a1a2e');
            document.documentElement.style.setProperty('--bg-secondary', tg.themeParams.secondary_bg_color || '#16213e');
            document.documentElement.style.setProperty('--text-primary', tg.themeParams.text_color || '#ffffff');
            document.documentElement.style.setProperty('--text-secondary', tg.themeParams.hint_color || '#8892b0');
        }
    }
} catch (e) {
    console.warn('Telegram WebApp SDK not available:', e);
}

// --- API BASE URL ---
var API_BASE = window.location.origin + '/api';

// --- USER ID: берём из Telegram SDK или из URL параметра (для дебага) ---
var TG_USER_ID = _g(tg, 'initDataUnsafe', 'user', 'id') || '';
var DEBUG_UID = new URLSearchParams(window.location.search).get('uid') || '';
var USER_ID = TG_USER_ID || DEBUG_UID || '';

// --- STATE ---
var currentTab = 'home';
var appData = {
    wishes: [],
    quotes: [],
    memories: [],
    relationship: null,
    user: null,
};

// --- INIT ---
document.addEventListener('DOMContentLoaded', function() {
    loadAllData();
    switchTab('home');
});

// ============================================
//                API CALLS
// ============================================
function _getInitData() {
    return (tg && tg.initData) ? tg.initData : '';
}

async function apiGet(endpoint) {
    try {
        var headers = {};
        var initData = _getInitData();
        if (initData) {
            headers['X-Telegram-Init-Data'] = initData;
        }
        var sep = endpoint.includes('?') ? '&' : '?';
        var url = USER_ID ? (API_BASE + endpoint + sep + 'uid=' + USER_ID) : (API_BASE + endpoint);
        var resp = await fetch(url, { headers: headers });
        if (!resp.ok) {
            var errText = await resp.text();
            console.error('API GET ' + endpoint + ': HTTP ' + resp.status, errText);
            throw new Error('HTTP ' + resp.status);
        }
        return await resp.json();
    } catch (e) {
        console.error('API GET ' + endpoint + ':', e);
        return null;
    }
}

async function apiPost(endpoint, body) {
    try {
        var headers = { 'Content-Type': 'application/json' };
        var initData = _getInitData();
        if (initData) {
            headers['X-Telegram-Init-Data'] = initData;
        }
        var sep = endpoint.includes('?') ? '&' : '?';
        var url = USER_ID ? (API_BASE + endpoint + sep + 'uid=' + USER_ID) : (API_BASE + endpoint);
        var resp = await fetch(url, {
            method: 'POST',
            headers: headers,
            body: JSON.stringify(body),
        });
        if (!resp.ok) {
            var errText = await resp.text();
            console.error('API POST ' + endpoint + ': HTTP ' + resp.status, errText);
            throw new Error('HTTP ' + resp.status);
        }
        return await resp.json();
    } catch (e) {
        console.error('API POST ' + endpoint + ':', e);
        return null;
    }
}

async function apiDelete(endpoint) {
    try {
        var headers = {};
        var initData = _getInitData();
        if (initData) {
            headers['X-Telegram-Init-Data'] = initData;
        }
        var sep = endpoint.includes('?') ? '&' : '?';
        var url = USER_ID ? (API_BASE + endpoint + sep + 'uid=' + USER_ID) : (API_BASE + endpoint);
        var resp = await fetch(url, { method: 'DELETE', headers: headers });
        if (!resp.ok) {
            var errText = await resp.text();
            console.error('API DELETE ' + endpoint + ': HTTP ' + resp.status, errText);
            throw new Error('HTTP ' + resp.status);
        }
        return await resp.json();
    } catch (e) {
        console.error('API DELETE ' + endpoint + ':', e);
        return null;
    }
}

// ============================================
//              LOAD DATA
// ============================================
async function loadAllData() {
    var results = await Promise.all([
        apiGet('/wishes'),
        apiGet('/quotes'),
        apiGet('/memories'),
        apiGet('/relationship'),
    ]);
    var wishes = results[0];
    var quotes = results[1];
    var memories = results[2];
    var relationship = results[3];

    appData.wishes = (wishes && wishes.data) ? wishes.data : [];
    appData.quotes = (quotes && quotes.data) ? quotes.data : [];
    appData.memories = (memories && memories.data) ? memories.data : [];
    appData.relationship = (relationship && relationship.data) ? relationship.data : null;
    appData.myUid = (wishes && wishes.my_uid) ? wishes.my_uid : String(USER_ID);

    updateRelationshipCounter();
    renderCurrentTab();
}

function updateRelationshipCounter() {
    var el = document.getElementById('relationship-counter');
    if (!appData.relationship || !appData.relationship.days) {
        el.textContent = '💕';
        return;
    }
    el.textContent = 'Вместе ' + appData.relationship.days + ' дней 💕';
}

// ============================================
//              TAB SWITCHING
// ============================================
function switchTab(tab) {
    currentTab = tab;

    // Update tab bar
    document.querySelectorAll('.tab').forEach(function(t) { t.classList.remove('active'); });
    var activeTab = document.querySelector('[data-tab="' + tab + '"]');
    if (activeTab) activeTab.classList.add('active');

    // Toggle chat input
    var chatInput = document.querySelector('.chat-input-wrap');
    if (chatInput) chatInput.classList.toggle('visible', tab === 'ai');

    renderCurrentTab();
}

function renderCurrentTab() {
    var content = document.getElementById('content');
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
    var rel = appData.relationship;
    var daysText = (rel && rel.days) ? rel.days : '—';
    var dateText = (rel && rel.start_date) ? formatDateShort(rel.start_date) : 'Не установлена';

    // Кнопка изменить дату
    var dateAction = (rel && rel.start_date)
        ? '<div class="relationship-edit" onclick="openSetDateModal()">✏️ Изменить дату</div>'
        : '<button class="btn btn-primary" style="margin-top:12px;max-width:200px;margin-left:auto;margin-right:auto" onclick="openSetDateModal()">💕 Установить дату</button>';

    container.innerHTML = '' +
        '<div class="card relationship-card">' +
            '<div class="relationship-days">' + daysText + '</div>' +
            '<div class="relationship-label">дней вместе</div>' +
            '<div class="relationship-date">С ' + dateText + '</div>' +
            dateAction +
        '</div>' +
        '<div class="stats-row">' +
            '<div class="stat-card">' +
                '<div class="stat-number">' + appData.memories.length + '</div>' +
                '<div class="stat-label">Воспоминаний</div>' +
            '</div>' +
            '<div class="stat-card">' +
                '<div class="stat-number">' + appData.wishes.length + '</div>' +
                '<div class="stat-label">Хотелок</div>' +
            '</div>' +
            '<div class="stat-card">' +
                '<div class="stat-number">' + appData.quotes.length + '</div>' +
                '<div class="stat-label">Цитат</div>' +
            '</div>' +
            '<div class="stat-card" onclick="switchTab(\'ai\')">' +
                '<div class="stat-number">🤖</div>' +
                '<div class="stat-label">Спросить ИИ</div>' +
            '</div>' +
        '</div>' +
        '<div class="section-title">Быстрые действия</div>' +
        '<div class="card" onclick="switchTab(\'memories\')">' +
            '<div class="card-header">' +
                '<div class="card-icon pink">📸</div>' +
                '<div>' +
                    '<div class="card-title">Добавить воспоминание</div>' +
                    '<div class="card-subtitle">Фото, видео или текст</div>' +
                '</div>' +
            '</div>' +
        '</div>' +
        '<div class="card" onclick="openAddModal(\'wish\')">' +
            '<div class="card-header">' +
                '<div class="card-icon blue">🎁</div>' +
                '<div>' +
                    '<div class="card-title">В виш-лист</div>' +
                    '<div class="card-subtitle">Добавь свою хотелку</div>' +
                '</div>' +
            '</div>' +
        '</div>' +
        '<div class="card" onclick="openAddModal(\'quote\')">' +
            '<div class="card-header">' +
                '<div class="card-icon green">🤣</div>' +
                '<div>' +
                    '<div class="card-title">В цитаты</div>' +
                    '<div class="card-subtitle">Запомни смешное</div>' +
                '</div>' +
            '</div>' +
        '</div>' +
        '<div class="card" onclick="openSecretMessage()">' +
            '<div class="card-header">' +
                '<div class="card-icon purple">💌</div>' +
                '<div>' +
                    '<div class="card-title">Тайное сообщение</div>' +
                    '<div class="card-subtitle">Отправь анонимно</div>' +
                '</div>' +
            '</div>' +
        '</div>' +
        '<div class="card" onclick="generateFact()">' +
            '<div class="card-header">' +
                '<div class="card-icon orange">✨</div>' +
                '<div>' +
                    '<div class="card-title">Факт про Майю</div>' +
                    '<div class="card-subtitle">ИИ расскажет что-то милое</div>' +
                '</div>' +
            '</div>' +
        '</div>';
}

// ============================================
//              MEMORIES TAB
// ============================================
function renderMemories(container) {
    if (appData.memories.length === 0) {
        container.innerHTML = '' +
            '<div class="empty-state">' +
                '<div class="empty-state-emoji">📸</div>' +
                '<div class="empty-state-text">Пока нет воспоминаний.<br>Добавь первое!</div>' +
                '<br>' +
                '<button class="btn btn-primary" onclick="openAddMemoryModal()">📸 Добавить</button>' +
            '</div>';
        return;
    }

    var html = '<div class="section-title">📸 Воспоминания (' + appData.memories.length + ')</div>';
    html += '<div class="memory-grid">';

    appData.memories.forEach(function(m, i) {
        var fileType = m.file_type;
        var text = m.text || '';
        var date = m.event_date ? formatDateShort(m.event_date) : formatDate(m.timestamp);

        if (fileType === 'photo' && m.file_url) {
            html += '' +
                '<div class="memory-cell" onclick="openMemoryDetail(' + i + ')">' +
                    '<img src="' + m.file_url + '" alt="memory" loading="lazy">' +
                    '<div class="memory-cell-overlay">' + date + '</div>' +
                '</div>';
        } else {
            var emojiMap = {video: '🎥', audio: '🎵', document: '📄'};
            var emoji = emojiMap[fileType] || '✍️';
            var preview = text.substring(0, 60) || (emoji + ' ' + (fileType || 'текст'));
            html += '' +
                '<div class="memory-cell memory-cell-text" onclick="openMemoryDetail(' + i + ')">' +
                    '<div>' +
                        '<div style="font-size:24px;margin-bottom:8px">' + emoji + '</div>' +
                        '<div>' + preview + '</div>' +
                        '<div style="font-size:10px;color:var(--text-secondary);margin-top:6px">' + date + '</div>' +
                    '</div>' +
                '</div>';
        }
    });

    html += '</div>';
    html += '<button class="btn-add" onclick="openAddMemoryModal()">+</button>';

    container.innerHTML = html;
}

// ============================================
//              WISHLIST TAB
// ============================================
function renderWishlist(container) {
    if (appData.wishes.length === 0) {
        container.innerHTML = '' +
            '<div class="empty-state">' +
                '<div class="empty-state-emoji">🎁</div>' +
                '<div class="empty-state-text">Виш-лист пуст.<br>Добавь первую хотелку!</div>' +
                '<br>' +
                '<button class="btn btn-primary" onclick="openAddModal(\'wish\')">🎁 Добавить</button>' +
            '</div>';
        return;
    }

    var html = '<div class="section-title">🎁 Виш-лист (' + appData.wishes.length + ')</div>';
    appData.wishes.forEach(function(wish, i) {
        var text = typeof wish === 'string' ? wish : wish.text;
        var author = wish.author || '';
        var ownerUid = wish.uid || appData.myUid;
        var sameOwner = appData.wishes.filter(function(w) { return (w.uid || appData.myUid) === ownerUid; });
        var realIdx = sameOwner.indexOf(wish);
        html += '' +
            '<div class="list-item">' +
                '<div class="list-item-number">' + (i + 1) + '</div>' +
                '<div class="list-item-text">' +
                    escapeHtml(text) +
                    '<div style="font-size:11px;color:var(--text-secondary);margin-top:4px">— ' + escapeHtml(author) + '</div>' +
                '</div>' +
                '<button class="list-item-delete" onclick="deleteSharedItem(\'wish\', ' + realIdx + ', \'' + ownerUid + '\')">🗑️</button>' +
            '</div>';
    });
    html += '<button class="btn-add" onclick="openAddModal(\'wish\')">+</button>';
    container.innerHTML = html;
}

// ============================================
//              QUOTES TAB
// ============================================
function renderQuotes(container) {
    if (appData.quotes.length === 0) {
        container.innerHTML = '' +
            '<div class="empty-state">' +
                '<div class="empty-state-emoji">🤣</div>' +
                '<div class="empty-state-text">Нет цитат.<br>Запомни что-то смешное!</div>' +
                '<br>' +
                '<button class="btn btn-primary" onclick="openAddModal(\'quote\')">🤣 Добавить</button>' +
            '</div>';
        return;
    }

    var html = '<div class="section-title">🤣 Цитаты (' + appData.quotes.length + ')</div>';
    appData.quotes.forEach(function(quote, i) {
        var text = typeof quote === 'string' ? quote : quote.text;
        var author = quote.author || '';
        var ownerUid = quote.uid || appData.myUid;
        var sameOwner = appData.quotes.filter(function(q) { return (q.uid || appData.myUid) === ownerUid; });
        var realIdx = sameOwner.indexOf(quote);
        html += '' +
            '<div class="list-item">' +
                '<div class="list-item-number">' + (i + 1) + '</div>' +
                '<div class="list-item-text">' +
                    '"' + escapeHtml(text) + '"' +
                    '<div style="font-size:11px;color:var(--text-secondary);margin-top:4px">— добавил(а) ' + escapeHtml(author) + '</div>' +
                '</div>' +
                '<button class="list-item-delete" onclick="deleteSharedItem(\'quote\', ' + realIdx + ', \'' + ownerUid + '\')">🗑️</button>' +
            '</div>';
    });
    html += '<button class="btn-add" onclick="openAddModal(\'quote\')">+</button>';
    container.innerHTML = html;
}

// ============================================
//              AI TAB
// ============================================
var chatHistory = [];

function renderAI(container) {
    var html = '<div class="chat-messages" id="chatMessages">';

    if (chatHistory.length === 0) {
        html += '<div class="chat-msg bot">Привет! 👋 Я ИИ-помощник. Спроси меня что угодно!</div>';
    }

    chatHistory.forEach(function(msg) {
        html += '<div class="chat-msg ' + msg.role + '">' + escapeHtml(msg.text) + '</div>';
    });

    html += '</div>';

    // Remove old chat input if exists
    _removeEl('.chat-input-wrap');

    // Add chat input
    var inputWrap = document.createElement('div');
    inputWrap.className = 'chat-input-wrap visible';
    inputWrap.innerHTML = '' +
        '<input class="chat-input" id="chatInput" type="text" placeholder="Напиши сообщение..." ' +
               'onkeydown="if(event.key===\'Enter\')sendAIMessage()">' +
        '<button class="chat-send" onclick="sendAIMessage()">➤</button>';
    document.body.appendChild(inputWrap);

    container.innerHTML = html;
    scrollChatBottom();
}

async function sendAIMessage() {
    var input = document.getElementById('chatInput');
    var text = (input && input.value) ? input.value.trim() : '';
    if (!text) return;

    input.value = '';
    chatHistory.push({ role: 'user', text: text });
    renderAI(document.getElementById('content'));

    // Show typing
    var messagesDiv = document.getElementById('chatMessages');
    var typingDiv = document.createElement('div');
    typingDiv.className = 'chat-msg bot';
    typingDiv.id = 'typing';
    typingDiv.textContent = '✍️ Думаю...';
    messagesDiv.appendChild(typingDiv);
    scrollChatBottom();

    var result = await apiPost('/ai', { message: text });

    _removeById('typing');

    var reply = (result && result.reply) ? result.reply : '❌ Ошибка ИИ';
    chatHistory.push({ role: 'bot', text: reply });
    renderAI(document.getElementById('content'));
}

function scrollChatBottom() {
    var el = document.getElementById('chatMessages');
    if (el) el.scrollTop = el.scrollHeight;
}

// ============================================
//              MODALS
// ============================================
function openAddModal(type) {
    var titles = { wish: '🎁 Новая хотелка', quote: '🤣 Новая цитата' };
    var placeholders = { wish: 'Что хочешь?', quote: 'Что сказали смешного?' };

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = '' +
        '<div class="modal">' +
            '<div class="modal-handle"></div>' +
            '<div class="modal-title">' + titles[type] + '</div>' +
            '<textarea class="modal-input" id="modalInput" placeholder="' + placeholders[type] + '" rows="3"></textarea>' +
            '<button class="btn btn-primary" onclick="submitAdd(\'' + type + '\')">Добавить</button>' +
            '<br><br>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Отмена</button>' +
        '</div>';

    document.body.appendChild(overlay);
    setTimeout(function() { _focusEl('modalInput'); }, 300);
}

async function submitAdd(type) {
    var input = document.getElementById('modalInput');
    var text = (input && input.value) ? input.value.trim() : '';
    if (!text) return;

    var endpoint = type === 'wish' ? '/wishes' : '/quotes';
    var result = await apiPost(endpoint, { text: text });

    _removeEl('.modal-overlay');

    if (result && result.ok) {
        await loadAllData();
        showToast('✅ Добавлено!');
    } else {
        showToast('❌ Ошибка');
    }
}

function openAddMemoryModal() {
    var today = new Date().toISOString().split('T')[0];
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = '' +
        '<div class="modal">' +
            '<div class="modal-handle"></div>' +
            '<div class="modal-title">📸 Новое воспоминание</div>' +
            '<textarea class="modal-input" id="memoryText" placeholder="Опиши воспоминание..." rows="3"></textarea>' +
            '<div style="margin-bottom:12px">' +
                '<label style="font-size:13px;color:var(--text-secondary);display:block;margin-bottom:6px">📅 Когда это было?</label>' +
                '<input type="date" id="memoryEventDate" value="' + today + '" max="' + today + '" class="modal-input" style="min-height:auto;padding:12px 16px">' +
            '</div>' +
            '<input type="file" id="memoryFile" accept="image/*,video/*" style="margin-bottom:12px;color:var(--text-secondary)">' +
            '<button class="btn btn-primary" onclick="submitMemory()">Сохранить 💕</button>' +
            '<br><br>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Отмена</button>' +
        '</div>';

    document.body.appendChild(overlay);
}

async function submitMemory() {
    var memTextEl = document.getElementById('memoryText');
    var text = (memTextEl && memTextEl.value) ? memTextEl.value.trim() : '';
    var memFileEl = document.getElementById('memoryFile');
    var file = (memFileEl && memFileEl.files && memFileEl.files.length > 0) ? memFileEl.files[0] : null;
    var memDateEl = document.getElementById('memoryEventDate');
    var eventDate = (memDateEl && memDateEl.value) ? memDateEl.value : '';

    if (!text && !file) {
        showToast('⚠️ Добавь текст или файл');
        return;
    }

    var formData = new FormData();
    formData.append('text', text);
    formData.append('event_date', eventDate);
    if (file) formData.append('file', file);

    try {
        var headers = {};
        var initData = _getInitData();
        if (initData) headers['X-Telegram-Init-Data'] = initData;

        var memUrl = USER_ID ? (API_BASE + '/memories?uid=' + USER_ID) : (API_BASE + '/memories');
        var resp = await fetch(memUrl, {
            method: 'POST',
            headers: headers,
            body: formData,
        });
        var result = await resp.json();

        _removeEl('.modal-overlay');

        if (result && result.ok) {
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

    var endpoint = type === 'wish' ? ('/wishes/' + index) :
                   type === 'quote' ? ('/quotes/' + index) :
                   ('/memories/' + index);

    var result = await apiDelete(endpoint);

    if (result && result.ok) {
        await loadAllData();
        showToast('✅ Удалено');
    } else {
        showToast('❌ Ошибка');
    }
}

async function deleteSharedItem(type, index, ownerUid) {
    if (!confirm('Удалить?')) return;

    var base = type === 'wish' ? 'wishes' : 'quotes';
    var endpoint = '/' + base + '/' + index + '?owner=' + ownerUid;

    var result = await apiDelete(endpoint);

    if (result && result.ok) {
        await loadAllData();
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
    var current = (appData.relationship && appData.relationship.start_date) ? appData.relationship.start_date : '';
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = '' +
        '<div class="modal">' +
            '<div class="modal-handle"></div>' +
            '<div class="modal-title">💕 Дата начала отношений</div>' +
            '<p style="color:var(--text-secondary);font-size:13px;margin-bottom:12px;text-align:center">' +
                'Эту дату увидят все пользователи бота' +
            '</p>' +
            '<input type="date" id="relDate" value="' + current + '" class="modal-input" style="min-height:auto;padding:12px 16px">' +
            '<button class="btn btn-primary" onclick="submitRelDate()">💕 Сохранить</button>' +
            '<br><br>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Отмена</button>' +
        '</div>';
    document.body.appendChild(overlay);
}

async function submitRelDate() {
    var relDateEl = document.getElementById('relDate');
    var date = (relDateEl && relDateEl.value) ? relDateEl.value : '';
    if (!date) { showToast('⚠️ Выбери дату'); return; }

    var result = await apiPost('/relationship', { date: date });
    _removeEl('.modal-overlay');

    if (result && result.ok) {
        await loadAllData();
        showToast('✅ Дата сохранена! 💕');
    } else {
        showToast('❌ Ошибка');
    }
}

async function generateFact() {
    showToast('✨ Генерирую факт...');
    var result = await apiGet('/fact');
    if (result && result.fact) {
        showFactModal(result.fact);
    } else {
        showToast('❌ Ошибка ИИ');
    }
}

function showFactModal(text) {
    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = '' +
        '<div class="modal">' +
            '<div class="modal-handle"></div>' +
            '<div class="modal-title">✨ Факт про Майю</div>' +
            '<p style="font-size:15px;line-height:1.6;color:var(--text-primary);margin-bottom:16px">' + escapeHtml(text) + '</p>' +
            '<button class="btn btn-primary" onclick="this.closest(\'.modal-overlay\').remove()">💕 Круто!</button>' +
        '</div>';
    document.body.appendChild(overlay);
}

function openSecretMessage() {
    var users = [
        { id: 7118929376, name: 'Тёма', emoji: '👦' },
        { id: 8481047835, name: 'Майя', emoji: '👩' },
    ];

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    var recipientBtns = users.map(function(u) {
        return '' +
            '<button class="recipient-btn" onclick="selectSecretRecipient(' + u.id + ', \'' + u.name + '\')">' +
                '<div class="recipient-avatar">' + u.emoji + '</div>' +
                '<div>' + u.name + '</div>' +
            '</button>';
    }).join('');

    overlay.innerHTML = '' +
        '<div class="modal">' +
            '<div class="modal-handle"></div>' +
            '<div class="modal-title">💌 Тайное сообщение</div>' +
            '<p style="color:var(--text-secondary);margin-bottom:16px;text-align:center">Кому отправить?</p>' +
            '<div class="secret-recipients">' + recipientBtns + '</div>' +
            '<br>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Отмена</button>' +
        '</div>';
    document.body.appendChild(overlay);
}

function selectSecretRecipient(userId, name) {
    _removeEl('.modal-overlay');

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    overlay.innerHTML = '' +
        '<div class="modal">' +
            '<div class="modal-handle"></div>' +
            '<div class="modal-title">💌 Для ' + name + '</div>' +
            '<textarea class="modal-input" id="secretText" placeholder="Напиши тайное сообщение..." rows="3"></textarea>' +
            '<button class="btn btn-primary" onclick="sendSecret(' + userId + ')">Отправить 💌</button>' +
            '<br><br>' +
            '<button class="btn btn-secondary" onclick="this.closest(\'.modal-overlay\').remove()">Отмена</button>' +
        '</div>';
    document.body.appendChild(overlay);
    setTimeout(function() { _focusEl('secretText'); }, 300);
}

async function sendSecret(toUserId) {
    var secretEl = document.getElementById('secretText');
    var text = (secretEl && secretEl.value) ? secretEl.value.trim() : '';
    if (!text) return;

    var result = await apiPost('/secret', { to_user_id: toUserId, text: text });
    _removeEl('.modal-overlay');

    if (result && result.ok) {
        showToast('✅ Тайное сообщение отправлено! 💌');
    } else {
        showToast('❌ Ошибка отправки');
    }
}

function openMemoryDetail(index) {
    var m = appData.memories[index];
    if (!m) return;

    var eventDate = m.event_date ? formatDateShort(m.event_date) : null;
    var createdDate = formatDate(m.timestamp);
    var dateDisplay = eventDate
        ? '<div style="font-size:16px;font-weight:600;color:var(--accent-light);margin-bottom:4px">📅 ' + eventDate + '</div>' +
          '<div style="font-size:11px;color:var(--text-secondary);margin-bottom:12px">Добавлено: ' + createdDate + '</div>'
        : '<div style="font-size:14px;color:var(--text-secondary);margin-bottom:8px">' + createdDate + '</div>';

    var overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.onclick = function(e) { if (e.target === overlay) overlay.remove(); };

    var mediaHtml = '';
    if (m.file_type === 'photo' && m.file_url) {
        mediaHtml = '<img src="' + m.file_url + '" style="width:100%;border-radius:12px;margin-bottom:12px">';
    }

    overlay.innerHTML = '' +
        '<div class="modal" style="max-height:90vh;overflow-y:auto">' +
            '<div class="modal-handle"></div>' +
            mediaHtml +
            dateDisplay +
            (m.text ? '<p style="font-size:15px;line-height:1.6;margin-bottom:16px">' + escapeHtml(m.text) + '</p>' : '') +
            '<button class="btn btn-secondary" onclick="deleteItem(\'memory\', ' + index + '); this.closest(\'.modal-overlay\').remove()">🗑️ Удалить</button>' +
            '<br><br>' +
            '<button class="btn btn-primary" onclick="this.closest(\'.modal-overlay\').remove()">Закрыть</button>' +
        '</div>';
    document.body.appendChild(overlay);
}

// ============================================
//              UTILS
// ============================================
function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(isoString) {
    try {
        var d = new Date(isoString);
        return d.toLocaleDateString('ru-RU', {
            day: '2-digit', month: '2-digit', year: 'numeric',
            hour: '2-digit', minute: '2-digit',
        });
    } catch (e) {
        return '—';
    }
}

function formatDateShort(dateStr) {
    try {
        var d = new Date(dateStr + (dateStr.length === 10 ? 'T00:00:00' : ''));
        var months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                      'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
        return d.getDate() + ' ' + months[d.getMonth()] + ' ' + d.getFullYear();
    } catch (e) {
        return dateStr || '—';
    }
}

function showToast(text) {
    var existing = document.querySelector('.toast');
    if (existing) existing.remove();

    var toast = document.createElement('div');
    toast.className = 'toast';
    toast.textContent = text;
    toast.style.cssText = '' +
        'position: fixed;' +
        'top: 20px;' +
        'left: 50%;' +
        'transform: translateX(-50%);' +
        'background: var(--bg-card);' +
        'color: var(--text-primary);' +
        'padding: 12px 24px;' +
        'border-radius: 12px;' +
        'font-size: 14px;' +
        'font-weight: 600;' +
        'z-index: 999;' +
        'box-shadow: 0 4px 20px rgba(0,0,0,0.3);' +
        'animation: fadeIn 0.2s ease;' +
        'border: 1px solid rgba(255,255,255,0.1);';
    document.body.appendChild(toast);
    setTimeout(function() { toast.remove(); }, 2500);
}
