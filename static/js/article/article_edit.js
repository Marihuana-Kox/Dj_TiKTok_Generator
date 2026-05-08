// ============================================================================
// ARTICLE EDIT — редактирование статьи
// Страница: /article/*/edit/
// ============================================================================

document.addEventListener('DOMContentLoaded', function() {
    console.log('🔍 article_edit.js инициализация...');

    // Авто-высота textarea
    document.querySelectorAll('textarea[name="content"]').forEach(tx => {
        // Устанавливаем минимальную высоту
        tx.style.minHeight = '250px';
        tx.style.height = 'auto';
        tx.style.height = tx.scrollHeight + 'px';
        
        tx.addEventListener('input', function() {
            this.style.height = 'auto';
            this.style.height = Math.max(this.scrollHeight, 250) + 'px';
        });
        
        // Trigger once on load
        tx.style.height = Math.max(tx.scrollHeight, 250) + 'px';
    });

    console.log('✅ article_edit.js готов');
});