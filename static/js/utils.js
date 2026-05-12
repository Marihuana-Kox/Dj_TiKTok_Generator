// ============================================================================
// ГЛОБАЛЬНЫЕ УТИЛИТЫ — загружаются на всех страницах
// ============================================================================

/** Получить CSRF cookie */
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie) {
        for (let c of document.cookie.split(';')) {
            c = c.trim();
            if (c.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(c.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

/** Показать toast уведомление */
function showToast(message, type = 'success', duration = 4000) {
    const toast = document.getElementById('toast-notification');
    if (!toast) {
        console.log('Toast:', message);
        return;
    }
    const icon = document.getElementById('toast-icon');
    const msg = document.getElementById('toast-message');
    if (icon) icon.innerText = type === 'success' ? '✅' : '❌';
    if (msg) msg.innerText = message;
    toast.classList.remove('d-none');
    setTimeout(() => toast.classList.add('d-none'), duration);
}
