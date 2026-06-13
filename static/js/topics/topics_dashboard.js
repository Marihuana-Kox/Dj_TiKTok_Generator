// ============================================================================
// TOPICS DASHBOARD & GENERATOR — чекбоксы + AJAX генерация
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 topics_dashboard.js инициализация...');

    // --- 1. ЛОГИКА ЧЕКБОКСОВ (Дашборд) ---
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.idea-checkbox, input[name="selected_topics"]');
    const rows = document.querySelectorAll('.idea-row');
    
    const countVal = document.getElementById('count-val');
    const selectionCount = document.getElementById('selection-count');
    const btnDelete = document.getElementById('btn-delete');
    const btnStatus = document.getElementById('btn-status');
    const statusSelect = document.getElementById('status-select');

    function updateSelection() {
        const checked = Array.from(checkboxes).filter(cb => cb.checked && cb.value);
        const count = checked.length;
        const hasSelection = count > 0;
        
        if (countVal) countVal.textContent = count;
        if (selectionCount) selectionCount.style.display = hasSelection ? 'inline' : 'none';
        if (btnDelete) btnDelete.disabled = !hasSelection;
        if (btnStatus) btnStatus.disabled = !hasSelection;
        if (statusSelect) statusSelect.disabled = !hasSelection;

        checkboxes.forEach((cb, index) => {
            if (rows[index]) {
                rows[index].classList.toggle('bg-selected', cb.checked);
            }
        });
    }

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
                cb.dispatchEvent(new Event('change'));
            });
            updateSelection();
        });
    }

    checkboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            if (!cb.checked && selectAll) selectAll.checked = false;
            updateSelection();
        });

        const row = cb.closest('.idea-row');
        if (row) {
            row.addEventListener('click', function(e) {
                // Чтобы клик по кнопкам или ссылкам внутри строки не переключал чекбокс
                if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'A' && e.target.type !== 'checkbox') {
                    cb.checked = !cb.checked;
                    cb.dispatchEvent(new Event('change'));
                }
            });
        }
    });

    updateSelection();


    // --- 2. ЛОГИКА ГЕНЕРАЦИИ (Форма) ---
    const generateForm = document.getElementById('generate-form');
    const generateBtn = document.getElementById('start-topics-gen');

    if (generateBtn) {
        generateBtn.addEventListener('click', function(e) {
            // ОСТАНАВЛИВАЕМ перезагрузку
            e.preventDefault();
            e.stopPropagation();

            console.log('🚀 Запуск генерации через AJAX...');

            // Если кнопка нажата на странице создания идей (где есть форма)
            if (generateForm) {
                const formData = new FormData(generateForm);
                const data = Object.fromEntries(formData.entries());

                // Явно берем состояние чекбоксов, так как FormData их пропускает, если они false
                data.refresh_old = generateForm.querySelector('[name="refresh_old"]')?.checked || false;
                data.allow_duplicates = generateForm.querySelector('[name="allow_duplicates"]')?.checked || false;

                // Открываем модалку и прогресс
                if (typeof window.openModal === 'function') window.openModal('progress-modal');
                if (typeof window.updateProgress === 'function') window.updateProgress(0, 'Отправка запроса...');

                // Отправляем POST на текущий URL формы
                fetch(window.location.href, {
                    method: 'POST',
                    headers: {
                        'X-CSRFToken': data.csrfmiddlewaretoken || document.querySelector('[name=csrfmiddlewaretoken]').value,
                        'Content-Type': 'application/json',
                        'X-Requested-With': 'XMLHttpRequest'
                    },
                    body: JSON.stringify(data)
                })
                .then(response => {
                    if (!response.ok) throw new Error('Ошибка сервера при запуске');
                    return response.json();
                })
                .then(result => {
                    console.log('✅ Задача принята сервером:', result);
                    // Запускаем SSE трекер
                    if (typeof window.startProgressTracking === 'function') {
                        window.startProgressTracking(
                            '/topics/api/generate-stream/', 
                            result.task_id || null, 
                            'progress-modal'
                        );
                    }
                })
                .catch(error => {
                    console.error('❌ Ошибка:', error);
                    if (typeof window.addProgressLog === 'function') {
                        window.addProgressLog('Ошибка: ' + error.message, 'error');
                    }
                });

            } else {
                // Если кнопка нажата на дашборде (где нет большой формы, только список)
                if (typeof window.openModal === 'function') window.openModal('progress-modal');
                if (typeof window.startProgressTracking === 'function') {
                    window.startProgressTracking('/topics/api/generate-stream/', null, 'progress-modal');
                }
            }
        });
    }

    // --- 3. ДОПОЛНИТЕЛЬНЫЕ ИНТЕРФЕЙСНЫЕ ФИШКИ ---
    const refreshCheck = document.querySelector('[name="refresh_old"]');
    const duplicateCheck = document.querySelector('[name="allow_duplicates"]');

    if (refreshCheck) {
        refreshCheck.addEventListener('change', function() {
            const options = document.getElementById('refresh-options');
            if (options) options.style.display = this.checked ? 'block' : 'none';
        });
    }
    if (duplicateCheck) {
        duplicateCheck.addEventListener('change', function() {
            const options = document.getElementById('duplicate-options');
            if (options) options.style.display = this.checked ? 'block' : 'none';
        });
    }

    console.log('✅ topics_dashboard.js полностью загружен');
});

document.addEventListener('DOMContentLoaded', () => {
    // Тоггл для обновления старых идей
    const refreshCheck = document.getElementById('id_refresh_old');
    const refreshOpts = document.getElementById('refresh-options');
    if (refreshCheck && refreshOpts) {
        refreshCheck.addEventListener('change', () => {
            refreshOpts.style.display = refreshCheck.checked ? 'block' : 'none';
        });
    }

    // Тоггл для повторов
    const dupCheck = document.getElementById('id_allow_duplicates');
    const dupOpts = document.getElementById('duplicate-options');
    if (dupCheck && dupOpts) {
        dupCheck.addEventListener('change', () => {
            dupOpts.style.display = dupCheck.checked ? 'block' : 'none';
        });
    }
});