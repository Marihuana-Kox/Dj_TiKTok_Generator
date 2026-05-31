/**
 * МОДУЛЬ ПЕРЕТАСКИВАНИЯ КАДРОВ (DRAG AND DROP) ДЛЯ ТАЙМЛАЙНА
 */

function initDragAndDrop() {
    const clips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    let draggedClip = null;

    clips.forEach(clip => {
        // Явно разрешаем перетаскивание элемента
        clip.setAttribute('draggable', 'true');

        // 1. Начало перетаскивания
        clip.addEventListener('dragstart', (e) => {
            draggedClip = clip;
            clip.classList.add('dragging');
            e.dataTransfer.setData('text/plain', clip.getAttribute('data-order'));
            e.dataTransfer.effectAllowed = 'move';
        });

        // 2. Конец перетаскивания (сброс стилей)
        clip.addEventListener('dragend', () => {
            clip.classList.remove('dragging');
            clips.forEach(c => c.classList.remove('drag-over'));
            draggedClip = null;
        });

        // 3. Кадр пролетает над другим кадром
        clip.addEventListener('dragover', (e) => {
            e.preventDefault(); // КРИТИЧЕСКИ ВАЖНО: без этого drop не сработает!
            if (clip !== draggedClip) {
                clip.classList.add('drag-over');
            }
            return false;
        });

        // 4. Курсор ушел с кадра
        clip.addEventListener('dragleave', () => {
            clip.classList.remove('drag-over');
        });

        // 5. Кадр отпустили над текущим элементом
        clip.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();

            if (clip !== draggedClip && draggedClip !== null) {
                // Сохраняем снимок для Undo перед изменением DOM
                if (typeof window.saveTimelineSnapshot === 'function') {
                    window.saveTimelineSnapshot();
                }

                const parent = clip.parentNode;
                const allClipsArray = Array.from(parent.querySelectorAll('.capcut-clip[data-type="video"]'));
                const draggedIndex = allClipsArray.indexOf(draggedClip);
                const targetIndex = allClipsArray.indexOf(clip);

                if (draggedIndex < targetIndex) {
                    // Перетаскиваем слева направо
                    parent.insertBefore(draggedClip, clip.nextSibling);
                } else {
                    // Перетаскиваем справа налево
                    parent.insertBefore(draggedClip, clip);
                }

                // Переиндексируем стейт
                reindexTimelineState();
            }
            clip.classList.remove('drag-over');
        });
    });
}

// Вспомогательная функция переиндексации после изменения порядка в HTML
function reindexTimelineState() {
    const currentClips = document.querySelectorAll('.capcut-clip[data-type="video"]');
    const newTimelineState = {};
    let newSelectedOrders = [];

    currentClips.forEach((clip, index) => {
        const oldOrder = parseInt(clip.getAttribute('data-order'));
        const newOrder = index + 1; // Создаем новый порядок 1, 2, 3...

        if (window.timelineState[oldOrder]) {
            newTimelineState[newOrder] = window.timelineState[oldOrder];
        }

        clip.setAttribute('data-order', newOrder);
        const badge = clip.querySelector('.capcut-badge');
        if (badge) {
            badge.innerText = `Кадр ${newOrder}`;
        }

        if (window.getSelectedOrders && window.getSelectedOrders().includes(oldOrder)) {
            newSelectedOrders.push(newOrder);
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
}

// Экспортируем в window
window.initDragAndDrop = initDragAndDrop;