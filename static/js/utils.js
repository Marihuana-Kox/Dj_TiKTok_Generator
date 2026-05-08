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

/** Открыть модалку по ID */
// function openModal(modalId) {
//     const modal = document.getElementById(modalId);
//     if (modal) {
//         modal.classList.remove('d-none');
//         modal.style.visibility = 'visible';
//         modal.style.display = 'flex';
//     }
// }

// /** Закрыть модалку по ID */
// function closeModal(modalId) {
//     const modal = document.getElementById(modalId);
//     if (modal) {
//         modal.classList.remove('active');
//         // Ждем завершения анимации (300ms) потом скрываем
//         setTimeout(() => {
//                 modal.classList.add('d-none');
//         }, 300);
//     }
// }


// /** Обновить прогресс бар */
// function updateProgress(percent, message, modalId) {
//     const modal = document.getElementById(modalId || 'progress-modal');
//     if (!modal) return;
    
//     const progressBar = document.getElementById('gen-progress-bar');
//     const progressPercent = document.getElementById('gen-progress-percent');
//     const progressMessage = document.getElementById('gen-progress-message');
    
//     if (progressBar) {
//         progressBar.style.width = percent + '%';
//         progressBar.setAttribute('aria-valuenow', percent);
//     }
//     if (progressPercent) progressPercent.textContent = percent + '%';
//     if (progressMessage && message) progressMessage.textContent = message;
// }

// /** Завершить прогресс */
// function finishProgress(success, message, redirectUrl = null, redirectDelay = 2000) {
//     const progressBar = document.getElementById('gen-progress-bar');
//     const statusText = document.getElementById('gen-progress-message');
    
//     if (progressBar) {
//         progressBar.classList.remove('progress-bar-animated');
//         if (success) {
//             progressBar.classList.add('bg-success');
//             progressBar.style.width = '100%';
//         } else {
//             progressBar.classList.add('bg-danger');
//         }
//     }
//     if (statusText) statusText.textContent = message;
    
//     if (success && redirectUrl) {
//         setTimeout(() => window.location.href = redirectUrl, redirectDelay);
//     }
// }
// /** Добавление лога в прогресс */
// function addProgressLog(message, type = 'info') {
//     const log = document.getElementById('gen-progress-log');
//     if (!log) return;
    
//     const li = document.createElement('li');
//     li.textContent = message;
//     li.className = type; // success, error, info
//     li.style.padding = '6px 8px';
//     li.style.borderBottom = '1px solid #e9ecef';
//     li.style.color = type === 'error' ? '#ef4444' : (type === 'success' ? '#4caf50' : '#495057');
//     log.appendChild(li);
//     log.scrollTop = log.scrollHeight;
// }
// function testProgressModal() {
//     console.log('🧪 Тест запущен');
    
//     // Открываем СУЩЕСТВУЮЩУЮ модалку
//     openModal('progress-modal');
    
//     // Сброс
//     updateProgress(0, 'Инициализация...');
    
//     // Симуляция шагов
//     const steps = [
//         { percent: 10, message: 'Подготовка...', delay: 800 },
//         { percent: 25, message: 'Анализ текста...', delay: 1000 },
//         { percent: 40, message: 'Генерация промптов...', delay: 1200 },
//         { percent: 55, message: 'Подключение к API...', delay: 800 },
//         { percent: 70, message: 'Генерация изображений...', delay: 1500 },
//         { percent: 85, message: 'Обработка результатов...', delay: 800 },
//         { percent: 95, message: 'Финализация...', delay: 500 },
//         { percent: 100, message: '✅ Готово!', delay: 300 }
//     ];
    
//     let i = 0;
//     function run() {
//         if (i >= steps.length) {
//             finishProgress(true, '✅ Тест завершён!', null, 2000);
//             return;
//         }
//         const s = steps[i];
//         updateProgress(s.percent, s.message);
//         addProgressLog(s.message, 'info');
//         i++;
//         setTimeout(run, s.delay);
//     }
//     run();
// }
// console.log('✅ utils.js загруен');