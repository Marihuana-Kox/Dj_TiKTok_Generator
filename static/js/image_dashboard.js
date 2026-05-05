    document.addEventListener('DOMContentLoaded', function() {
        // Логика выделения строк (как в статьях)
        const selectAll = document.getElementById('select-all');
        const checkboxes = document.querySelectorAll('.idea-checkbox');
        const rows = document.querySelectorAll('.idea-row');
        const countVal = document.getElementById('count-val');
        const selectionCount = document.getElementById('selection-count');
        const btnDelete = document.getElementById('btn-delete');
        const btnRegen = document.getElementById('btn-regen');

        function updateSelection() {
            const checkedCount = Array.from(checkboxes).filter(cb => cb.checked).length;
            countVal.innerText = checkedCount;
            selectionCount.style.display = checkedCount > 0 ? 'inline' : 'none';
            
            // Активация кнопок
            if (btnDelete) btnDelete.disabled = checkedCount === 0;
            if (btnRegen) btnRegen.disabled = checkedCount === 0;
        }

        if (selectAll) {
            selectAll.addEventListener('change', function() {
                checkboxes.forEach((cb, index) => {
                    cb.checked = selectAll.checked;
                    if(rows[index]) rows[index].classList.toggle('bg-selected', selectAll.checked);
                });
                updateSelection();
            });
        }

        checkboxes.forEach((cb, index) => {
            cb.addEventListener('change', function() {
                if(rows[index]) rows[index].classList.toggle('bg-selected', cb.checked);
                if (!cb.checked && selectAll) selectAll.checked = false;
                updateSelection();
            });
        });

        // Логика модального окна (если нужно открывать через JS)
        const modal = document.getElementById('create-modal');
        const closeBtn = document.getElementById('close-create-modal');
        // Здесь можно добавить обработчик клика на кнопку "Новый проект", если она открывает модалку
        // document.querySelector('.btn-primary').addEventListener('click', (e) => {
        //     e.preventDefault();
        //     modal.classList.add('active');
        // });
        
        if(closeBtn) {
            closeBtn.addEventListener('click', () => {
                modal.classList.remove('active');
            });
        }
    });