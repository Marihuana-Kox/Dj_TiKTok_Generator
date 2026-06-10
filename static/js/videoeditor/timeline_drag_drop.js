/**
 * МОДУЛЬ ПЕРЕТАСКИВАНИЯ КАДРОВ (DRAG AND DROP) ДЛЯ ТАЙМЛАЙНА С АВТОСОХРАНЕНИЕМ
 */
let hasChanges = false;
let draggedClip = null; // Выносим в глобальную область модуля

// Функция навешивания Drag & Drop на ОДИН конкретный элемент (вызывается при создании кадра)
function attachDragAndDropToElement(clip) {
    clip.setAttribute('draggable', 'true');

    clip.addEventListener('dragstart', (e) => {
        draggedClip = clip;
        clip.classList.add('dragging');
        e.dataTransfer.setData('text/plain', clip.getAttribute('data-order'));
        e.dataTransfer.effectAllowed = 'move';
    });

    clip.addEventListener('dragend', () => {
        clip.classList.remove('dragging');
        document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(c => c.classList.remove('drag-over'));
        draggedClip = null;
    });

    clip.addEventListener('dragover', (e) => {
        e.preventDefault();
        if (clip !== draggedClip) {
            clip.classList.add('drag-over');
        }
        return false;
    });

    clip.addEventListener('dragleave', () => {
        clip.classList.remove('drag-over');
    });

    clip.addEventListener('drop', (e) => {
        e.preventDefault();
        e.stopPropagation();

        if (clip !== draggedClip && draggedClip !== null) {
            if (typeof window.saveTimelineSnapshot === 'function') {
                window.saveTimelineSnapshot();
            }

            const parent = clip.parentNode;
            const allClipsArray = Array.from(parent.querySelectorAll('.capcut-clip[data-type="video"]'));
            const draggedIndex = allClipsArray.indexOf(draggedClip);
            const targetIndex = allClipsArray.indexOf(clip);

            if (draggedIndex < targetIndex) {
                parent.insertBefore(draggedClip, clip.nextSibling);
            } else {
                parent.insertBefore(draggedClip, clip);
            }

            hasChanges = true; 
            reindexTimelineState();
        }
        clip.classList.remove('drag-over');
    });
}

// Старая функция теперь просто массово обрабатывает все элементы при старте
function initDragAndDrop() {
    const clips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    clips.forEach(clip => {
        attachDragAndDropToElement(clip);
    });
}

// Экспортируем функции в глобальное окно window
window.initDragAndDrop = initDragAndDrop;
window.attachDragAndDropToElement = attachDragAndDropToElement;
window.reindexTimelineState = reindexTimelineState;

// ... (Весь остальной твой код: reindexTimelineState, collectTimelineData, автосохранение и события зеркалирования ОСТАЮТСЯ БЕЗ ИЗМЕНЕНИЙ) ...
function reindexTimelineState() {
    const currentClips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    const newTimelineState = {};
    let newSelectedOrders = [];

    currentClips.forEach((clip, index) => {
        const oldOrder = parseInt(clip.getAttribute('data-order'));
        const newOrder = index + 1;

        if (window.timelineState[oldOrder]) {
            newTimelineState[newOrder] = window.timelineState[oldOrder];
        }

        clip.setAttribute('data-order', newOrder);
        
        const innerCard = clip.querySelector('.image-asset-card.video-block');
        if (innerCard) {
            innerCard.setAttribute('data-order', newOrder);
        }

        const badge = clip.querySelector('.capcut-badge');
        if (badge) {
            badge.innerText = `Кадр ${newOrder}`;
        }

        if (window.getSelectedOrders && window.getSelectedOrders().includes(oldOrder)) {
            newSelectedOrders.push(newOrder);
        }
        if (typeof window.syncResourceBarButtons === 'function') {
            window.syncResourceBarButtons();
        }
    });

    window.timelineState = newTimelineState;
    if (typeof window.setSelectedOrders === 'function') {
        window.setSelectedOrders(newSelectedOrders);
    }

    const titleEl = document.getElementById('selectedClipTitle');
    if (titleEl && window.getSelectedOrders) {
        titleEl.innerText = `(Выделено сцен: ${window.getSelectedOrders().length})`;
    }

    if (typeof window.refreshTimelineLayout === 'function') {
        window.refreshTimelineLayout();
    }

    if (typeof window.triggerAutoSave === 'function') {
        window.triggerAutoSave();
    }
}

