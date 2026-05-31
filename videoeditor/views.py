import json
import os
import threading
import time
import uuid
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, render

from audio.models import AudioProject, AudioTrack
from image.models import ImageProject, ImagePrompt

# ИМПОРТИРУЕМ КЛИПЫ И КЛАСС ЭФФЕКТОВ ИЗ MOVIEPY V2
from moviepy import AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips, vfx
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip

# Импортируем твой класс эффектов
from .video_effects import VideoEffects
from videoeditor.services import sanitize_media_path
from proglog import ProgressBarLogger


def make_video_processing(
    t_id, timeline_list, p_id, s_file_path, out_dir, out_path, v_url, project_media_dir=None
):
    """
    Профессиональная параллельная сборка таймлайна (архитектура MoviePy v2.x).
    Видео и аудио — два абсолютно независимых клипа. Сборка видеоряда строго через CompositeVideoClip.
    """
    os.environ["MOVIEPY_SUPPRESS_WARNINGS"] = "1"

    class DjangoProgressLogger(ProgressBarLogger):
        def __init__(self):
            super().__init__()
            self.last_update_time = 0

        def callback(self, **kwargs):
            bars = self.state.get("bars")
            if "frame_index" in bars:
                bar = bars["frame_index"]
                if bar["total"] > 0:
                    current_frame = bar["index"]
                    total_frames = bar["total"]
                    render_percent = int((current_frame / total_frames) * 36) + 48
                    now = time.time()
                    if now - self.last_update_time > 0.4 or render_percent == 99:
                        self.last_update_time = now
                        p_data = {
                            "percent": render_percent,
                            "message": f"🚀 Кодирование кадров: {current_frame} из {total_frames}...",
                            "status": "running",
                            "task_id": t_id,
                        }
                        cache.set(f"progress_{t_id}", p_data, timeout=3600)
                        try:
                            with open(s_file_path, "w", encoding="utf-8") as f:
                                json.dump(p_data, f, ensure_ascii=False)
                        except:
                            pass

    video_clips = []
    audio_clips = []
    final_audio_track = None
    final_video_track = None
    final_clip = None

    try:
        total_scenes = len(timeline_list)
        print(f"🎰 [ПОТОК РЕНДЕРА] Получено сценариев для сборки: {total_scenes}")
        if total_scenes == 0:
            raise ValueError("Список сцен пуст.")

        # ==========================================
        # ЭТАП 1: АВТОНОМНАЯ СБОРКА АУДИОТРЕКА
        # ==========================================
        for item in timeline_list:
            track = item.get("track")
            if track and hasattr(track, "audio_file") and track.audio_file:
                audio_path = sanitize_media_path(track.audio_file.path)
                if os.path.exists(audio_path):
                    a_clip = AudioFileClip(audio_path)
                    meta_settings = item.get("meta_settings", {})
                    audio_fx = meta_settings.get(
                        "audio_effects", {"volume": 100, "fade_in": 0, "fade_out": 0}
                    )
                    a_clip = VideoEffects.apply_audio_effects(a_clip, audio_fx)
                    audio_clips.append(a_clip)

        if audio_clips:
            final_audio_track = concatenate_audioclips(audio_clips)
            total_audio_duration = final_audio_track.duration
            print(f"🎵 АУДИОДОРОЖКА СОБРАНА. Длина звука: {total_audio_duration} сек.")
        else:
            total_audio_duration = 0.0
            print("🎵 АУДИОДОРОЖКА ПУСТАЯ (Видео будет без звука).")

        total_video_duration = 0.0

        # ==========================================
        # 🎯 ДИНАМИЧЕСКИЙ РАСЧЕТ ДЛЯ АВТОПОДГОНА
        # ==========================================
        if total_audio_duration > 0 and total_scenes > 0:
            ideal_scene_duration = total_audio_duration / total_scenes
            print(
                f"🎯 АВТОПОДГОН ВКЛЮЧЕН: Реальный звук {total_audio_duration}с делим на {total_scenes} scenes. Каждая сцена = {ideal_scene_duration:.4f} сек."
            )
        else:
            ideal_scene_duration = None
            print("🎯 АВТОПОДГОН ВЫКЛЮЧЕН: Видео будет собираться по таймингам фронтенда.")

        # ==========================================
        # ЭТАП 2: АВТОНОМНАЯ СБОРКА ВИДЕОТРЕКА
        # ==========================================
        for i, item in enumerate(timeline_list):
            current_num = i + 1

            percent = int((i / total_scenes) * 32) + 5
            p_data = {
                "percent": percent,
                "message": f"📹 Подготовка сцены {current_num} из {total_scenes}...",
                "status": "running",
                "task_id": t_id,
            }
            cache.set(f"progress_{t_id}", p_data, timeout=3600)
            try:
                with open(s_file_path, "w", encoding="utf-8") as f:
                    json.dump(p_data, f, ensure_ascii=False)
            except:
                pass

            meta_settings = item.get("meta_settings", {})

            # Если работает автоподгон — берем идеальную длину, иначе — из фронтенда
            if ideal_scene_duration:
                scene_duration = ideal_scene_duration
            else:
                scene_duration = float(meta_settings.get("duration", 5.0))

            video_fx = meta_settings.get("video_effects", "none")
            color_filter = meta_settings.get("filter", "none")
            text_fx = meta_settings.get("text_overlay", {})
            transition_type = meta_settings.get("transition", "none")
            mirror_x = meta_settings.get("mirror_x", False)
            mirror_y = meta_settings.get("mirror_y", False)

            image_name = meta_settings.get("image_name")
            image_path = None

            # ПРЯМОЙ ПОИСК ФАЙЛА НА ДИСКЕ ПО ИМЕНИ В ВЕРИФИЦИРОВАННОЙ ПАПКЕ ПРОЕКТА
            if project_media_dir and image_name:
                potential_path = os.path.join(project_media_dir, image_name)
                if os.path.exists(potential_path):
                    image_path = potential_path

            # Резервный поиск в глобальных медиа, если папка проекта не помогла
            if not image_path and image_name:
                for folder in ["uploaded_images", "", "image"]:
                    test_path = os.path.join(settings.MEDIA_ROOT, folder, image_name)
                    if os.path.exists(test_path):
                        image_path = sanitize_media_path(test_path)
                        break

            # Окончательная проверка существования файла
            if not image_path or not os.path.exists(image_path):
                raise FileNotFoundError(
                    f"Критическая ошибка: Кадр №{current_num} требует файл '{image_name}', но он не найден на сервере."
                )

            total_video_duration += scene_duration

            # Создаем клип с динамически вычисленной точной длительностью
            base_image_clip = ImageClip(image_path).with_duration(scene_duration)
            resized_base_clip = base_image_clip.resized((1080, 1920))

            animated_clip = VideoEffects.apply_visual_effect(resized_base_clip, video_fx)
            final_video_clip = VideoEffects.apply_color_filter(animated_clip, color_filter)

            if text_fx and text_fx.get("text"):
                final_video_clip = VideoEffects.attach_text_overlay(final_video_clip, text_fx)

            effects_stack = []
            if mirror_x:
                effects_stack.append(vfx.MirrorX())
            if mirror_y:
                effects_stack.append(vfx.MirrorY())
            if transition_type == "fade_black":
                effects_stack.append(vfx.FadeIn(1.0))

            if effects_stack:
                final_video_clip = final_video_clip.with_effects(effects_stack)

            video_clips.append(final_video_clip)

        if not video_clips:
            raise ValueError("Массив видеоклипов пуст.")

        # ========================================================
        # 🔥 СОВРЕМЕННАЯ СБОРКА ЧЕРЕЗ COMPOSITEVIDEOCLIP (СТЫК-В-СТЫК)
        # ========================================================
        positioned_clips = []
        current_time = 0.0

        for idx, clip in enumerate(video_clips):
            # Ставим клип строго на текущую временную отметку таймлайна
            clip = clip.with_start(current_time)
            positioned_clips.append(clip)

            # Перемещаем указатель времени строго на длину этого клипа
            current_time += clip.duration

        # Собираем финальный трек исключительно через CompositeVideoClip
        final_video_track = CompositeVideoClip(positioned_clips, size=(1080, 1920))
        final_video_track = final_video_track.with_duration(current_time)

        actual_video_duration = final_video_track.duration
        print(f"📹 ВИДЕОРЯД СОБРАН. Честная длина видео: {actual_video_duration} сек.")

        # ==========================================
        # TIMELINE LOG CHECK
        # ==========================================
        for i, clip in enumerate(positioned_clips):
            print(
                f"\n========== TIMELINE CHECK ==========\n"
                f"CLIP {i + 1}: start={clip.start:.2f} end={clip.end:.2f} duration={clip.duration:.2f}"
            )

        print(
            f"\nFINAL TIMELINE LENGTH = {current_time:.2f}\n====================================\n"
        )

        # ==========================================
        # ЭТАП 3: СОЕДИНЕНИЕ ПОТОКОВ
        # ==========================================
        if final_audio_track:
            print(
                f"📊 СРАВНЕНИЕ ДЛИНЫ: Видео = {actual_video_duration:.2f}с, Аудио = {total_audio_duration:.2f}с."
            )

            # Накладываем аудиопоток на видеоряд
            final_clip = final_video_track.with_audio(final_audio_track)

            # Видео и аудио теперь гарантированно равны до миллисекунды
            final_clip = final_clip.with_duration(actual_video_duration)
        else:
            final_clip = final_video_track

        # ==========================================
        # ЗАПУСК РЕНДЕРИНГА ФАЙЛА
        # ==========================================
        os.makedirs(out_dir, exist_ok=True)
        final_clip.write_videofile(
            out_path,
            fps=30,  # Стандарт для TikTok, убирает баг округления кадров
            codec="libx264",
            audio_codec="aac",
            ffmpeg_params=[
                "-pix_fmt",
                "yuv420p",
                "-shortest" if not final_audio_track else "-fflags",
                "+shortest",
            ],
            threads=4,
            logger=DjangoProgressLogger(),
        )

        final_data = {
            "percent": 100,
            "message": "✅ Видеоролик успешно собран!",
            "status": "done",
            "task_id": t_id,
            "completed": True,
            "video_url": v_url,
        }
        cache.set(f"progress_{t_id}", final_data, timeout=3600)
        try:
            with open(s_file_path, "w", encoding="utf-8") as f:
                json.dump(final_data, f, ensure_ascii=False)
        except:
            pass

    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА В ПОТОКЕ РЕНДЕРА: {str(e)}")
        err_data = {"status": "error", "message": f"Ошибка таймлайна: {str(e)}", "percent": 0}
        cache.set(f"progress_{t_id}", err_data, timeout=3600)
        try:
            with open(s_file_path, "w", encoding="utf-8") as f:
                json.dump(err_data, f, ensure_ascii=False)
        except:
            pass
    finally:
        for clip in video_clips:
            try:
                clip.close()
            except:
                pass
        for a_clip in audio_clips:
            try:
                a_clip.close()
            except:
                pass
        if final_audio_track:
            try:
                final_audio_track.close()
            except:
                pass
        if final_video_track:
            try:
                final_video_track.close()
            except:
                pass
        if final_clip:
            try:
                final_clip.close()
            except:
                pass
        connection.close()


