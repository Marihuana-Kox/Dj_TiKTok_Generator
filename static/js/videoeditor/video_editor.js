document.addEventListener("DOMContentLoaded", function () {
    const container = document.querySelector(".capcut-container");
    if (!container) return;

    const projectId = container.getAttribute("data-project-id");
    const renderBtn = document.getElementById("render-video-btn");
    const statusBlock = document.getElementById("render-status-block");
    const progressFill = document.getElementById("render-progress-bar");
    const percentText = document.getElementById("render-status-percent");
    const statusMsg = document.getElementById("render-status-msg");
    const previewContainer = document.getElementById("video-preview-container");

    // 🔥 ЭЛЕМЕНТЫ ДЛЯ ПЕРЕКЛЮЧАТЕЛЯ ФОРМАТА
    const ratioBtn = document.getElementById("ratio-toggle-btn");
    const previewBox = document.getElementById("video-preview-container");
    const ratioLabel = document.getElementById("ratio-text-label");
    
    // Переменная хранит текущий выбор (по умолчанию горизонтальный)
    let selectedRatio = "16x9"; 
    let currentAudio = null;

    // 1. ИНТЕРАКТИВНЫЙ ТАЙМЛАЙН: Прослушивание аудио при клике на дорожку A1
    document.querySelectorAll(".play-audio-btn").forEach(clip => {
        clip.addEventListener("click", function () {
            const audioUrl = this.getAttribute("data-src");
            if (!audioUrl) return;

            // Если кликнули по уже играющему треку — ставим на паузу
            if (currentAudio && !currentAudio.paused && currentAudio.src === window.location.origin + audioUrl) {
                currentAudio.pause();
                this.style.borderColor = "rgba(255,255,255,0.08)";
                return;
            }

            // Останавливаем прошлый трек, если он играл
            if (currentAudio) {
                currentAudio.pause();
                document.querySelectorAll(".play-audio-btn").forEach(c => c.style.borderColor = "rgba(255,255,255,0.08)");
            }

            // Запускаем воспроизведение клипа таймлайна
            currentAudio = new Audio(audioUrl);
            currentAudio.play();
            this.style.borderColor = "#00ff87";

            currentAudio.onended = () => {
                this.style.borderColor = "rgba(255,255,255,0.08)";
            };
        });
    });

    // 🔥 2. ЛОГИКА КЛИКА ПО КНОПКЕ ПЕРЕКЛЮЧЕНИЯ ФОРМАТА (16:9 <=> 9:16)
    if (ratioBtn && previewBox) {
        ratioBtn.addEventListener("click", function () {
            if (selectedRatio === "16x9") {
                selectedRatio = "9x16";
                previewBox.classList.remove("aspect-16x9");
                previewBox.classList.add("aspect-9x16");
                ratioBtn.setAttribute("data-current-ratio", "9x16");
                ratioLabel.innerText = "Формат: 9:16 (Shorts/TikTok)";
                ratioBtn.querySelector(".ratio-icon").innerText = "📱";
            } else {
                selectedRatio = "16x9";
                previewBox.classList.remove("aspect-9x16");
                previewBox.classList.add("aspect-16x9");
                ratioBtn.setAttribute("data-current-ratio", "16x9");
                ratioLabel.innerText = "Формат: 16:9 (YouTube)";
                ratioBtn.querySelector(".ratio-icon").innerText = "📺";
            }
            console.log("🎬 Изменено соотношение сторон в интерфейсе:", selectedRatio);
        });
    }

    // 3. ВЗАИМОДЕЙСТВИЕ С BACKEND (MoviePy Экспорт через AJAX)
    if (renderBtn) {
        renderBtn.addEventListener("click", function () {
            renderBtn.disabled = true;
            renderBtn.innerText = "⏳ Экспорт...";
            statusBlock.classList.remove("d-none");

            // Инициализируем POST запрос к нашей Django вьюшке
            fetch(window.location.pathname, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-Requested-With": "XMLHttpRequest",
                    "X-CSRFToken": getCsrfToken()
                },
                // 🔥 ТЕПЕРЬ ТУТ ЧЕСТНО ОТПРАВЛЯЕТСЯ ТЕКУЩИЙ ВЫБРАННЫЙ РЕЖИМ СЮДА!
                body: JSON.stringify({ 
                    action: "start_render",
                    aspect_ratio: selectedRatio 
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success && data.task_id) {
                    // Включаем пулинг прогресса сборки
                    trackRenderProgress(data.task_id);
                } else {
                    alert("Ошибка старта: " + (data.error || "Неизвестный сбой"));
                    resetRenderButton();
                }
            })
            .catch(err => {
                console.error("Ошибка сети:", err);
                resetRenderButton();
            });
        });
    }

    // Функция циклического опроса состояния кэша Джанго
    function trackRenderProgress(taskId) {
        const interval = setInterval(() => {
            fetch(`${window.location.pathname}?task_id=${taskId}`, {
                headers: { "X-Requested-With": "XMLHttpRequest" }
            })
            .then(res => res.json())
            .then(data => {
                if (data.status === "error") {
                    clearInterval(interval);
                    statusMsg.innerText = data.message;
                    statusMsg.style.color = "#ef4444";
                    resetRenderButton();
                } else if (data.status === "done" || data.completed) {
                    clearInterval(interval);
                    progressFill.style.width = "100%";
                    percentText.innerText = "100%";
                    statusMsg.innerText = "🎉 Сборка завершена!";
                    
                    // Перезагружаем страницу через 1.5 секунды, чтобы плеер отобразил готовый mp4 файл
                    setTimeout(() => {
                        window.location.reload();
                    }, 1500);
                } else {
                    // Обновляем состояние прогресс-бара под плеером
                    const pct = data.percent || 0;
                    progressFill.style.width = pct + "%";
                    percentText.innerText = pct + "%";
                    statusMsg.innerText = data.message || "Сборка видеопотока...";
                }
            })
            .catch(err => {
                console.error("Ошибка пулинга:", err);
                clearInterval(interval);
            });
        }, 2000); // Опрос каждые 2 секунды
    }

    function resetRenderButton() {
        if (renderBtn) {
            renderBtn.disabled = false;
            renderBtn.innerText = "🎬 Собрать готовый ролик (.mp4)";
        }
    }

    function getCsrfToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== "") {
            const cookies = document.cookie.split(";");
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === "csrftoken=") {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        return cookieValue;
    }
});