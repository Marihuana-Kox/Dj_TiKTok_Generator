// ============================================================================
// ARTICLE DASHBOARD — чекбоксы, выделение, массовые действия
// Страница: /article/
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 article_dashboard.js инициализация...');

    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('input[name="selected_articles"]');
    const rows = document.querySelectorAll('.idea-row');
    
    // Элементы управления
    const countVal = document.getElementById('count-val');
    const selectionCount = document.getElementById('selection-count');
    const btnDelete = document.getElementById('btn-delete');
    const btnStatus = document.getElementById('btn-status');
    const statusSelect = document.getElementById('status-select');

    function updateSelection() {
        // Считаем только чекбоксы с НЕПУСТЫМ value
        const checked = Array.from(checkboxes).filter(cb => cb.checked && cb.value);
        const count = checked.length;
        const hasSelection = count > 0;
        
        // Обновляем счётчик
        if (countVal) countVal.textContent = count;
        if (selectionCount) selectionCount.style.display = hasSelection ? 'inline' : 'none';
        
        // Активируем/дезактивируем кнопки И ВЫПАДАЮЩИЙ СПИСОК
        if (btnDelete) btnDelete.disabled = !hasSelection;
        if (btnStatus) btnStatus.disabled = !hasSelection;
        if (statusSelect) statusSelect.disabled = !hasSelection;  // ← ВОТ ЭТО ВКЛЮЧАЕТ СПИСОК

        // Подсветка строк
        checkboxes.forEach((cb, index) => {
            if (rows[index]) {
                rows[index].classList.toggle('bg-selected', cb.checked);
            }
        });
        
        console.log('🔍 updateSelection:', count, 'выбрано, статус-селект активен:', hasSelection);
    }

    // Выбрать все
    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
                cb.dispatchEvent(new Event('change'));
            });
            updateSelection();
        });
    }

    // Отдельные чекбоксы
    checkboxes.forEach(cb => {
        cb.addEventListener('change', function() {
            if (!cb.checked && selectAll) selectAll.checked = false;
            updateSelection();
        });

        // Клик по строке → чекбокс
        const row = cb.closest('.idea-row');
        if (row) {
            row.addEventListener('click', function(e) {
                if (e.target.type !== 'checkbox') {
                    cb.checked = !cb.checked;
                    cb.dispatchEvent(new Event('change'));
                }
            });
        }
    });

    // Проверка при загрузке (для failed проектов)
    updateSelection();

    console.log('✅ article_dashboard.js готов');
});