// Экспортируем в window
window.initDragAndDrop = initDragAndDrop;
window.reindexTimelineState = reindexTimelineState;


// =========================================================================
// ЕДИНАЯ ОЧИЩЕННАЯ ФУНКЦИЯ СБОРА ТЕКУЩИХ ДАННЫХ ДЛЯ ОТПРАВКИ НА СЕРВЕР
// =========================================================================
function collectTimelineData() {
    let timeline = [];
    const videoBlocks = document.querySelectorAll('.image-asset-card.video-block');
    
    window.timelineState = window.timelineState || {};
    
    videoBlocks.forEach((block, index) => {
        const originalOrder = parseInt(block.getAttribute('data-order')) || (index + 1);
        
        const imgEl = block.querySelector('img');
        const namePic = imgEl ? (imgEl.getAttribute('src') || "Image") : "Image";

        if (!window.timelineState[originalOrder]) {
            window.timelineState[originalOrder] = {};
        }
        
        const stateConfig = window.timelineState[originalOrder];
        
        if (stateConfig.duration === undefined) stateConfig.duration = parseFloat(block.getAttribute('data-duration')) || 5.0;
        if (stateConfig.video_effects === undefined) stateConfig.video_effects = block.getAttribute('data-effect') || "none";
        if (stateConfig.filter === undefined) stateConfig.filter = block.getAttribute('data-filter') || "none";
        if (stateConfig.transition === undefined) stateConfig.transition = block.getAttribute('data-transition') || "none";
        
        // Надежное восстановление флагов зеркалирования при сохранении
        if (stateConfig.mirror_x === undefined) {
            stateConfig.mirror_x = block.getAttribute('data-mirror-x') === 'true';
        }
        if (stateConfig.mirror_y === undefined) {
            stateConfig.mirror_y = block.getAttribute('data-mirror-y') === 'true';
        }
        
        if (!stateConfig.text_overlay) {
            stateConfig.text_overlay = {
                text: block.getAttribute('data-text') || "", 
                font: block.getAttribute('data-font') || "Arial", 
                font_size: 30, 
                font_color: block.getAttribute('data-font-color') || "#FFFFFF", 
                position: block.getAttribute('data-position') || "bottom"
            };
        }
        if (!stateConfig.audio_effects) {
            stateConfig.audio_effects = { volume: 100, fade_in: 0, fade_out: 0 };
        }
        
        timeline.push({
            "order": originalOrder,
            "meta_settings": {
                "image_name": namePic.substring(namePic.lastIndexOf('/') + 1), 
                "duration": stateConfig.duration.toString(),
                "video_effects": stateConfig.video_effects,
                "filter": stateConfig.filter,
                "transition": stateConfig.transition,
                "mirror_x": stateConfig.mirror_x,
                "mirror_y": stateConfig.mirror_y,
                "text_overlay": stateConfig.text_overlay,
                "audio_effects": stateConfig.audio_effects
            }
        });
        if (typeof window.syncResourceBarButtons === 'function') {
            window.syncResourceBarButtons();
        }
    });
    
    return timeline;
}
window.collectTimelineData = collectTimelineData; 


