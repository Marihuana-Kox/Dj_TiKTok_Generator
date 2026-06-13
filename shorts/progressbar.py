import json
import time
from django.core.cache import cache
from django.http import StreamingHttpResponse, JsonResponse

# Настройки по умолчанию
CACHE_TIMEOUT = 3600  # 1 час жизни записи в кэше
LOG_LIMIT = 15  # Сколько последних логов хранить в массиве


class ProgressManager:
    """
    Универсальный менеджер прогресса через Django Cache.
    Совместим с modal.js: отдаёт percent, message, status, logs, redirect_url.
    """

    def __init__(self, task_id: str, redirect_url: str = None, timeout: int = None):
        self.task_id = task_id
        self.redirect_url = redirect_url
        self.timeout = timeout or CACHE_TIMEOUT
        self.cache_key = f"progress_{task_id}"

    def _get_current(self) -> dict:
        return cache.get(self.cache_key, {})

    def update(
        self, percent: int, message: str, log_msg: str = None, status: str = "running", **extra
    ):
        """Обновляет состояние в кэше"""
        current = self._get_current()
        logs = current.get("logs", [])

        if log_msg and (not logs or logs[-1] != log_msg):
            logs.append(log_msg)

        data = {
            "percent": percent,
            "message": message,
            "status": status,
            "logs": logs[-LOG_LIMIT:],
            "task_id": self.task_id,
            **extra,
        }
        cache.set(self.cache_key, data, timeout=self.timeout)

    def init(self, message: str = " Запуск...", log_msg: str = None):
        """Инициализация задачи (5%)"""
        self.update(5, message, log_msg=log_msg or message)

    def done(self, percent: int = 100, message: str = "✅ Готово!", log_msg: str = None):
        """Финализация: статус done + редирект"""
        self.update(
            percent,
            message,
            log_msg=log_msg or message,
            status="done",
            redirect_url=self.redirect_url,
        )

    def fail(self, error_msg: str, percent: int = 0):
        """Обработка ошибки"""
        self.update(percent, f"❌ {error_msg}", log_msg=f"❌ {error_msg}", status="error")


def sse_progress_view(request, task_id: str, timeout: int = None):
    """
    Готовый SSE-эндпоинт. Стримит изменения из кэша на фронтенд.
    Используется в urls.py: path('stream/<str:task_id>/', ...)
    """
    if not task_id:
        return JsonResponse({"error": "No task_id"}, status=400)

    cache_key = f"progress_{task_id}"
    last_percent = -1
    checks_without_change = 0
    timeout_sec = timeout or CACHE_TIMEOUT

    def event_stream():
        nonlocal last_percent, checks_without_change
        while True:
            data = cache.get(cache_key)
            if not data:
                yield f"data: {json.dumps({'status': 'waiting', 'message': 'Подключение...'})}\n\n"
                time.sleep(1)
                continue

            current_status = data.get("status")
            current_percent = data.get("percent", 0)

            if current_percent != last_percent or current_status in ["done", "error"]:
                yield f"data: {json.dumps(data)}\n\n"
                last_percent = current_percent
                checks_without_change = 0
                if current_status in ["done", "error"]:
                    break
            else:
                checks_without_change += 1
                # Защита от "зависших" задач (>30 сек без изменений)
                if checks_without_change > 30:
                    yield f"data: {json.dumps({'status': 'error', 'message': 'Таймаут ожидания'})}\n\n"
                    break

            time.sleep(0.8)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
