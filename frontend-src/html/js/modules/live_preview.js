/**
 * 创建实时预览管理器
 * @param {Object} editors - 包含html, css, js编辑器实例的对象
 * @param {HTMLIFrameElement} iframe - 预览iframe元素
 * @returns {Object} 包含预览管理方法的对象
 */
export function createLivePreview(editors, iframe) {
    // 存储编辑器和iframe的引用
    const previewState = {
        editors: editors,
        iframe: iframe,
        isUpdating: false
    };

    /**
     * 更新预览
     */
    function updatePreview() {
        if (previewState.isUpdating) {
            return;
        }

        previewState.isUpdating = true;

        try {
            // 获取各编辑器的值
            const htmlCode = previewState.editors.html.getValue();
            const cssCode = previewState.editors.css.getValue();
            const jsCode = previewState.editors.js.getValue();

            // 创建预览内容
            const content = `
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>实时预览</title>
    <style>
        ${cssCode}
    </style>
</head>
<body>
    ${htmlCode}
    <script>
        // 错误处理
        window.onerror = function(message, source, lineno, colno, error) {
            console.error('JavaScript错误:', message, '行:', lineno, '列:', colno);
            return false;
        };
        
        try {
            ${jsCode}
        } catch (error) {
            console.error('执行JavaScript时出错:', error);
        }
    <\/script>
</body>
</html>
            `;

            // 更新iframe内容
            const iframeDoc = previewState.iframe.contentDocument || previewState.iframe.contentWindow.document;
            iframeDoc.open();
            iframeDoc.write(content);
            iframeDoc.close();
        } catch (error) {
            console.error('更新预览时出错:', error);
        } finally {
            previewState.isUpdating = false;
        }
    }

    /**
     * 触发更新
     */
    function triggerUpdate() {
        // 使用防抖机制，避免频繁更新
        clearTimeout(previewState.updateTimer);
        previewState.updateTimer = setTimeout(() => {
            updatePreview();
        }, 300);
    }

    /**
     * 销毁预览管理器
     */
    function destroy() {
        // 清除定时器
        if (previewState.updateTimer) {
            clearTimeout(previewState.updateTimer);
        }
    }

    // 返回公共方法
    return {
        updatePreview,
        triggerUpdate,
        destroy
    };
}