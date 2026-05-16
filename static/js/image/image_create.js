/**
 * Глобальная функция для переключения видимости настроек.
 * Вызывается из HTML: onchange="toggleSettings(false/true)"
 */
window.toggleSettings = function(show) {
    // Находим блок по ID, который указан у тебя в HTML
    const settingsBlock = document.getElementById('manual-settings-block');
    
    if (settingsBlock) {
        if (show) {
            // Если "Ручной" (true) — убираем скрывающий класс Bootstrap d-none
            settingsBlock.classList.remove('d-none');
            console.log('Режим: Ручной (настройки показаны)');
        } else {
            // Если "Авто" (false) — добавляем класс d-none
            settingsBlock.classList.add('d-none');
            console.log('Режим: Авто (настройки скрыты)');
        }
    } else {
        console.error('Ошибка: Элемент #manual-settings-block не найден');
    }
};

(function() {
    console.log('🔍 image_create.js инициализирован');

    const form = document.querySelector('#project-create-form');
    const submitBtn = form?.querySelector('button[type="submit"]');

    if (!form || !submitBtn) return;

    /**
     * Обработка отправки формы
     */
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        submitBtn.disabled = true;
        submitBtn.innerHTML = '⏳ Запуск...';
        
        const formData = new FormData(form);
        const actionUrl = form.dataset.actionUrl || form.getAttribute('action');
        
        fetch(actionUrl, {
            method: 'POST',
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            },
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success && data.task_id) {
                // Запуск универсального прогресс-бара из modal.js
                if (typeof window.startProgressTracking === 'function') {
                    window.openModal('progress-modal');
                    window.startProgressTracking('/images/api/generation-stream/', data.task_id, 'progress-modal');
                    // window.startProgressTracking('/images/api/generation-progress/', data.task_id);
                }
            } else {
                alert('❌ ' + (data.error || 'Ошибка запуска'));
                submitBtn.disabled = false;
                submitBtn.innerHTML = '🚀 Создать проект';
            }
        })
        .catch(error => {
            console.error('Ошибка fetch:', error);
            submitBtn.disabled = false;
            submitBtn.innerHTML = '🚀 Создать проект';
        });
    });

    // Инициализация начального состояния при загрузке (если вдруг страница перезагружена с выбранным ручным режимом)
    const manualRadio = form.querySelector('input[name="gen_mode"][value="manual"]');
    if (manualRadio && manualRadio.checked) {
        window.toggleSettings(true);
    }
})();