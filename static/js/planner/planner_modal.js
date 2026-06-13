
//  СКРИПТ ДЛЯ СВЯЗИ ФОРМЫ С ГЛОБАЛЬНЫМ PROGRESSBAR (modal.js)
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('generate-form');
    if (!form) return;

    form.addEventListener('submit', async function(e) {
        e.preventDefault(); // Останавливаем стандартную перезагрузку страницы

        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '⏳ Запуск...';

        const formData = new FormData(form);
        const csrf = typeof getCookie === 'function' ? getCookie('csrftoken') : '';

        try {
            // Отправляем данные через fetch с заголовком, который ждет views.py
            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest' 
                }
            });

            const data = await response.json();

            if (data.status === 'ok' && data.task_id) {
                // Формируем URL для SSE потока (должен совпадать с твоим urls.py)
                const streamUrl = `/planner/generate_stream/?task_id=${data.task_id}`;

                // Запускаем глобальную модалку из modal.js
                window.startProgressTracking(
                    streamUrl,
                    data.task_id,
                    'progress-modal', // ID твоего глобального модального окна
                    function(result) {
                        // Колбэк после завершения (встроенная задержка 3 сек уже есть в modal.js)
                        if (result.success && result.redirectUrl) {
                            window.location.href = result.redirectUrl;
                        }
                    }
                );
            } else {
                showToast(data.errors ? JSON.stringify(data.errors) : 'Ошибка запуска', 'error');
                btn.disabled = false;
                btn.innerHTML = originalText;
            }
        } catch (error) {
            console.error('Ошибка сети:', error);
            showToast('Ошибка сети. Проверьте консоль.', 'error');
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
});