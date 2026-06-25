/**
 * Video Script List - Bulk Actions
 * Обработка массовых действий (выделение, удаление, смена статуса)
 */

document.addEventListener('DOMContentLoaded', function() {
    // Элементы управления
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.idea-checkbox');
    const rows = document.querySelectorAll('.idea-row');
    const btnDelete = document.getElementById('btn-delete');
    const btnStatus = document.getElementById('btn-status');
    const statusSelect = document.getElementById('status-select');
    const selectionCount = document.getElementById('selection-count');
    const countVal = document.getElementById('count-val');

    /**
     * Обновление состояния кнопок и счётчика
     */
    function updateButtons() {
        const checked = document.querySelectorAll('.idea-checkbox:checked').length;
        const hasSelection = checked > 0;
        
        // Включаем/отключаем кнопки
        if (btnDelete) {
            btnDelete.disabled = !hasSelection;
        }
        
        if (btnStatus) {
            btnStatus.disabled = !hasSelection || (statusSelect && !statusSelect.value);
        }
        
        // Показываем/скрываем счётчик
        if (selectionCount && countVal) {
            if (hasSelection) {
                selectionCount.style.display = 'inline';
                countVal.textContent = checked;
            } else {
                selectionCount.style.display = 'none';
            }
        }
    }

    /**
     * Обработчик "Выбрать все"
     */
    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach((cb, index) => {
                cb.checked = selectAll.checked;
                if (rows[index]) {
                    rows[index].classList.toggle('bg-selected', selectAll.checked);
                }
            });
            updateButtons();
        });
    }

    /**
     * Обработчики индивидуальных чекбоксов
     */
    checkboxes.forEach((cb, index) => {
        cb.addEventListener('change', function() {
            // Подсветка строки
            if (rows[index]) {
                rows[index].classList.toggle('bg-selected', cb.checked);
            }
            
            // Снимаем "Выбрать все", если хотя бы один снят
            if (!cb.checked && selectAll) {
                selectAll.checked = false;
            }
            
            updateButtons();
        });
    });

    /**
     * Обработчик изменения статуса в select
     */
    if (statusSelect) {
        statusSelect.addEventListener('change', updateButtons);
    }

    // Инициализация при загрузке
    updateButtons();
});