// Работа с черновиками БД при загрузке
document.addEventListener("DOMContentLoaded", function () {
    const timelineContainer = document.getElementById("timeline-main-panel");
    if (!timelineContainer) return;

    let savedConfig = [];
    
    const jsonScriptTag = document.getElementById("my-saved-draft-json");
    if (jsonScriptTag) {
        try {
            savedConfig = JSON.parse(jsonScriptTag.textContent);
        } catch (e) {
            console.error("Ошибка парсинга скрытого JSON черновика:", e);
        }
    }

    function getCsrfToken() {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, 10) === ('csrftoken=')) {
                    cookieValue = decodeURIComponent(cookie.substring(10));
                    break;
                }
            }
        }
        if (!cookieValue) {
            cookieValue = document.querySelector('[name=csrfmiddlewaretoken]')?.value;
        }
        return cookieValue;
    }

    function autoSaveTimeline() {
        if (!hasChanges) {
            console.log("⚡ Изменений нет, автосохранение пропущено.");
            return;
        }

        const currentData = collectTimelineData();
        console.log("💾 Отправка данных автосохранения на сервер...", currentData);

        let token = '';
        const csrfNode = document.querySelector('[name=csrfmiddlewaretoken]');
        if (csrfNode) token = csrfNode.value;

        // Сборка правильного URL пути для черновика Django
        let currentUrl = window.location.pathname; // Получим, например, "/video/project/18/"
        
        if (!currentUrl.endsWith('/')) {
            currentUrl += '/';
        }
        const saveDraftUrl = currentUrl + 'save-draft/'; // Итоговый "/video/project/18/save-draft/"

        // Передаем точное имя переменной saveDraftUrl без опечаток
        fetch(saveDraftUrl, { 
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": token,
                "X-Requested-With": "XMLHttpRequest"
            },
            body: JSON.stringify({
                action: "save_config", 
                timeline: currentData
            })
        })
        .then(response => {
            return response.text().then(text => {
                return {
                    ok: response.ok,
                    status: response.status,
                    text: text
                };
            });
        })
        .then(res => {
            try {
                const data = JSON.parse(res.text);
                
                if (data.success || data.status === 'success') {
                    console.log("✅ Таймлайн успешно автосохранен в черновик Django!");
                    hasChanges = false; // Сбрасываем флаг изменений только при успехе
                } else {
                    console.warn("⚠️ Сервер вернул ошибку сохранения:", data.message || data.error);
                }
            } catch (jsonErr) {
                console.error("💥 ОШИБКА БЭКЕНДА: save-draft вернул не JSON!");
                console.error(`HTTP Статус: ${res.status}`);
                console.error("👉 ОТВЕТ СЕРВЕРА (Первые 500 символов):\n", res.text.substring(0, 500));
                hasChanges = false; 
            }
        })
        .catch(err => {
            console.error("💥 Ошибка сети при автосохранении:", err);
            hasChanges = false;
        });
    }
    window.triggerAutoSave = autoSaveTimeline;

    function getSelectedClipsElements(fallbackBlock) {
        let targets = [];
        if (window.getSelectedOrders && window.getSelectedOrders().length > 0) {
            window.getSelectedOrders().forEach(order => {
                const el = document.querySelector(`.capcut-clip[data-order="${order}"]`);
                if (el) targets.push(el);
            });
        } else {
            const selectedDom = document.querySelectorAll('.capcut-clip.selected, .capcut-clip.active');
            if (selectedDom.length > 0) targets = Array.from(selectedDom);
        }
        if (targets.length === 0 && fallbackBlock) {
            targets.push(fallbackBlock);
        }
        return targets;
    }

    // =========================================================================
    // ЕДИНАЯ ТОЧКА СЛУШАНИЯ КНОПОК ЗЕРКАЛИРОВАНИЯ (ИНСПЕКТОР)
    // =========================================================================
    document.addEventListener('click', function(e) {
        const btnX = e.target.closest('#clipMirrorX');
        const btnY = e.target.closest('#clipMirrorY');
        
        if (!btnX && !btnY) return; 

        console.log(`Пойман клик на кнопку зеркалирования! X: ${!!btnX}, Y: ${!!btnY}`);

        let activeBlock = document.querySelector('.capcut-clip.selected') || document.querySelector('.capcut-clip.active');
        if (!activeBlock && timelineContainer.hasAttribute('data-active-clip-id')) {
            activeBlock = document.querySelector(`.capcut-clip[data-id="${timelineContainer.getAttribute('data-active-clip-id')}"]`);
        }
        
        const targetClips = getSelectedClipsElements(activeBlock);
        if (targetClips.length === 0) return;

        if (typeof window.saveTimelineSnapshot === 'function') {
            window.saveTimelineSnapshot();
        }

        // ОБРАБОТКА ЗЕРКАЛА X
        if (btnX) {
            const currentSelectedOrder = window.getSelectedOrders()[window.getSelectedOrders().length - 1] || parseInt(activeBlock?.getAttribute('data-order'));
            const currentMirrorState = window.timelineState[currentSelectedOrder]?.mirror_x || false;
            const nextMirrorState = !currentMirrorState;

            btnX.classList.toggle('active-fx-btn', nextMirrorState);

            targetClips.forEach(clip => {
                const order = parseInt(clip.getAttribute('data-order'));
                clip.setAttribute('data-mirror-x', nextMirrorState ? 'true' : 'false');
                
                const innerCard = clip.querySelector('.image-asset-card.video-block');
                if (innerCard) innerCard.setAttribute('data-mirror-x', nextMirrorState ? 'true' : 'false');

                if (order && window.timelineState[order]) {
                    window.timelineState[order].mirror_x = nextMirrorState;
                }
                if (typeof window.updateBadgesVisibility === 'function') {
                    window.updateBadgesVisibility(order);
                }
            });

            // Обновляем главный монитор превью
            const previewImage = document.getElementById('monitor-preview-image');
            if (previewImage && window.timelineState[currentSelectedOrder]) {
                const scaleX = window.timelineState[currentSelectedOrder].mirror_x ? '-1' : '1';
                const scaleY = window.timelineState[currentSelectedOrder].mirror_y ? '-1' : '1';
                previewImage.style.transform = `scale(${scaleX}, ${scaleY})`;
            }
        }

        // ОБРАБОТКА ЗЕРКАЛА Y
        if (btnY) {
            const currentSelectedOrder = window.getSelectedOrders()[window.getSelectedOrders().length - 1] || parseInt(activeBlock?.getAttribute('data-order'));
            const currentMirrorState = window.timelineState[currentSelectedOrder]?.mirror_y || false;
            const nextMirrorState = !currentMirrorState;

            btnY.classList.toggle('active-fx-btn', nextMirrorState);

            targetClips.forEach(clip => {
                const order = parseInt(clip.getAttribute('data-order'));
                clip.setAttribute('data-mirror-y', nextMirrorState ? 'true' : 'false');
                
                const innerCard = clip.querySelector('.image-asset-card.video-block');
                if (innerCard) innerCard.setAttribute('data-mirror-y', nextMirrorState ? 'true' : 'false');

                if (order && window.timelineState[order]) {
                    window.timelineState[order].mirror_y = nextMirrorState;
                }
                if (typeof window.updateBadgesVisibility === 'function') {
                    window.updateBadgesVisibility(order);
                }
            });

            // Обновляем главный монитор превью
            const previewImage = document.getElementById('monitor-preview-image');
            if (previewImage && window.timelineState[currentSelectedOrder]) {
                const scaleX = window.timelineState[currentSelectedOrder].mirror_x ? '-1' : '1';
                const scaleY = window.timelineState[currentSelectedOrder].mirror_y ? '-1' : '1';
                previewImage.style.transform = `scale(${scaleX}, ${scaleY})`;
            }
        }

        autoSaveTimeline();
        hasChanges = true;
    });

    // Глобальный триггер изменений в инспекторе
    document.addEventListener('change', function(e) {
        const target = e.target;

        if (target.matches('.effect-select, .filter-select, .duration-input, .text-overlay-input, .font-select, .font-color-input, .position-select, #clipTransitionType')) {
            
            let activeBlock = document.querySelector('.capcut-clip.selected') || target.closest('.capcut-clip');

            if (!activeBlock && timelineContainer.hasAttribute('data-active-clip-id')) {
                const activeId = timelineContainer.getAttribute('data-active-clip-id');
                activeBlock = document.querySelector(`.capcut-clip[data-id="${activeId}"]`);
            }

            const targetClips = getSelectedClipsElements(activeBlock);

            if (targetClips.length > 0) {
                targetClips.forEach(clip => {
                    const order = parseInt(clip.getAttribute('data-order'));
                    if (!order) return;
                    
                    if (!window.timelineState[order]) window.timelineState[order] = {};

                    if (target.classList.contains('effect-select')) {
                        clip.setAttribute('data-effect', target.value);
                        window.timelineState[order].video_effects = target.value;
                    }
                    else if (target.classList.contains('filter-select')) {
                        clip.setAttribute('data-filter', target.value);
                        window.timelineState[order].filter = target.value;
                    }
                    else if (target.id === 'clipTransitionType' || target.classList.contains('transition-select')) {
                        clip.setAttribute('data-transition', target.value);
                        window.timelineState[order].transition = target.value;
                    }
                    else if (target.classList.contains('duration-input')) {
                        clip.setAttribute('data-duration', target.value);
                        window.timelineState[order].duration = parseFloat(target.value);
                        const newWidth = parseFloat(target.value) * 6;
                        clip.style.width = `${newWidth}px`;
                    }
                    
                    if (!window.timelineState[order].text_overlay) window.timelineState[order].text_overlay = {};
                    
                    if (target.classList.contains('text-overlay-input')) {
                        clip.setAttribute('data-text', target.value);
                        window.timelineState[order].text_overlay.text = target.value;
                    }
                    else if (target.classList.contains('font-select')) {
                        clip.setAttribute('data-font', target.value);
                        window.timelineState[order].text_overlay.font = target.value;
                    }
                    else if (target.classList.contains('font-color-input')) {
                        clip.setAttribute('data-font-color', target.value);
                        window.timelineState[order].text_overlay.font_color = target.value;
                    }
                    else if (target.classList.contains('position-select')) {
                        clip.setAttribute('data-position', target.value);
                        window.timelineState[order].text_overlay.position = target.value;
                    }
                });

                console.log(`⚙️ Параметры массово обновлены в HTML data-атрибутах для выделенных кадров (${targetClips.length} шт). Автосохранение...`);
                
                hasChanges = true;
                autoSaveTimeline();
            }
        }
    });

    if (savedConfig && savedConfig.length > 0) {
        if (typeof window.restoreTimelineFromJSON === 'function') {
            window.restoreTimelineFromJSON(savedConfig);
        }
    }
    if (typeof window.syncResourceBarButtons === 'function') {
        window.syncResourceBarButtons();
    }
});

