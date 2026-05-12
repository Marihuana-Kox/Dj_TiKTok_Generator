/**
 * ARTICLE EDIT — авто-высота полей
 */
document.addEventListener('DOMContentLoaded', function() {
    const textareas = document.querySelectorAll('textarea[name="content"]');
    
    textareas.forEach(tx => {
        const adjustHeight = () => {
            tx.style.height = 'auto';
            tx.style.height = Math.max(tx.scrollHeight, 250) + 'px';
        };

        tx.style.minHeight = '250px';
        tx.addEventListener('input', adjustHeight);
        adjustHeight(); // Вызов при загрузке
    });
});