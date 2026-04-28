// form_module.js
document.addEventListener('DOMContentLoaded', () => {
    const form = document.getElementById('article-gen-form');
    const btn = form?.querySelector('button[type="submit"]');
    if (!form || !btn) return;

    let isBusy = false;
    let pendingFormData = null;

    // Элементы модалки
    const modal = document.getElementById('status-modal');
    const summaryBox = document.getElementById('status-summary');
    const actionsBox = document.getElementById('status-actions');
    const progressBlock = document.getElementById('status-progress-block');
    const confirmBtn = document.getElementById('btn-confirm-start');
    const cancelBtn = document.getElementById('btn-cancel-start');
    const closeX = document.getElementById('modal-close-x');
    const progressBar = document.getElementById('gen-progress-bar');
    const statusText = document.getElementById('progress-status-text');
    const detailsText = document.getElementById('progress-details');
    const titleText = document.getElementById('status-modal-title');

    // --- 1. ЛОГИКА ЧЕКБОКСОВ ---
    const updateCount = () => {
        const el = document.getElementById('selected-count');
        if (el) el.textContent = document.querySelectorAll('.idea-checkbox:checked').length;
    };
    document.querySelectorAll('.idea-row').forEach(row => {
        row.addEventListener('click', e => {
            if (e.target.type !== 'checkbox') {
                const cb = row.querySelector('.idea-checkbox');
                if (cb) { cb.checked = !cb.checked; cb.dispatchEvent(new Event('change')); }
            }
        });
    });
    document.querySelectorAll('.idea-checkbox').forEach(cb => cb.addEventListener('change', updateCount));
    const selectAll = document.getElementById('select-all-ideas');
    if (selectAll) selectAll.addEventListener('change', e => {
        document.querySelectorAll('.idea-checkbox').forEach(cb => {
            cb.checked = e.target.checked;
            cb.dispatchEvent(new Event('change'));
        });
    });
    updateCount();

    // --- 2. НАСТРОЙКИ (ОБНОВЛЕННАЯ ЛОГИКА) ---
    window.togglePromptSettings = () => {
        const promptsToggle = document.getElementById('enable-prompts-toggle');
        const isPromptsEnabled = promptsToggle ? promptsToggle.checked : true;

        const block = document.getElementById('prompt-settings-container');
        if (!block) return;

        // Проверяем радиокнопку для режима (Авто или Ручной)
        const isManual = document.querySelector('input[name="image_mode"][value="manual"]')?.checked;
        const manualSubBlock = document.getElementById('manual-count-block');

        if (!isPromptsEnabled) {
            // Если переключатель выключен, скрываем весь блок и блокируем элементы
            block.style.display = 'none';
            block.classList.add('d-none');
            block.querySelectorAll('input, select, button').forEach(i => i.disabled = true);
        } else {
            // Если переключатель включен, показываем блок и настраиваем элементы
            block.style.display = 'block';
            block.classList.remove('d-none');

            // Активируем радиокнопки режима
            document.querySelectorAll('input[name="image_mode"]').forEach(radio => radio.disabled = false);

            if (manualSubBlock) {
                if (isManual) {
                    // Если выбран ручной режим, показываем подблок и активируем элементы
                    manualSubBlock.style.display = 'block';
                    manualSubBlock.classList.remove('d-none');
                    manualSubBlock.querySelectorAll('input, button').forEach(i => i.disabled = false);
                } else {
                    // Если выбран автоматический режим, скрываем подблок и блокируем элементы
                    manualSubBlock.style.display = 'none';
                    manualSubBlock.classList.add('d-none');
                    manualSubBlock.querySelectorAll('input, button').forEach(i => i.disabled = true);
                }
            }

            // Активируем остальные элементы, не относящиеся к ручному блоку
            block.querySelectorAll('select, input:not([name="image_mode"]), button').forEach(i => {
                if (!isManual && manualSubBlock && manualSubBlock.contains(i)) {
                    i.disabled = true;
                } else {
                    i.disabled = false;
                }
            });
        }
    };

    // Инициализация при загрузке
    setTimeout(window.togglePromptSettings, 50);

    // Слушатели событий
    const promptsToggle = document.getElementById('enable-prompts-toggle');
    if (promptsToggle) {
        promptsToggle.addEventListener('change', window.togglePromptSettings);
    }

    document.querySelectorAll('input[name="image_mode"]').forEach(r => {
        r.addEventListener('change', window.togglePromptSettings);
    });

    // --- 3. ОТПРАВКА ФОРМЫ ---
    form.addEventListener('submit', e => {
        e.preventDefault();
        if (isBusy) return alert('⏳ Процесс уже идет...');

        const ideaCheckboxes = document.querySelectorAll('input[name="idea_selection"]:checked');
        const ideaIds = Array.from(ideaCheckboxes).map(c => c.value);
        const langCount = document.querySelectorAll('input[name="languages"]:checked').length;

        if (!ideaIds.length) return alert('⚠️ Выберите хотя бы одну идею!');
        if (!langCount) return alert('⚠️ Выберите хотя бы один язык!');

        // --- СБОР ДАННЫХ ДЛЯ МОДАЛКИ ---
        const providerEl = document.getElementById('id_ai_provider');
        const provider = providerEl ? providerEl.options[providerEl.selectedIndex].text : 'Unknown';

        const promptEl = document.getElementById('id_article_prompt');
        const promptStyle = promptEl ? promptEl.options[promptEl.selectedIndex].text : 'Random';

        const aspectEl = document.getElementById('id_aspect_ratio');
        const aspectRatio = aspectEl ? aspectEl.value : '9:16';

        const isManual = document.querySelector('input[name="image_mode"][value="manual"]')?.checked;
        let modeText = isManual ? '✋ Ручной' : '🤖 Автоматический';

        const promptsToggleEl = document.getElementById('enable-prompts-toggle');
        const isPromptsEnabled = promptsToggleEl ? promptsToggleEl.checked : true;

        const artStyleInput = document.getElementById('id_art_style');
        const artStyleValue = artStyleInput ? artStyleInput.value.trim() : '';

        let artStyleInfo = '';
        if (isPromptsEnabled) {
            if (artStyleValue) {
                artStyleInfo = `<li><span>✨ Стиль рисования:</span> <strong>"${artStyleValue}"</strong></li>`;
            } else {
                artStyleInfo = `<li><span>✨ Стиль рисования:</span> <strong class="text-muted">По умолчанию</strong></li>`;
            }
        }

        let sceneCountInfo = '';
        if (!isPromptsEnabled) {
            sceneCountInfo = `<li><span>🖼️ Картинки:</span> <strong class="text-muted">❌ Отключены</strong></li>`;
        } else {
            if (isManual) {
                const countVal = document.getElementById('id_manual_scene_count')?.value || 5;
                sceneCountInfo = `<li><span>🖼️ Сцен (ручн.):</span> <strong>${countVal} шт.</strong></li>`;
            } else {
                sceneCountInfo = `<li><span>🖼️ Сцен:</span> <strong>AI определит сам</strong></li>`;
            }
        }

        summaryBox.innerHTML = `
            <ul>
                <li><span>📝 Идеи:</span> <strong>${ideaIds.length} шт.</strong></li>
                <li><span>🌍 Языки:</span> <strong>${langCount} выбрано</strong></li>
                <li><span>🤖 Провайдер:</span> <strong>${provider}</strong></li>
                <li><span>✍️ Стиль статьи:</span> <strong>${promptStyle}</strong></li>
                <li><span>🎨 Режим:</span> <strong>${modeText}</strong></li>
                ${sceneCountInfo}
                ${artStyleInfo}
                <li><span>📐 Пропорции:</span> <strong>${aspectRatio}</strong></li>
            </ul>
        `;

        pendingFormData = new FormData(form);
        showModal();
    });

    // --- 4. УПРАВЛЕНИЕ МОДАЛКОЙ ---
    function showModal() {
        if (!modal) return;
        modal.classList.add('active');
        actionsBox.classList.remove('d-none');
        progressBlock.classList.add('d-none');
        titleText.innerText = '🚀 Подготовка к генерации';
        titleText.style.color = ''; 
    }

    function hideModal() {
        if (!modal) return;
        modal.classList.remove('active');
        setTimeout(() => { pendingFormData = null; }, 300);
    }

    if (closeX) closeX.addEventListener('click', hideModal);
    if (modal) modal.addEventListener('click', (e) => { if (e.target === modal) hideModal(); });

    if (cancelBtn) cancelBtn.addEventListener('click', () => { hideModal(); console.log('Отмена'); });

    // if (confirmBtn) {
    //     confirmBtn.addEventListener('click', () => {
    //         if (!pendingFormData) return;
            
    //         actionsBox.classList.add('d-none');
    //         progressBlock.classList.remove('d-none');
    //         titleText.innerText = '⏳ Генерация идет...';

    //         progressBar.style.width = '0%';
    //         progressBar.className = 'progress-bar progress-bar-animated';
    //         statusText.innerText = 'Отправка данных...';

    //         form.querySelectorAll('[disabled]').forEach(el => el.disabled = false);
    //         isBusy = true;

    //         fetch(window.GEN_API_URL || '/article/api/start-generation/', {
    //             method: 'POST',
    //             body: pendingFormData,
    //             headers: { 'X-Requested-With': 'XMLHttpRequest', 'X-CSRFToken': getCookie('csrftoken') }
    //         })
    //         .then(r => {
    //             if (!r.ok) throw new Error(`Ошибка: ${r.status}`);
    //             return r.json();
    //         })
    //         .then(data => {
    //             if (data.status === 'started') {
    //                 if (typeof window.startProgressTracking === 'function') window.startProgressTracking();
    //                 else {
    //                     statusText.innerText = 'Запущено!';
    //                     progressBar.style.backgroundColor = '#28a745';
    //                     setTimeout(hideModal, 2000);
    //                 }
    //             } else throw new Error(data.message);
    //         })
    //         .catch(err => {
    //             console.error(err);
    //             statusText.innerText = '❌ Ошибка';
    //             statusText.style.color = '#dc3545';
    //             progressBar.classList.remove('progress-bar-animated');
    //             progressBar.style.backgroundColor = '#dc3545';
    //             progressBar.style.width = '100%';
    //             detailsText.innerText = err.message;
    //             isBusy = false;
    //         });
    //     });
    // }
        // Кнопка ПРОДОЛЖИТЬ
    if (confirmBtn) {
        confirmBtn.addEventListener('click', () => {
            if (!pendingFormData) return;
            
            // Переключаем интерфейс на прогресс-бар
            actionsBox.classList.add('d-none');
            progressBlock.classList.remove('d-none');
            titleText.innerText = '⏳ Генерация идет...';
            
            progressBar.style.width = '0%';
            progressBar.className = 'progress-bar progress-bar-animated';
            statusText.innerText = 'Отправка данных...';
            detailsText.innerText = '';

            // === 🔍 ДИАГНОСТИКА: ЧТО ОТПРАВЛЯЕМ? ===
            console.group('📦 ОТПРАВКА ДАННЫХ НА СЕРВЕР');
            console.log('URL:', window.GEN_API_URL || '/article/api/start-generation/');
            
            const formDataObj = {};
            // FormData нельзя просто так вывести, преобразуем в объект для лога
            for (let [key, value] of pendingFormData.entries()) {
                // Если ключ повторяется (например, несколько языков или идей), собираем в массив
                if (formDataObj[key]) {
                    if (!Array.isArray(formDataObj[key])) {
                        formDataObj[key] = [formDataObj[key]];
                    }
                    formDataObj[key].push(value);
                } else {
                    formDataObj[key] = value;
                }
            }
            console.table(formDataObj); // Красивая таблица в консоли
            console.groupEnd();
            // =======================================

            // Включаем скрытые поля перед реальной отправкой (чтобы они ушли в запросе)
            // Но мы уже собрали pendingFormData раньше, так что это нужно, если форма отправляется напрямую.
            // В нашем случае pendingFormData уже собран, но для надежности оставим эту строку, 
            // если вдруг логика изменится на прямую отправку form.submit()
            form.querySelectorAll('[disabled]').forEach(el => el.disabled = false);

            isBusy = true;

            fetch(window.GEN_API_URL || '/article/api/start-generation/', {
                method: 'POST',
                body: pendingFormData, // Отправляем собранные ранее данные
                headers: { 
                    'X-Requested-With': 'XMLHttpRequest', 
                    'X-CSRFToken': getCookie('csrftoken') 
                }
            })
            .then(r => {
                if (!r.ok) throw new Error(`Ошибка сервера: ${r.status}`);
                return r.json();
            })
            .then(data => {
                console.log('📥 ОТВЕТ СЕРВЕРА:', data); // Лог ответа
                
                if (data.status === 'started') {
                    statusText.innerText = 'Соединение с потоком данных...';
                    if (typeof window.startProgressTracking === 'function') {
                        window.startProgressTracking();
                    } else {
                        throw new Error('Функция startProgressTracking не найдена!');
                    }
                } else {
                    throw new Error(data.message || 'Неизвестная ошибка в ответе');
                }
            })
            .catch(err => {
                console.error('❌ КРИТИЧЕСКАЯ ОШИБКА:', err);
                statusText.innerText = '❌ Ошибка запуска';
                statusText.style.color = '#dc3545';
                progressBar.classList.remove('progress-bar-animated');
                progressBar.style.backgroundColor = '#dc3545';
                progressBar.style.width = '100%';
                detailsText.innerText = err.message;
                isBusy = false;
            });
        });
    }

    function getCookie(name) {
        const v = document.cookie.match('(^|;) ?' + name + '=([^;]*)(;|$)');
        return v ? v[2] : null;
    }
});