// Синхронный глобальный хук изменений структуры DOM
window.updateTimelineAfterDOMChange = function() {
    console.log("🧩 DOM таймлайна изменился. Выполняем сохранение...");
    
    collectTimelineData();

    if (typeof window.renderFlexibleTimeline === 'function') {
        window.renderFlexibleTimeline();
    }
    if (typeof window.triggerAutoSave === 'function') {
        window.triggerAutoSave();
    }
    if (typeof window.syncResourceBarButtons === 'function') {
        window.syncResourceBarButtons();
    }
};

/**
 * Отправка JSON перед перезагрузкой страницы
 */
window.addEventListener('beforeunload', (event) => {
    // 1. Проверяем, нужны ли изменения и есть ли функция
    if (hasChanges && typeof window.collectTimelineData === 'function') {
        
        // 2. Собираем данные
        const currentData = window.collectTimelineData();
        
        // 3. Формируем полезную нагрузку
        const payload = JSON.stringify({ 
            "timeline": currentData 
        });
        
        // 4. Отправляем на правильный эндпоинт (тот, что у нас для сохранения)
        const saveUrl = window.location.pathname + "save-draft/";
        
        // Navigator.sendBeacon отлично работает со строками и объектами Blob
        navigator.sendBeacon(saveUrl, payload);
        
        console.log("🚀 Автосохранение при закрытии страницы...");
    }
    if (typeof window.syncResourceBarButtons === 'function') {
        window.syncResourceBarButtons();
    }
});
// Клонирование картинки на таймлайн
// Клонирование картинки на таймлайн (ОБНОВЛЕННАЯ ВЕРСИЯ)
window.addImageToTimelineFromResource = function(fileName) {
    console.log("🚀 Пытаюсь вернуть на таймлайн файл:", fileName);

    const timelineTrack = document.querySelector('.timeline-track.video-track');
    if (!timelineTrack) {
        console.error("Контейнер .timeline-track.video-track не найден!");
        return;
    }

    const nextOrder = document.querySelectorAll('.capcut-clip[data-type="video"]').length + 1;
    const defaultDuration = 17.98; 
    const calculatedWidth = defaultDuration * 6; 

    const newClip = document.createElement('div');
    
    // СРАЗУ добавляем классы active и selected-active, чтобы он загорелся на экране
    newClip.className = 'image-asset-card capcut-clip video-block has-transition selected-active active';
    
    // Снимаем выделение со всех предыдущих кадров в DOM
    document.querySelectorAll('.capcut-clip[data-type="video"]').forEach(c => {
        c.classList.remove('selected', 'active', 'selected-active');
    });

    newClip.setAttribute('data-id', 'temp_' + Date.now());
    newClip.setAttribute('data-type', 'video');
    newClip.setAttribute('data-order', nextOrder);
    newClip.setAttribute('data-duration', defaultDuration.toFixed(2));
    newClip.setAttribute('data-effect', 'none');
    newClip.setAttribute('data-filter', 'none');
    newClip.setAttribute('data-transition', 'none');
    newClip.setAttribute('data-mirror-x', 'false');
    newClip.setAttribute('data-mirror-y', 'false');
    newClip.setAttribute('data-text', '');
    newClip.setAttribute('data-font', 'Arial');
    newClip.setAttribute('data-font-color', '#FFFFFF');
    newClip.setAttribute('data-position', 'bottom');
    newClip.style.width = `${calculatedWidth}px`;

    newClip.innerHTML = `
        <img src="/media/projects/velikaya_lozh_kolumba/${fileName}" alt="">
        <span class="capcut-badge">Кадр ${nextOrder}</span>
        <div class="clip-fx-status-bar">
            <span class="fx-badge badge-anim">FX</span>
            <span class="fx-badge badge-filter">🎨</span>
            <span class="fx-badge badge-trans">🔀</span>
            <span class="fx-badge badge-text">📝</span>
            <span class="fx-badge badge-mirror-x" style="display: none;">↔</span>
            <span class="fx-badge badge-mirror-y" style="display: none;">↕</span>
        </div>
    `;

    // Создаем дефолтное состояние в глобальном window.timelineState до вставки
    window.timelineState = window.timelineState || {};
    window.timelineState[nextOrder] = {
        duration: defaultDuration,
        user_duration: defaultDuration,
        video_effects: "none",
        filter: "none",
        transition: "none",
        mirror_x: false,
        mirror_y: false,
        text_overlay: { text: "", font: "Arial", font_size: 30, font_color: "#FFFFFF", position: "bottom" },
        audio_effects: { volume: 100, fade_in: 0, fade_out: 0 }
    };

    // Обновляем массив выделенных кадров (теперь выделен только наш новый кадр)
    if (typeof window.setSelectedOrders === 'function') {
        window.setSelectedOrders([nextOrder]);
    }

    // МАКСИМАЛЬНО ВАЖНО: Вешаем клики, инспектор и drag-n-drop на новый кадр ДО добавления в DOM
    if (typeof window.attachClipEvents === 'function') {
        window.attachClipEvents(newClip);
    }

    // Вставляем на таймлайн
    timelineTrack.appendChild(newClip);

    // Пересчитываем сетку таймлайна, чтобы тики (секунды) сверху дорисовывались
    if (typeof window.refreshTimelineLayout === 'function') {
        window.refreshTimelineLayout();
    }

    // Загружаем данные нового кадра в правую панель параметров (инспектор)
    if (typeof window.loadClipSettingsToPanel === 'function') {
        window.loadClipSettingsToPanel(nextOrder);
    }

    if (typeof window.reindexTimelineState === 'function') {
        window.reindexTimelineState();
    }
    if (typeof window.syncResourceBarButtons === 'function') {
        window.syncResourceBarButtons();
    }
    
    hasChanges = true;
    if (typeof window.triggerAutoSave === 'function') {
        window.triggerAutoSave();
    }

    console.log(`🖼️ Кадр ${fileName} полностью интегрирован, активирован и готов к работе без перезагрузки!`);
};