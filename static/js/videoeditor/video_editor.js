/**
 * МОДУЛЬ УПРАВЛЕНИЯ РЕНДЕРИНГОМ И АВТОМАТИЧЕСКОГО РАСПРЕДЕЛЕНИЯ КЛИПОВ
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log("🎯 Скрипт видеоредактора успешно инициализирован и готов к работе!");

    const renderButton = document.getElementById('startRenderBtn');
    
    const progressBlock = document.getElementById('progressBlock');
    const progressMessage = document.getElementById('progressMessage');
    const progressPercent = document.getElementById('progressPercent');
    const progressBar = document.getElementById('progressBar');
    
    const videoPlayer = document.getElementById('videoPlayer');
    const emptyMonitorState = document.getElementById('emptyMonitorState');
    const downloadVideoBtn = document.getElementById('downloadVideoBtn');
    const videoResultBlock = document.getElementById('videoResultBlock');

    // Находим CSRF-токен
    let csrfToken = '';
    const csrfTokenNode = document.querySelector('[name=csrfmiddlewaretoken]');
    if (csrfTokenNode) {
        csrfToken = csrfTokenNode.value;
    } else {
        const match = document.cookie.match(/csrftoken=([^;]+)/);
        if (match) csrfToken = match[1];
    }

    let checkProgressInterval = null;

    // Автоматически распределяем изображения по длине аудио при загрузке страницы
    renderFlexibleTimeline();

    // Функция запуска рендеринга / пересборки (БЕЗОПАСНАЯ И КОРРЕКТНАЯ ВЕРСИЯ)
    async function initVideoRender(e) {
        if (e) {
            e.preventDefault(); 
            e.stopPropagation(); 
        }
        
        console.log("🚀 Клик по кнопке #startRenderBtn зафиксирован! Запуск...");
        
        const mainPlayer = document.getElementById('main-editor-player');
        if (mainPlayer) {
            mainPlayer.pause();
            mainPlayer.src = "";
            mainPlayer.load();
            mainPlayer.style.display = 'none';
            mainPlayer.classList.add('hidden');
        }
        if (videoPlayer) {
            videoPlayer.pause();
            videoPlayer.src = "";
            videoPlayer.load();
            videoPlayer.style.display = 'none';
            videoPlayer.classList.add('hidden');
        }

        if (renderButton) {
            renderButton.disabled = true;
            renderButton.style.display = 'none';
            renderButton.classList.add('hidden');
        }
        if (downloadVideoBtn) {
            downloadVideoBtn.style.display = 'none';
            downloadVideoBtn.classList.add('hidden');
        }

        if (progressBlock) {
            progressBlock.classList.remove('hidden');
            progressBlock.style.setProperty('display', 'block', 'important');
            progressBlock.style.display = 'block';
        }
        if (progressBar) progressBar.style.width = '5%';
        if (progressPercent) progressPercent.innerText = '5%';
        if (progressMessage) progressMessage.innerText = '🎬 Инициализация MoviePy...';
        
        if (emptyMonitorState) {
            emptyMonitorState.classList.remove('hidden');
            emptyMonitorState.style.display = 'block';
        }
        if (videoResultBlock) {
            videoResultBlock.classList.add('hidden');
            videoResultBlock.style.display = 'none';
        }

        const finalTimelinePayload = [];

        // Читаем физический DOM таймлайна, чтобы новые кадры гарантированно попали в сборку
        const clipsInDOM = document.querySelectorAll('.capcut-clip[data-type="video"]');
        
        clipsInDOM.forEach((clip, index) => {
            const order = index + 1; // Определяем честный порядковый номер кадра на экране
            
            // Заглядываем в стейт, если там пусто — подстрахуемся пустым объектом
            const sceneData = (window.timelineState && window.timelineState[order]) || {};
            
            let imageFilename = "";
            const imgEl = clip.querySelector('img');
            if (imgEl && imgEl.src) {
                // Берём чистый относительный путь из атрибута src (например: "/media/projects/velikaya_lozh_kolumba/pic_1.png")
                // Если там полный URL (http://...), getAttribute('src') всё равно вернёт то, что прописано в HTML
                let srcPath = imgEl.getAttribute('src');
                
                // На всякий случай убираем домен, если он прилетел с http://
                if (srcPath.startsWith('http')) {
                    try {
                        srcPath = new URL(srcPath).pathname;
                    } catch(e) {}
                }
                
                imageFilename = srcPath; 
                console.log("🚀 Передаем на бэкенд полный путь:", imageFilename);
            }
            finalTimelinePayload.push({
                "order": order,
                "meta_settings": {
                    "image_name": imageFilename,
                    "duration": parseFloat(clip.getAttribute('data-duration')) || parseFloat(sceneData.duration) || 17.98,
                    "video_effects": clip.getAttribute('data-effect') || sceneData.video_effects || 'none',
                    "filter": clip.getAttribute('data-filter') || sceneData.filter || 'none',
                    "transition": clip.getAttribute('data-transition') || sceneData.transition || 'none',
                    "mirror_x": clip.getAttribute('data-mirror-x') === 'true' || sceneData.mirror_x === true,
                    "mirror_y": clip.getAttribute('data-mirror-y') === 'true' || sceneData.mirror_y === true,
                    "text_overlay": {
                        "text": clip.getAttribute('data-text') || sceneData.text_overlay?.text || '',
                        "font": clip.getAttribute('data-font') || sceneData.text_overlay?.font || 'Arial',
                        "font_color": clip.getAttribute('data-font-color') || sceneData.text_overlay?.font_color || '#FFFFFF',
                        "position": clip.getAttribute('data-position') || sceneData.text_overlay?.position || 'bottom'
                    },
                    "audio_effects": {
                        "volume": parseInt(sceneData.audio_effects?.volume || 100),
                        "fade_in": parseFloat(sceneData.audio_effects?.fade_in || 0.0),
                        "fade_out": parseFloat(sceneData.audio_effects?.fade_out || 0.0)
                    }
                }
            });
        });

        console.log("📦 Сформирован Payload для отправки на РЕНДЕР:", finalTimelinePayload);

        try {
            let currentUrl = window.location.pathname; 
            if (!currentUrl.endsWith('/')) {
                currentUrl += '/';
            }
            const startRenderUrl = currentUrl + 'start-render/';

            let response = await fetch(startRenderUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-Requested-With': 'XMLHttpRequest',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({ 
                    action: 'start_render',
                    timeline: finalTimelinePayload
                })
            });

            // Безопасно перехватываем ответ сервера в виде текста, защищаясь от HTML-страниц
            let responseText = await response.text();
            let data;
            
            try {
                data = JSON.parse(responseText);
            } catch (jsonErr) {
                console.error('💥 Ошибка! Сервер вместо JSON для рендера прислал HTML.');
                console.error('👉 Ответ сервера:\n', responseText.substring(0, 1000));
                alert('Ошибка сборки! Сервер вернул некорректный ответ. Подробности выведены в консоль (F12).');
                resetButtons();
                return;
            }
            
            if ((data.success || data.status === 'success') && data.task_id) {
                console.log("🚀 Рендеринг успешно запущен! Task ID:", data.task_id);
                startPolling(data.task_id); // Вызываем твою родную функцию опроса состояния задачи
            } else {
                alert('Ошибка запуска: ' + (data.error || data.message || 'Неизвестная ошибка сервера.'));
                resetButtons();
            }
        } catch (err) {
            console.error('💥 Критическая ошибка POST:', err);
            resetButtons();
        }
    }
    function startPolling(taskId) {
        if (checkProgressInterval) clearInterval(checkProgressInterval);
        
        console.log("🕵️‍♂️ Запущен процесс опроса статуса генерации для задачи:", taskId);

        checkProgressInterval = setInterval(async () => {
            try {
                // СТРОИМ ПРАВИЛЬНЫЙ ПУТЬ К СТАТУСУ: вместо "/video/project/18/?task_id=..."
                // отправляем на "/video/project/18/start-render/?task_id=..." или твой выделенный роут.
                // Так как файл статуса создается в той же директории, логично спросить у нашего нового эндпоинта.
                let currentUrl = window.location.pathname;
                if (!currentUrl.endsWith('/')) currentUrl += '/';
                
                // Делаем запрос к start-render, но методом GET, чтобы получить статус JSON, а не запуск
                const statusUrl = `${currentUrl}start-render/?task_id=${taskId}`;

                let response = await fetch(statusUrl, {
                    method: 'GET', // Важно: GET запрос просто читает статус
                    headers: { 'X-Requested-With': 'XMLHttpRequest' }
                });

                if (!response.ok) {
                    console.warn("⚠️ Сервер статуса ответил кодом:", response.status);
                    return;
                }

                let data = await response.json();
                console.log("📊 Текущий статус из файла:", data);

                if (data.status === 'running') {
                    if (progressBar) progressBar.style.width = `${data.progress}%`;
                    if (progressPercent) progressPercent.innerText = `${data.progress}%`;
                    if (progressMessage) progressMessage.innerText = data.message || '🎬 Рендеринг видео...';
                } 
                else if (data.status === 'completed' || data.status === 'success') {
                    clearInterval(checkProgressInterval);
                    if (progressBar) progressBar.style.width = '100%';
                    if (progressPercent) progressPercent.innerText = '100%';
                    if (progressMessage) progressMessage.innerText = '🎉 Видео успешно собрано!';
                    
                    // Показываем плеер с готовым видео
                    if (videoPlayer) {
                        videoPlayer.src = data.video_url;
                        videoPlayer.load();
                        videoPlayer.style.display = 'block';
                        videoPlayer.classList.remove('hidden');
                    }
                    if (videoResultBlock) {
                        videoResultBlock.classList.remove('hidden');
                        videoResultBlock.style.display = 'block';
                    }
                    if (downloadVideoBtn) {
                        downloadVideoBtn.href = data.video_url;
                        downloadVideoBtn.style.display = 'inline-block';
                        downloadVideoBtn.classList.remove('hidden');
                    }
                    if (emptyMonitorState) {
                        emptyMonitorState.classList.add('hidden');
                        emptyMonitorState.style.display = 'none';
                    }
                    if (progressBlock) {
                        progressBlock.classList.add('hidden');
                        progressBlock.style.display = 'none';
                    }
                } 
                else if (data.status === 'failed' || data.status === 'error') {
                    clearInterval(checkProgressInterval);
                    alert('💥 Ошибка рендеринга MoviePy: ' + (data.message || data.error || 'Неизвестный сбой'));
                    resetButtons();
                }
            } catch (err) {
                console.error("💥 Ошибка при получении статуса задачи:", err);
            }
        }, 1500); // Опрашиваем сервер раз в 1.5 секунды
    }

    function resetButtons() {
        if (renderButton) {
            renderButton.disabled = false; 
            renderButton.style.display = 'inline-flex';
            renderButton.classList.remove('hidden');
        }
        if (progressBlock) progressBlock.style.display = 'none';
    }
    if (renderButton) {
        renderButton.addEventListener('click', initVideoRender);
    }
});

function renderFlexibleTimeline() {
    const pixelsPerSecond = 6; 
    const bufferSeconds = 10;
    
    const timebar = document.getElementById('dynamic-timebar');
    if (!timebar) return;

    const videoClips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    const audioClips = document.querySelectorAll('.capcut-clip[data-type="audio"]');

    const audioDisplay = document.getElementById('total-audio-display');
    const videoDisplay = document.getElementById('total-video-display');

    let totalAudioDuration = 0;
    audioClips.forEach(clip => {
        let rawDuration = (clip.getAttribute('data-duration') || "0").replace(',', '.');
        totalAudioDuration += parseFloat(rawDuration) || 0;
    });

    if (totalAudioDuration === 0) totalAudioDuration = 30; 
    if (audioDisplay) audioDisplay.innerText = totalAudioDuration.toFixed(2);

    let totalVideoDuration = 0;
    const autoAlignCheckbox = document.getElementById('auto-align-audio');

    if (autoAlignCheckbox && !autoAlignCheckbox.checked) {
        videoClips.forEach(clip => {
            const order = parseInt(clip.getAttribute('data-order'));
            
            let baseDuration = 5.0;
            if (window.timelineState && window.timelineState[order]) {
                baseDuration = parseFloat(window.timelineState[order].duration) || parseFloat(clip.getAttribute('data-duration')) || 5.0;
            } else {
                baseDuration = parseFloat(clip.getAttribute('data-duration')) || 5.0;
            }

            if (window.timelineState && window.timelineState[order] && window.timelineState[order].user_duration !== undefined) {
                baseDuration = parseFloat(window.timelineState[order].user_duration);
            }

            let finalClipDuration = baseDuration;

            if (window.timelineState && window.timelineState[order]) {
                window.timelineState[order].user_duration = baseDuration; 
                window.timelineState[order].duration = finalClipDuration;
            }

            clip.style.width = (finalClipDuration * pixelsPerSecond) + 'px';
            totalVideoDuration += finalClipDuration; 
            
            if (typeof window.updateBadgesVisibility === 'function') {
                window.updateBadgesVisibility(order);
            }
        });
    } else {
        if (videoClips.length > 0) {
            const baseDurationPerImage = totalAudioDuration / videoClips.length;

            videoClips.forEach(clip => {
                const order = parseInt(clip.getAttribute('data-order'));
                let finalClipDuration = baseDurationPerImage;

                if (window.timelineState && window.timelineState[order]) {
                    window.timelineState[order].duration = parseFloat(finalClipDuration.toFixed(2));
                }

                clip.setAttribute('data-duration', finalClipDuration.toFixed(2));
                clip.style.width = (finalClipDuration * pixelsPerSecond) + 'px';
                
                if (typeof window.updateBadgesVisibility === 'function') {
                    window.updateBadgesVisibility(order);
                }
            });
            
            totalVideoDuration = totalAudioDuration;
        }
    }

    if (totalVideoDuration < 0) totalVideoDuration = 0;
    if (videoDisplay) videoDisplay.innerText = totalVideoDuration.toFixed(2);

    const maxDuration = Math.max(totalAudioDuration, totalVideoDuration);
    drawTimelineTicks(maxDuration, 10, pixelsPerSecond, timebar);
}

function drawTimelineTicks(duration, buffer, pixelsPerSecond, timebar) {
    const scaleTotalSeconds = Math.ceil(duration + buffer);
    timebar.innerHTML = '';

    for (let s = 0; s <= scaleTotalSeconds; s++) {
        const tick = document.createElement('div');
        tick.className = 'time-tick';
        tick.style.width = pixelsPerSecond + 'px';

        if (s % 5 === 0) {
            tick.classList.add('major');
            tick.innerHTML = `<span>${s}s</span>`;
        } else {
            tick.innerHTML = ``;
        }
        timebar.appendChild(tick);
    }
}

window.renderFlexibleTimeline = renderFlexibleTimeline;

document.addEventListener('DOMContentLoaded', () => {
    const autoAlignCheckbox = document.getElementById('auto-align-audio');
    
    if (autoAlignCheckbox) {
        autoAlignCheckbox.addEventListener('change', () => {
            window.renderFlexibleTimeline();
        });
    }

    document.addEventListener('input', (e) => {
        if (e.target.classList.contains('scene-duration-input') || e.target.id === 'clipDurationInput') {
            let order = e.target.closest('[data-order]')?.getAttribute('data-order');
            if (!order && window.getSelectedOrders) {
                const selected = window.getSelectedOrders();
                if (selected.length > 0) order = selected[selected.length - 1];
            }
            
            if (order && window.timelineState && window.timelineState[order]) {
                window.timelineState[order].duration = parseFloat(e.target.value) || 0;
                window.timelineState[order].user_duration = parseFloat(e.target.value) || 0;
            }

            if (autoAlignCheckbox && autoAlignCheckbox.checked) {
                autoAlignCheckbox.checked = false;
                console.log("📌 Автоподгон отключен из-за ручного изменения секунд кадра.");
            }
            
            window.renderFlexibleTimeline();
        }
    });

    document.addEventListener('change', (e) => {
        if (e.target.classList.contains('scene-transition-select') || e.target.id === 'clipTransitionType') {
            let order = e.target.closest('[data-order]')?.getAttribute('data-order');
            if (!order && window.getSelectedOrders) {
                const selected = window.getSelectedOrders();
                if (selected.length > 0) order = selected[selected.length - 1];
            }
            
            if (order && window.timelineState && window.timelineState[order]) {
                window.timelineState[order].transition = e.target.value;
            }

            window.renderFlexibleTimeline();
        }
    });
});