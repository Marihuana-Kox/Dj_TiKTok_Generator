// progress_module.js
document.addEventListener('DOMContentLoaded', () => {
    const progressBar = document.getElementById('gen-progress-bar');
    const statusText = document.getElementById('progress-status-text');
    const detailsText = document.getElementById('progress-details');
    
    let source = null;

    window.startProgressTracking = () => {
        console.log('📡 [SSE] Запуск подключения к потоку...');
        if (statusText) statusText.innerText = 'Подключение к серверу...';

        if (source) source.close();
        
        const url = window.GEN_STREAM_URL || '/article/api/generation-stream/';
        console.log('📡 [SSE] URL потока:', url);
        
        source = new EventSource(url);

        source.onmessage = e => {
            console.log('📩 [SSE] Получено сообщение:', e.data); // <-- ВАЖНЫЙ ЛОГ
            
            try {
                const data = JSON.parse(e.data);
                
                // Обновление полоски
                if (progressBar && data.percent !== undefined) {
                    const percentStr = data.percent + '%';
                    progressBar.style.width = percentStr;
                    if (data.percent > 10) progressBar.innerText = percentStr;
                    
                    if (data.percent === 100) {
                        progressBar.classList.remove('progress-bar-animated');
                        progressBar.style.backgroundColor = '#28a745'; // Зеленый
                    }
                }
                
                // Обновление текста статуса
                if (statusText && data.message) {
                    statusText.innerText = data.message;
                }
                
                // Детали (последний лог)
                if (detailsText && data.log && data.log.length) {
                    detailsText.innerText = 'Последнее: ' + data.log[data.log.length - 1];
                }

                // Финиш
                if (data.status === 'done') {
                    console.log('✅ [SSE] Генерация завершена успешно');
                    finish(true, 'Готово!');
                } else if (data.status === 'error') {
                    console.error('❌ [SSE] Ошибка в процессе:', data.message);
                    finish(false, data.message);
                }
            } catch (parseErr) {
                console.error('Ошибка парсинга JSON из SSE:', parseErr, e.data);
            }
        };

        source.onerror = (err) => {
            console.warn('⚠️ [SSE] Ошибка соединения или закрытие:', err);
            source.close();
            
            const w = progressBar ? parseFloat(progressBar.style.width) : 0;
            if (w >= 100) {
                finish(true, 'Завершено (соединение закрыто)');
            } else {
                finish(false, 'Связь прервана');
            }
        };
    };

    function finish(success, msg) {
        if (statusText) {
            statusText.innerText = msg;
            statusText.style.color = success ? '#28a745' : '#dc3545';
            statusText.classList.add('fw-bold');
        }
        if (progressBar) {
            progressBar.classList.remove('progress-bar-animated');
            if (success) {
                progressBar.style.width = '100%';
                progressBar.style.backgroundColor = '#28a745';
                progressBar.innerText = '100%';
            } else {
                progressBar.style.backgroundColor = '#dc3545';
            }
        }
        // 3. АВТОМАТИЧЕСКАЯ ПЕРЕЗАГРУЗКА ПРИ УСПЕХЕ
        if (success) {
            console.log('✅ Генерация успешна. Перезагрузка через 3 секунды...');
            
            // Ждем 3 секунды и перезагружаем страницу
            setTimeout(() => {
                window.location.reload();
            }, 3000);
        }
        // Если ошибка - не перезагружаем, даем пользователю прочитать сообщение
    }
});