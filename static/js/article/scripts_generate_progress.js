/**
 * VIDEO SCRIPT GENERATE — Генерация текста для ролика с прогресс-баром
 * Использует глобальные функции из modal.js и utils.js
 */

document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('video-script-form');
    const submitBtn = form?.querySelector('button[type="submit"]');
    // Обновление code_name промпта при изменении select
    const promptSelect = document.getElementById('id_script_prompt');
    const codeDisplay = document.getElementById('prompt-code-display');
    
    if (promptSelect && codeDisplay) {
        // Функция обновления отображения
        function updateCodeDisplay() {
            const selectedOption = promptSelect.options[promptSelect.selectedIndex];
            const codeName = selectedOption ? selectedOption.value : '';
            codeDisplay.textContent = codeName || 'не выбран';
        }
        
        // Обновляем при изменении
        promptSelect.addEventListener('change', updateCodeDisplay);
        
        // Обновляем при загрузке (на случай если уже что-то выбрано)
        updateCodeDisplay();
        
    }
    if (!form || !submitBtn) {
        console.warn('⚠️ Форма или кнопка не найдены');
        return;
    }

    // Обработка отправки формы
    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        // Проверка: выбрано ли исследование
        const researchSelect = document.querySelector('select[name="research_project"]');
        if (!researchSelect || !researchSelect.value) {
            showToast('⚠️ Выберите исследование', 'error');
            return;
        }
        
        // Блокируем кнопку
        submitBtn.disabled = true;
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Запуск...';
        
        // Собираем данные формы
        const formData = new FormData(form);
        
        // Отправляем AJAX запрос
        fetch(form.action || window.location.href, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => {
            // Проверяем, что сервер вернул JSON
            const contentType = response.headers.get('content-type');
            if (!contentType || !contentType.includes('application/json')) {
                return response.text().then(text => {
                    console.error('❌ Сервер вернул HTML вместо JSON:', text.substring(0, 500));
                    throw new Error('Сервер вернул ошибку ' + response.status);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok' && data.task_id) {
                // ✅ УСПЕХ: передаём управление в modal.js
                console.log('✅ Задача запущена, task_id:', data.task_id);
                
                if (typeof window.startProgressTracking === 'function') {
                    // Используем URL стрима из window или data
                    const streamUrl = data.stream_url || window.VIDEO_SCRIPT_STREAM_URL || '/article/api/generation-stream/';
                    
                    window.startProgressTracking(
                        streamUrl,
                        data.task_id,
                        'progress-modal', // ID модального окна
                        null, // callback (не нужен)
                        null  // cancelUrl (не нужен)
                    );
                } else {
                    console.error('❌ modal.js не загружен или функция startProgressTracking отсутствует');
                    showToast('❌ Ошибка: система прогресса не загружена', 'error');
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = originalBtnText;
                }
            } else {
                // ❌ Ошибка от сервера
                console.error('❌ Ошибка запуска:', data);
                showToast(data.message || 'Ошибка запуска генерации', 'error');
                
                if (data.errors) {
                    // Показываем ошибки формы
                    Object.values(data.errors).forEach(err => {
                        showToast(err[0] || err, 'error');
                    });
                }
                
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
        })
        .catch(error => {
            // 🚨 Критическая ошибка сети
            console.error('❌ Ошибка выполнения:', error);
            showToast('Критическая ошибка при отправке формы', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        });
    });
    console.log('✅ video_script_generate.js загружен и готов к работе');
});