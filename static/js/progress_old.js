// static/topics/js/progress.js

function initProgressTracker(streamUrl, taskId, redirectUrl) {
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const percentText = document.getElementById('percent-text');
    const statusText = document.getElementById('status-text');
    const detailLog = document.getElementById('detail-log');

    if (!progressContainer || !progressBar) {
        console.error("❌ Элементы прогресс-бара не найдены!");
        return;
    }

    // Сброс состояния
    progressContainer.style.display = 'block';
    progressContainer.classList.remove('hidden');
    progressBar.style.backgroundColor = ""; // Сброс цвета (на случай ошибки ранее)
    if(percentText) percentText.textContent = "0%";
    if(statusText) statusText.textContent = "Инициализация...";
    if(detailLog) detailLog.innerHTML = '';
    
    const url = new URL(streamUrl, window.location.origin);
    url.searchParams.set('task_id', taskId);

    console.log("📡 [Progress] Подключение к SSE:", url.toString());
    const eventSource = new EventSource(url.toString());

    eventSource.onmessage = function(event) {
        try {
            const data = JSON.parse(event.data);
            const percent = data.percent || 0;
            console.log(`📊 [Progress] Получено: ${percent}% - ${data.message}`);
            
            progressBar.style.width = `${percent}%`;
            if(percentText) percentText.textContent = `${percent}%`;
            if(statusText) statusText.textContent = data.message || "Обработка...";

            // Логирование шагов
            if (detailLog && data.message) {
                // detailLog.textContent = (data.status === 'error' ? "❌ " : "⏳ ") + data.message;
                // detailLog.style.color = data.status === 'error' ? "red" : "gray";
                const div = document.createElement('div');
                div.className = 'log-entry';
                div.textContent = `${data.status === 'error' ? "❌" : "⏳"} ${data.message}`;
                div.style.color = data.status === 'error' ? "#ef4444" : "#6b7280";
                detailLog.appendChild(div);
                detailLog.scrollTop = detailLog.scrollHeight;
            }

            // Успешное завершение
            // Внутри eventSource.onmessage
            if (data.status === 'done') {
                progressBar.style.width = '100%';
                if(percentText) percentText.textContent = '100%';
                progressBar.style.backgroundColor = '#4caf50';
                if(statusText) statusText.textContent = 'Готово!';
                
                // НЕ ЗАКРЫВАЕМ СРАЗУ, даем пользователю увидеть 100%
                handleCompletion(eventSource, true, redirectUrl);
            }
            // Ошибка
            else if (data.status === 'error') {
                // progressBar.style.backgroundColor = "red";
                // handleCompletion(eventSource, false);
                progressBar.style.backgroundColor = "#ef4444";
                handleCompletion(eventSource, false, redirectUrl);
            }
        } catch (e) {
            console.error('Ошибка данных SSE:', e);
        }
    };

    eventSource.onerror = function(err) {
        // Если сервер закрыл соединение, не пытаемся стучаться вечно
        if (eventSource.readyState === EventSource.CLOSED) {
            console.log("Соединение закрыто сервером.");
        } else {
            // Если случилась ошибка сети — закрываем, чтобы не спамить
            eventSource.close();
            if(statusText) statusText.textContent = "Ошибка связи с сервером";
        }
    };

    function handleCompletion(source, isSuccess, redirectUrl) {
        // Закрываем поток СРАЗУ, чтобы не было повторных запросов
        source.close();
        // 1. Сначала принудительно красим в 100%
        const progressBar = document.getElementById('progress-bar');
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.style.backgroundColor = '#4caf50'; // Ярко-зеленый
        }

        setTimeout(() => {
            if (isSuccess && redirectUrl) {
                window.location.href = redirectUrl;
            } else if (!isSuccess) {
                // Если ошибка — оставляем бар красным на 5 секунд, потом прячем
                setTimeout(() => {
                    progressContainer.style.display = 'none';
                    progressContainer.classList.add('hidden');
                }, 5000);
            } else {
                // Просто прячем, если нет редиректа
                // progressContainer.style.display = 'none';
                // progressContainer.classList.add('hidden');
                // Просто прячем через 2 секунды
                setTimeout(() => {
                    progressContainer.classList.add('hidden');
                }, 2000);
            }
        }, 1500);
    }
}