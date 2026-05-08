// ============================================================================
// IMAGE DASHBOARD — чекбоксы, выделение, массовые действия
// Страница: /images/
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 image_dashboard.js инициализация...');

    const selectAll = document.getElementById('select-all');
    const checkboxes = document.querySelectorAll('.idea-checkbox');
    const rows = document.querySelectorAll('.idea-row');
    const countVal = document.getElementById('count-val');
    const selectionCount = document.getElementById('selection-count');
    const btnDelete = document.getElementById('btn-delete');
    const btnRegen = document.getElementById('btn-regen');

    function updateSelection() {
        const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
        
        if (countVal) countVal.innerText = checkedCount;
        if (selectionCount) selectionCount.style.display = checkedCount > 0 ? 'inline' : 'none';
        if (btnDelete) btnDelete.disabled = checkedCount === 0;
        if (btnRegen) btnRegen.disabled = checkedCount === 0;

        checkboxes.forEach((cb, index) => {
            if (rows[index]) {
                rows[index].classList.toggle('bg-selected', cb.checked);
            }
        });
    }

    if (selectAll) {
        selectAll.addEventListener('change', function() {
            checkboxes.forEach((cb, index) => {
                cb.checked = this.checked;
                if (rows[index]) rows[index].classList.toggle('bg-selected', this.checked);
            });
            updateSelection();
        });
    }

    checkboxes.forEach((cb, index) => {
        cb.addEventListener('change', function() {
            if (rows[index]) rows[index].classList.toggle('bg-selected', cb.checked);
            if (!cb.checked && selectAll) selectAll.checked = false;
            updateSelection();
        });
    });

    updateSelection();
    console.log('✅ image_dashboard.js готов');
});