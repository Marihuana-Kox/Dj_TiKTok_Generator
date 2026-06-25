document.addEventListener('DOMContentLoaded', function() {
    // 1. Находим форму
    const form = document.getElementById('short-form');
    if (!form) {
        console.warn("Форма с id='short-form' не найдена");
        return;
    }

    // 2. Перехватываем отправку
    form.addEventListener('submit', async function(e) {
        e.preventDefault(); // ОСТАНАВЛИВАЕМ стандартную перезагрузку страницы

        const btn = form.querySelector('button[type="submit"]');
        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '⏳ Запуск...';

        const formData = new FormData(form);
        const csrf = typeof getCookie === 'function' ? getCookie('csrftoken') : '';

        try {
            // 3. Отправляем данные тихо через fetch
            const response = await fetch(form.action || window.location.href, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-CSRFToken': csrf,
                    'X-Requested-With': 'XMLHttpRequest' // Ключевой заголовок для views.py
                }
            });

            const data = await response.json();
            console.log("✅ Ответ от сервера:", data);

            // 4. ЕСЛИ ВСЁ УСПЕШНО — ЗАПУСКАЕМ МОДАЛКУ!
            if (data.status === 'ok' && data.task_id) {
                window.startProgressTracking(
                    data.stream_url,          // 1. Откуда читать прогресс (из ответа views.py)
                    data.task_id,             // 2. ID задачи
                    'progress-modal',         // 3. ID твоего модального окна
                    function(result) {        // 4. Что делать после завершения
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
            console.error("💥 Ошибка сети:", error);
            showToast('Ошибка сети. Проверьте консоль.', 'error');
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    });
});