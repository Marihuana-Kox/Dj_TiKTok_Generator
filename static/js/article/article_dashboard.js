/**
 * ARTICLE DASHBOARD — управление списком статей
 */
document.addEventListener('DOMContentLoaded', function() {
    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('input[name="selected_articles"]');
    const countVal = document.getElementById('count-val');
    const selectionCount = document.getElementById('selection-count');
    
    const actionButtons = [
        document.getElementById('btn-delete'),
        document.getElementById('btn-status'),
        document.getElementById('status-select')
    ];

    function updateSelection() {
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        const hasSelection = checkedCount > 0;
        
        if (countVal) countVal.textContent = checkedCount;
        if (selectionCount) selectionCount.style.display = hasSelection ? 'inline' : 'none';
        
        actionButtons.forEach(btn => {
            if (btn) btn.disabled = !hasSelection;
        });

        // Подсветка выбранных строк
        checkboxes.forEach(cb => {
            const row = cb.closest('.idea-row');
            if (row) row.classList.toggle('bg-selected', cb.checked);
        });
    }

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach(cb => {
                cb.checked = this.checked;
            });
            updateSelection();
        });
    }

    checkboxes.forEach(cb => {
        cb.addEventListener('change', updateSelection);
    });

    updateSelection(); // Начальное состояние
});