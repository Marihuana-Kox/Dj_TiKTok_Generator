(function() {
    console.log('✅ modal.js загружен');

    let eventSource = null;
    let currentModalId = 'progress-modal';

    // --- Функции открытия/закрытия ---
    window.openModal = window.openModal || function(modalId) {
        const modal = document.getElementById(modalId || 'progress-modal');
        if (!modal) return;
        modal.classList.remove('d-none');
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
        console.log('🔓 Модалка открыта:', modalId);
    };

    window.closeModal = window.closeModal || function(modalId) {
        const modal = document.getElementById(modalId || 'progress-modal');
        if (!modal) return;
        modal.classList.add('d-none');
        modal.style.display = 'none';
        document.body.style.overflow = '';
        console.log('🔒 Модалка закрыта:', modalId);
    };

    // --- Плавное обновление прогресса и БЕГУЩИЕ ЦИФРЫ ---
    window.updateProgress = window.updateProgress || function(targetPercent, message) {
        const progressBar = document.getElementById('gen-progress-bar');
        const progressPercent = document.getElementById('gen-progress-percent');
        const progressMessage = document.getElementById('gen-progress-message');
        
        if (progressMessage && message) progressMessage.textContent = message;

        if (progressBar) {
            progressBar.style.transition = "width 1s linear"; 
            progressBar.style.width = targetPercent + '%';
        }

        if (progressPercent) {
            const startPercent = parseInt(progressPercent.textContent) || 0;
            const duration = 1000; 
            const startTime = performance.now();

            function animate(currentTime) {
                const elapsed = currentTime - startTime;
                const progress = Math.min(elapsed / duration, 1);
                const currentNum = Math.floor(startPercent + (targetPercent - startPercent) * progress);
                
                progressPercent.textContent = currentNum + '%';

                if (progress < 1) {
                    requestAnimationFrame(animate);
                }
            }
            requestAnimationFrame(animate);
        }
    };

    window.addProgressLog = window.addProgressLog || function(message, type = 'info') {
        const log = document.getElementById('gen-progress-log');
        if (!log) return;
        const li = document.createElement('li');
        li.textContent = message;
        li.className = type;
        log.appendChild(li);
        log.scrollTop = log.scrollHeight;
    };

    function finishProgress(success, message, redirectUrl, minDelay) {
        if (eventSource) { eventSource.close(); eventSource = null; }

        const progressBar = document.getElementById('gen-progress-bar');
        const statusText = document.getElementById('gen-progress-message');
        
        if (progressBar) {
            progressBar.style.width = '100%';
            progressBar.className = 'progress-bar ' + (success ? 'bg-success' : 'bg-danger');
        }
        if (statusText) statusText.textContent = message;

        console.log("🏁 Завершение. Ждем редирект...");

        setTimeout(() => {
            if (success && redirectUrl) {
                window.location.href = redirectUrl;
            }
        }, minDelay || 3000);
    }

    window.startProgressTracking = function(streamUrl, taskId) {
        currentModalId = 'progress-modal';
        openModal(currentModalId); // Убеждаемся, что окно открывается

        const url = new URL(streamUrl, window.location.origin);
        if (taskId) url.searchParams.set('task_id', taskId);
        
        if (eventSource) eventSource.close();
        eventSource = new EventSource(url.toString());

        eventSource.onmessage = function(event) {
            try {
                const data = JSON.parse(event.data);
                
                if (data.percent !== undefined) {
                    updateProgress(data.percent, data.message);
                }

                if (data.logs && Array.isArray(data.logs)) {
                    const logContainer = document.getElementById('gen-progress-log');
                    if (logContainer) {
                        logContainer.innerHTML = ''; 
                        data.logs.forEach(msg => {
                            const li = document.createElement('li');
                            li.textContent = msg;
                            logContainer.appendChild(li);
                        });
                        logContainer.scrollTop = logContainer.scrollHeight;
                    }
                }

                if (data.status === 'done') {
                    finishProgress(true, data.message, data.redirect_url || '/topics/', 3000);
                } else if (data.status === 'error') {
                    finishProgress(false, data.message, null, 0);
                }
            } catch (e) {
                console.error('Ошибка SSE:', e);
            }
        };

        eventSource.onerror = function() {
            console.warn("📡 Потеря связи с сервером...");
        };
    };

    window.stopProgressTracking = function() {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        const closeBtn = document.getElementById('close-progress-modal');
        if (closeBtn) {
            closeBtn.addEventListener('click', function() {
                closeModal(currentModalId);
                stopProgressTracking();
            });
        }
    });
})();