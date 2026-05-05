document.addEventListener('DOMContentLoaded', function() {
    const modal = document.getElementById('generation-modal');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const statusText = document.getElementById('status-text');
    const finishAction = document.getElementById('finish-action');

    if (modal && progressBar) {
        modal.classList.remove('d-none');
        setTimeout(() => {
            modal.classList.add('active');
            simulateProgress();
        }, 100);
    }

    function simulateProgress() {
        let width = 0;
        const interval = setInterval(() => {
            if (width >= 100) {
                clearInterval(interval);
                finishGeneration();
            } else {
                width += Math.floor(Math.random() * 8) + 2;
                if (width > 100) width = 100;
                progressBar.style.width = width + '%';
                progressText.innerText = width + '%';
                if (width >= 20 && width < 40) statusText.innerText = "Анализ текста...";
                else if (width >= 40 && width < 70) statusText.innerText = "Генерация промптов...";
                else if (width >= 70 && width < 90) statusText.innerText = "Применение стиля...";
                else statusText.innerText = "Финализация...";
            }
        }, 200);
    }

    function finishGeneration() {
        progressBar.classList.remove('progress-bar-animated');
        statusText.innerText = "✅ Готово! Промпты сгенерированы.";
        statusText.classList.add('text-success');
        if (finishAction) finishAction.classList.remove('d-none');
    }
});

function closeModal() {
    const modal = document.getElementById('generation-modal');
    if (modal) {
        modal.classList.remove('active');
        setTimeout(() => modal.classList.add('d-none'), 300);
    }
}