@login_required
def video_editor_view(request, project_id):
    output_dir = os.path.join(settings.MEDIA_ROOT, "rendered_videos")
    filename = f"project_{project_id}.mp4"
    expected_mp4 = os.path.join(output_dir, filename)
    video_url = f"/media/rendered_videos/{filename}"

    is_ajax = (
        request.headers.get("X-Requested-With") == "XMLHttpRequest"
        or request.content_type == "application/json"
    )

    if is_ajax:
        if request.method == "GET":
            task_id = request.GET.get("task_id")
            status_file = os.path.join(settings.MEDIA_ROOT, f"status_{task_id}.json")

            if os.path.exists(status_file):
                try:
                    with open(status_file, "r", encoding="utf-8") as f:
                        status_data = json.load(f)
                        return JsonResponse(status_data)
                except:
                    pass
            return JsonResponse(
                {"completed": False, "percent": 5, "message": "🎬 Ожидание потока..."}
            )

        if request.method == "POST":
            try:
                req_data = json.loads(request.body.decode("utf-8"))
            except Exception:
                req_data = {}

            audio_project = get_object_or_404(AudioProject, id=project_id, user=request.user)
            clean_title = audio_project.title.strip()
            image_project = ImageProject.objects.filter(title__icontains=clean_title).first()
            if not image_project and audio_project.article:
                image_project = ImageProject.objects.filter(
                    article_id=audio_project.article_id
                ).first()

            tracks_list = list(AudioTrack.objects.filter(project=audio_project).order_by("order"))
            prompts_list = (
                list(ImagePrompt.objects.filter(project=image_project).order_by("order"))
                if image_project
                else []
            )

            # 🛠 ОПРЕДЕЛЯЕМ ПАПКУ ПРОЕКТА НА ДИСКЕ ОДИН РАЗ ДО ЦИКЛА
            project_media_dir = None
            if prompts_list:
                # Берем любой промпт, у которого заполнена картинка
                sample_prompt = next((p for p in prompts_list if p.image), None)
                if sample_prompt:
                    sanitized_db_path = sanitize_media_path(sample_prompt.image.path)
                    project_media_dir = os.path.dirname(sanitized_db_path)

            frontend_timeline = req_data.get("timeline", [])
            print("!!! СЫРЫЕ ДАННЫЕ С ФРОНТЕНДА !!!")
            print(frontend_timeline)
            print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")

            render_timeline = []

            # ИДЕМ СТРОГО ПО МАССИВУ ФРОНТЕНДА (ПОЛНАЯ АВТОНОМНОСТЬ)
            for item in frontend_timeline:
                meta_settings = item.get("meta_settings", {})

                try:
                    order_from_frontend = int(item.get("order", 1))
                except (ValueError, TypeError):
                    order_from_frontend = 1

                # Нам больше не нужно искать объект prompt в БД по имени файла ради пути!
                # Мы просто привяжем аудиодорожку по номеру очереди шага.
                track = next((t for t in tracks_list if t.order == order_from_frontend), None)

                if not meta_settings:
                    meta_settings = {
                        "duration": 5.0,
                        "video_effects": "none",
                        "filter": "none",
                        "transition": "none",
                        "text_overlay": {
                            "text": "",
                            "font": "Arial",
                            "font_size": 30,
                            "font_color": "#FFFFFF",
                            "position": "bottom",
                        },
                        "audio_effects": {"volume": 100, "fade_in": 0, "fade_out": 0},
                    }

                render_timeline.append(
                    {
                        "track": track,
                        "meta_settings": meta_settings,
                        "order": order_from_frontend,
                    }
                )

            print(f"🔍 DEBUG OPTIMIZED: Фронтенд передал {len(frontend_timeline)} сцен.")
            print(
                f"🔍 DEBUG OPTIMIZED: Верифицированная папка проекта на сервере: {project_media_dir}"
            )

            if not render_timeline:
                return JsonResponse(
                    {"success": False, "error": "Нет готовых данных для сборки"}, status=400
                )

            if os.path.exists(expected_mp4):
                try:
                    os.remove(expected_mp4)
                except:
                    pass

            task_id = str(uuid.uuid4())
            init_data = {
                "percent": 5,
                "message": "🎬 Подготовка таймлайна...",
                "status": "running",
                "task_id": task_id,
            }

            os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
            status_file_path = os.path.join(settings.MEDIA_ROOT, f"status_{task_id}.json")
            with open(status_file_path, "w", encoding="utf-8") as f:
                json.dump(init_data, f, ensure_ascii=False)

            threading.Thread(
                target=make_video_processing,
                args=(
                    task_id,
                    render_timeline,
                    project_id,
                    status_file_path,
                    output_dir,
                    expected_mp4,
                    video_url,
                    project_media_dir,  # Пробрасываем чистую папку проекта прямо в рендерер
                ),
                daemon=True,
            ).start()

            return JsonResponse({"success": True, "task_id": task_id})

    # ОБЫЧНЫЙ СИНХРОННЫЙ GET-ЗАПРОС СТРАНИЦЫ
    audio_project = get_object_or_404(AudioProject, id=project_id, user=request.user)
    clean_title = audio_project.title.strip()
    image_project = (
        ImageProject.objects.filter(title__icontains=clean_title).first()
        or ImageProject.objects.filter(article_id=audio_project.article_id).first()
    )

    tracks = AudioTrack.objects.filter(project=audio_project).order_by("order")
    prompts = (
        ImagePrompt.objects.filter(project=image_project).order_by("order") if image_project else []
    )

    timeline_data = []
    all_orders = set()
    for t in tracks:
        all_orders.add(t.order)
    for p in prompts:
        if p.image:
            all_orders.add(p.order)

    max_elements = max(all_orders) if all_orders else 0

    for idx in range(max_elements):
        current_order = idx + 1
        track = next((t for t in tracks if t.order == current_order), None)
        prompt = next((p for p in prompts if p.order == current_order), None)

        if track or (prompt and prompt.image):
            track_duration = 5.0
            if track and track.audio_file:
                try:
                    audio_path = sanitize_media_path(track.audio_file.path)
                    if os.path.exists(audio_path):
                        with AudioFileClip(audio_path) as audio_meta:
                            track_duration = round(audio_meta.duration, 2)
                except Exception:
                    track_duration = 3.5

            timeline_data.append(
                {
                    "order": current_order,
                    "track": track,
                    "prompt": prompt,
                    "audio_duration": track_duration,
                }
            )

    video_render = None
    if os.path.exists(expected_mp4):
        video_render = {"status": "success", "video_file": {"url": video_url}}

    return render(
        request,
        "videoeditor/video_editor.html",
        {"project": audio_project, "timeline_data": timeline_data, "video_render": video_render},
    )


@login_required
def download_video_file(request, project_id):
    file_path = os.path.join(settings.MEDIA_ROOT, "rendered_videos", f"project_{project_id}.mp4")
    if os.path.exists(file_path):
        return FileResponse(
            open(file_path, "rb"),
            content_type="video/mp4",
            as_attachment=True,
            filename=f"project_{project_id}.mp4",
        )
    raise Http404()
