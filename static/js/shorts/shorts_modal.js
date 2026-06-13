document.getElementById('short-form')?.addEventListener('submit', async function(e) {
    e.preventDefault();
    const btn = this.querySelector('button[type="submit"]');
    btn.disabled = true;
    btn.textContent = '⏳ Запуск...';

    const formData = new FormData(this);
    const csrf = typeof getCookie === 'function' ? getCookie('csrftoken') : '';

    try {
        const res = await fetch('{% url "shorts:generate" %}', {
            method: 'POST',
            headers: { 'X-CSRFToken': csrf },
            body: formData
        });
        const data = await res.json();

        if (data.status === 'ok' && data.task_id) {
            // modal.js сам построит URL: /shorts/generate_stream/?task_id=...
            window.startProgressTracking(
                '{% url "shorts:generate_stream" %}',
                data.task_id,
                'progress-modal',
                () => {} // callback после завершения (редирект уже встроен в finishProgress)
            );
        } else {
            showToast(data.errors ? JSON.stringify(data.errors) : 'Ошибка запуска', 'error');
            btn.disabled = false;
            btn.textContent = '🚀 Создать сценарий';
        }
    } catch (err) {
        showToast('Ошибка сети: ' + err.message, 'error');
        btn.disabled = false;
        btn.textContent = '🚀 Создать сценарий';
    }
});