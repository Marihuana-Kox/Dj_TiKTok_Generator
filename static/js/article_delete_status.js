document.addEventListener('DOMContentLoaded', function() {
        const selectAll = document.getElementById('select-all');
        // Ищем чекбоксы внутри формы (класс idea-checkbox или имя selected_ideas)
        const checkboxes = document.querySelectorAll('input[name="selected_articles"], input[name="selected_ideas"]'); // Обновлено для соответствия шаблону
        // const checkboxes = document.querySelectorAll('input[name="selected_ideas"]'); // Обновлено для соответствия шаблону
        console.log(`Найдено чекбоксов: ${checkboxes.length}`);
        
        const rows = document.querySelectorAll('.idea-row');
        
        const btnDelete = document.getElementById('btn-delete');
        const btnStatus = document.getElementById('btn-status');
        const statusSelect = document.getElementById('status-select');
        const countLabel = document.getElementById('selection-count');
        const countVal = document.getElementById('count-val');

        function updateControls() {
            let checkedCount = 0;
            checkboxes.forEach(cb => { if (cb.checked) checkedCount++; });
            
            const hasSelection = checkedCount > 0;

            if (btnDelete) btnDelete.disabled = !hasSelection;
            if (btnStatus) btnStatus.disabled = !hasSelection;
            if (statusSelect) statusSelect.disabled = !hasSelection;

            if (countLabel && countVal) {
                if (hasSelection) {
                    countLabel.style.display = 'inline';
                    countVal.textContent = checkedCount;
                } else {
                    countLabel.style.display = 'none';
                }
            }

            // Подсветка строк
            checkboxes.forEach((cb, index) => {
                if (rows[index]) {
                    rows[index].style.backgroundColor = cb.checked ? 'rgba(0, 123, 255, 0.05)' : '';
                }
            });
        }

        if (selectAll) {
            selectAll.addEventListener('change', function() {
                checkboxes.forEach(cb => { cb.checked = selectAll.checked; });
                updateControls();
            });
        }

        checkboxes.forEach(cb => {
            cb.addEventListener('change', function() {
                if (!cb.checked && selectAll) selectAll.checked = false;
                if (selectAll) {
                    selectAll.checked = Array.from(checkboxes).every(c => c.checked);
                }
                updateControls();
            });
        });
        
        updateControls();
    });
