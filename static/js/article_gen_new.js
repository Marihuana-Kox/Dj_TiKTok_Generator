document.addEventListener('DOMContentLoaded', function() {
    console.log("🚀 [FINAL SCRIPT] Article Generator v3.0 Loaded");

    // --- 1. НАСТРОЙКИ И ЭЛЕМЕНТЫ ---
    const form = document.getElementById('article-gen-form');
    const submitBtn = form ? form.querySelector('button[type="submit"]') : null;
    
    const warningBox = document.getElementById('warning-box');
    const warningText = document.getElementById('warning-text');
    const counterEl = document.getElementById('selected-count');
    
    // Элементы модального окна и прогресса
    const progressModal = document.getElementById('progress-modal'); // Убедись, что такой ID есть в HTML
    const progressBar = document.getElementById('gen-progress-bar'); // Полоска
    const progressPercent = document.getElementById('gen-progress-percent'); // Текст процентов
    const progressMessage = document.getElementById('gen-progress-message'); // Текст статуса
    const progressLog = document.getElementById('gen-progress-log'); // Список логов (опционально)
    const closeProgressBtn = document.getElementById('close-progress-modal'); // Кнопка закрытия

    if (!form) {
        console.error("❌ Форма с ID 'article-gen-form' не найдена!");
        return;
    }

    let isGenerating = false;
    let eventSource = null; // Для хранения подключения SSE

    // --- 🧠 ЛОГИКА ЧЕКБОКСОВ (Твоя рабочая версия) ---
    function updateCount() {
        const count = document.querySelectorAll('.idea-checkbox:checked').length;
        if (counterEl) counterEl.textContent = count;
    }

    function toggleRowCheckbox(row) {
        const checkbox = row.querySelector('.idea-checkbox');
        if (!checkbox) return;
        checkbox.checked = !checkbox.checked;
        checkbox.dispatchEvent(new Event('change'));
    }

    document.querySelectorAll('.idea-row').forEach(row => {
        row.addEventListener('click', function(e) {
            if (e.target.type === 'checkbox') return;
            toggleRowCheckbox(row);
        });
    });

    document.querySelectorAll('.idea-checkbox').forEach(cb => {
        cb.addEventListener('change', updateCount);
    });

    updateCount();

    // --- ⚙️ НОВАЯ ФУНКЦИЯ: НАСТРОЙКИ ПРОМПТОВ (Fix ReferenceError) ---
    window.togglePromptSettings = function() {
        console.log("⚙️ Переключение режима картинок...");
        
        const manualRadio = document.querySelector('input[name="image_mode"][value="manual"]');
        const manualBlock = document.getElementById('manual-count-block');
        
        if (!manualBlock) return;

        if (manualRadio && manualRadio.checked) {
            manualBlock.style.display = 'block';
            manualBlock.classList.remove('d-none');
            // Включаем инпуты, чтобы они отправились в форме
            const inputs = manualBlock.querySelectorAll('input, select');
            inputs.forEach(inp => inp.disabled = false);
        } else {
            manualBlock.style.display = 'none';
            manualBlock.classList.add('d-none');
            // Отключаем, чтобы не мешали
            const inputs = manualBlock.querySelectorAll('input, select');
            inputs.forEach(inp => inp.disabled = true);
        }
    };

    // Запускаем проверку при загрузке, чтобы скрыть/показать блок правильно
    setTimeout(window.togglePromptSettings, 100);
    
    // Вешаем слушатели на радиокнопки, если их нет в HTML
    document.querySelectorAll('input[name="image_mode"]').forEach(radio => {
        radio.addEventListener('change', window.togglePromptSettings);
    });

    // --- ✅ SELECT ALL ---
    const selectAllCheckbox = document.getElementById('select-all-ideas');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            const isChecked = this.checked;
            document.querySelectorAll('.idea-checkbox').forEach(cb => {
                cb.checked = isChecked;
                cb.dispatchEvent(new Event('change'));
            });
        });
    }

    // --- 2. ОБРАБОТЧИК ОТПРАВКИ ---
    form.addEventListener('submit', function(e) {
        e.preventDefault();

        if (isGenerating) {
            alert("⏳ Генерация уже запущена.");
            return;
        }

        if (warningBox) warningBox.classList.add('d-none');
        if (warningText) warningText.innerHTML = '';

        const selectedCheckboxes = document.querySelectorAll('input[name="idea_selection"]:checked');
        const selectedIds = Array.from(selectedCheckboxes).map(cb => cb.value);

        if (selectedIds.length === 0) {
            showWarning("⚠️ Выберите хотя бы одну идею.");
            return;
        }

        console.log(`✅ Запуск для ${selectedIds.length} идей...`);

        const formData = new FormData(form);
        setGeneratingState(true);

        const url = window.GEN_API_URL || form.action || '/article/api/start-generation/';
        
        fetch(url, {
            method: 'POST',
            body: formData,
            headers: {
                'X-Requested-With': 'XMLHttpRequest',
                'X-CSRFToken': getCookie('csrftoken')
            }
        })
        .then(r => {
            if (!r.ok) throw new Error(`HTTP ${r.status}`);
            return r.text().then(text => {
                try {
                    return JSON.parse(text);
                } catch (e) {
                    console.error("❌ Сервер вернул НЕ JSON:", text);
                    throw new Error("Сервер вернул HTML вместо JSON. Проверьте консоль Django.");
                }
            });
        })
        .then(data => {
            console.log("📥 Ответ сервера:", data);

            if (data.status === 'started') {
                // Запускаем трекер прогресса
                if (typeof window.initProgressTracker === 'function') {
                    window.initProgressTracker(window.GEN_STREAM_URL || '/article/api/generation-stream/');
                } else {
                    alert("Генерация запущена! Но модуль прогресс-бара не найден.");
                    setGeneratingState(false);
                }
            } else {
                showWarning(data.message || "Ошибка сервера");
                setGeneratingState(false);
            }
        })
        .catch(err => {
            console.error(err);
            showWarning(err.message);
            setGeneratingState(false);
        });
    });

    // --- 3. ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

    function showWarning(htmlMessage) {
        if (warningText) warningText.innerHTML = htmlMessage;
        if (warningBox) {
            warningBox.classList.remove('d-none');
            warningBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
        } else {
            alert(htmlMessage.replace(/<[^>]*>?/gm, ''));
        }
    }

    function setGeneratingState(isLoading) {
        isGenerating = isLoading;
        if (submitBtn) {
            submitBtn.disabled = isLoading;
            submitBtn.innerHTML = isLoading ? '⏳ Обработка...' : '🚀 Запустить генерацию';
        }
        form.querySelectorAll('input, select, button').forEach(el => {
            if (el !== submitBtn) el.disabled = isLoading;
        });
    }

    function getCookie(name) {
        let cookieValue = null;
        document.cookie.split(';').forEach(cookie => {
            cookie = cookie.trim();
            if (cookie.startsWith(name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
            }
        });
        return cookieValue;
    }

    // --- 4. МОДАЛКА И ПРОГРЕСС-БАР (ИНТЕГРАЦИЯ) ---
    
    window.initProgressTracker = function(url) {
        console.log("📡 Подключение к SSE потоку:", url);

        // 1. Открываем модалку
        if (progressModal) {
            progressModal.style.display = 'block';
            progressModal.classList.remove('d-none');
            // Если используешь Bootstrap, добавь класс show
            progressModal.classList.add('show'); 
        }

        // Сброс прогресса
        if (progressBar) {
            progressBar.style.width = '0%';
            progressBar.setAttribute('aria-valuenow', 0);
            progressBar.textContent = '0%';
            progressBar.classList.remove('bg-success', 'bg-danger');
            progressBar.classList.add('bg-primary', 'progress-bar-animated');
        }
        if (progressPercent) progressPercent.textContent = '0%';
        if (progressMessage) progressMessage.textContent = 'Инициализация...';
        if (progressLog) progressLog.innerHTML = '';

        // 2. Подключаемся к потоку
        if (eventSource) eventSource.close(); // Закрываем старое, если было
        eventSource = new EventSource(url);

        // 3. Обработка сообщений
        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                console.log("📊 Прогресс:", data);

                // Обновляем полосу
                if (progressBar && data.percent !== undefined) {
                    const percent = data.percent + '%';
                    progressBar.style.width = percent;
                    progressBar.setAttribute('aria-valuenow', data.percent);
                    progressBar.textContent = percent;
                    if (progressPercent) progressPercent.textContent = percent;
                }

                // Обновляем текст статуса
                if (progressMessage && data.message) {
                    progressMessage.textContent = data.message;
                }

                // Добавляем лог (если есть блок логов)
                if (progressLog && data.log && data.log.length > 0) {
                    const lastLog = data.log[data.log.length - 1];
                    const li = document.createElement('li');
                    li.textContent = lastLog;
                    progressLog.prepend(li);
                }

                // 4. Завершение или Ошибка
                if (data.status === 'done') {
                    finishProgress(true, "Готово!");
                } else if (data.status === 'error') {
                    finishProgress(false, data.message || "Произошла ошибка");
                }

            } catch (e) {
                console.error("Ошибка парсинга SSE:", e);
            }
        };

        // 5. Обработка ошибок соединения
        eventSource.onerror = function(err) {
            console.error("❌ SSE Ошибка соединения:", err);
            // Не показываем ошибку сразу, возможно поток просто закрылся сервером после завершения
            // Проверяем, не достигли ли мы 100% перед этим
            if (progressBar && parseFloat(progressBar.style.width) >= 100) {
                finishProgress(true, "Соединение закрыто (задача выполнена)");
            } else {
                finishProgress(false, "Потеряно соединение с сервером");
            }
            eventSource.close();
        };
    };

    function finishProgress(success, message) {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }

        if (progressBar) {
            progressBar.classList.remove('progress-bar-animated');
            if (success) {
                progressBar.classList.add('bg-success');
                progressBar.style.width = '100%';
                if (progressPercent) progressPercent.textContent = '100%';
            } else {
                progressBar.classList.add('bg-danger');
            }
        }
        
        if (progressMessage) progressMessage.textContent = message;
        if (progressLog) {
            const li = document.createElement('li');
            li.textContent = success ? "✅ Завершено успешно" : "❌ Ошибка выполнения";
            li.className = success ? "text-success" : "text-danger";
            li.style.fontWeight = "bold";
            progressLog.prepend(li);
        }

        // Разблокируем кнопку формы
        setGeneratingState(false);

        // Автоматическое закрытие через 3 секунды (опционально)
        setTimeout(() => {
            if (progressModal) {
                // progressModal.style.display = 'none'; 
                // progressModal.classList.remove('show');
                // Лучше оставить открытым, чтобы пользователь сам закрыл и увидел логи
                console.log("✅ Процесс завершен. Окно открыто.");
            }
        }, 3000);
    }

    // Кнопка закрытия модалки
    if (closeProgressBtn) {
        closeProgressBtn.addEventListener('click', function() {
            if (progressModal) {
                progressModal.style.display = 'none';
                progressModal.classList.remove('show');
            }
        });
    }

    console.log("✅ Все системы готовы. Чекбоксы, настройки и прогресс-бар работают.");
});