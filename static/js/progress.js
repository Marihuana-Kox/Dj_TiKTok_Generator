// static/topics/js/progress.js

function initProgressTracker(streamUrl, taskId, redirectUrl) {
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const percentText = document.getElementById('percent-text');
    const statusText = document.getElementById('status-text');
    const detailLog = document.getElementById('detail-log');

    if (!progressContainer || !progressBar) return;

    // --- НАСТРОЙКИ СИМУЛЯЦИИ ---
    let currentPercent = 0;
    let targetPercent = 0;
    let isFinished = false;

    // Сброс состояния UI
    progressContainer.style.display = 'block';
    progressContainer.classList.remove('hidden');
    progressBar.style.backgroundColor = ""; 
    progressBar.style.width = "0%";
    if(percentText) percentText.textContent = "0%";
    if(statusText) statusText.textContent = "Подготовка ИИ...";

    // --- ФУНКЦИЯ ПЛАВНОЙ ОТРИСОВКИ (Simulation Loop) ---
    function updateVisuals() {
        if (isFinished) return;

        // Если реальный прогресс (targetPercent) выше текущего, подтягиваемся к нему
        // Если нет — медленно ползем сами (симуляция работы), но не выше 95%
        if (currentPercent < targetPercent) {
            currentPercent += 1.0; // Быстрый догон реальных данных
        } else if (currentPercent < 70) {
            currentPercent += 0.05; // Очень медленное "ожидание" ответа ИИ
        }

        progressBar.style.width = `${currentPercent}%`;
        if(percentText) percentText.textContent = `${Math.floor(currentPercent)}%`;

        requestAnimationFrame(updateVisuals);
    }
    requestAnimationFrame(updateVisuals);

    // --- SSE ПОДКЛЮЧЕНИЕ ---
    const url = new URL(streamUrl, window.location.origin);
    url.searchParams.set('task_id', taskId);
    const eventSource = new EventSource(url.toString());

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            
            // Обновляем цель для симулятора
            if (data.percent) targetPercent = data.percent;
            
            if (statusText && data.message) {
                statusText.textContent = data.message;
            }

            // Логирование шагов в консоль снизу
            if (detailLog && data.message) {
                const div = document.createElement('div');
                div.className = 'log-entry';
                div.textContent = `${data.status === 'error' ? "❌" : "⏳"} ${data.message}`;
                div.style.color = data.status === 'error' ? "#ef4444" : "#ffffff";
                detailLog.appendChild(div);
                detailLog.scrollTop = detailLog.scrollHeight;
            }

            // ФИНАЛ
            if (data.status === 'done' || data.percent >= 100) {
                isFinished = true;
                finishEffect(true);
            } else if (data.status === 'error') {
                isFinished = true;
                finishEffect(false);
            }
        } catch (e) {
            console.error('Ошибка данных SSE:', e);
        }
    };

    eventSource.onerror = function() {
        if (eventSource.readyState !== EventSource.CLOSED) {
            eventSource.close();
            // Не прерываем симуляцию при сетевой ошибке, 
            // так как фоновый поток в Django скорее всего доработает.
        }
    };

    function finishEffect(success) {
        eventSource.close();
        
        // Резкий прыжок до конца
        progressBar.style.transition = "width 1.5s ease-out, background-color red 1.5s";
        progressBar.style.width = '100%';
        if(percentText) percentText.textContent = '100%';
        
        if (success) {
            progressBar.style.backgroundColor = '#4caf50';
            if(statusText) statusText.textContent = 'Готово! Сохраняем...';
            
            setTimeout(() => {
                if (redirectUrl) window.location.href = redirectUrl;
            }, 1200);
        } else {
            progressBar.style.backgroundColor = "#ef4444";
            if(statusText) statusText.textContent = 'Ошибка генерации';
        }
    }
}