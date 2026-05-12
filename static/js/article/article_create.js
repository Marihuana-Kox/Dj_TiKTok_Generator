/**
 * ARTICLE CREATE — оптимизированная версия для работы с modal.js
 */
document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('article-gen-form');
    const submitBtn = form?.querySelector('button[type="submit"]');

    if (!form || !submitBtn) return;

    // Инициализация UI логики
    initSelectAll();
    initRowClick();

    form.addEventListener('submit', function(e) {
        e.preventDefault();
        
        const selectedCheckboxes = document.querySelectorAll('input[name="idea_selection"]:checked');
        if (selectedCheckboxes.length === 0) {
            showToast('⚠️ Выберите хотя бы одну идею', 'error');
            return;
        }

        submitBtn.disabled = true;
        const originalBtnText = submitBtn.innerHTML;
        submitBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Запуск...';

        const formData = new FormData(form);

        // ВАЖНО: Проверь, чтобы form.action вел на /article/api/start-generation/
        fetch(form.action, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(response => {
            // Если сервер вернул ошибку (HTML вместо JSON), мы увидим это здесь
            if (!response.ok) {
                return response.text().then(text => {
                    console.error("❌ Ошибка сервера (HTML):", text);
                    throw new Error('Сервер вернул ошибку ' + response.status);
                });
            }
            return response.json();
        })
        .then(data => {
            if (data.status === 'ok' && data.task_id) {
                // ПЕРЕДАЕМ УПРАВЛЕНИЕ В MODAL.JS
                if (typeof window.startProgressTracking === 'function') {
                    // ИСПОЛЬЗУЕМ АДРЕС СТРИМА (stream), а не запуска (start)
                    window.startProgressTracking('/article/api/generation-stream/', data.task_id);
                } else {
                    console.error('❌ modal.js не загружен или функция startProgressTracking отсутствует');
                }
            } else {
                showToast(data.message || 'Ошибка запуска', 'error');
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalBtnText;
            }
        })
        .catch(error => {
            console.error('❌ Ошибка выполнения:', error);
            showToast('Критическая ошибка при отправке', 'error');
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalBtnText;
        });
    });

    function initSelectAll() {
        const selectAll = document.getElementById('select-all-ideas'); 
        if (!selectAll) return;
        selectAll.addEventListener('change', function() {
            document.querySelectorAll('input[name="idea_selection"]').forEach(cb => {
                cb.checked = this.checked;
            });
            updateCount(); // Обновляем счетчик
        });
    }
    function updateCount() {
        const countLabel = document.getElementById('selected-count'); // Было count-val
        const checked = document.querySelectorAll('input[name="idea_selection"]:checked').length;
        if (countLabel) countLabel.textContent = checked;
    }
    // Внутри initRowClick тоже вызывайте updateCount
    function initRowClick() {
        document.querySelectorAll('.idea-row').forEach(row => {
            row.addEventListener('click', function(e) {
                if (e.target.type !== 'checkbox') {
                    const cb = this.querySelector('input[name="idea_selection"]');
                    if (cb) {
                        cb.checked = !cb.checked;
                        updateCount();
                    }
                }
            });
        });
    }
});