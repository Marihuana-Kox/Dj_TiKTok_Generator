import io
import json
import os
import time
import uuid
import urllib.parse
import threading
import zipfile
from django.conf import settings
from django.core.cache import cache
from django.contrib.auth.decorators import login_required
from django.db import connection
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponse, JsonResponse, FileResponse, Http404
from django.shortcuts import get_object_or_404, render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.contrib import messages
import mutagen

from .models import ProjectVideoRelease
from audio.models import AudioProject, AudioTrack
from image.models import ImageProject, ImagePrompt

# ИМПОРТИРУЕМ КЛИПЫ И КЛАСС ЭФФЕКТОВ ИЗ MOVIEPY V2
from moviepy import AudioFileClip, ImageClip, concatenate_audioclips, concatenate_videoclips, vfx
from moviepy.video.compositing.CompositeVideoClip import CompositeAudioClip, CompositeVideoClip
from moviepy.video.VideoClip import ColorClip

# Импортируем твои утилиты
from .video_effects import VideoEffects
from .services import sanitize_media_path
from proglog import ProgressBarLogger


@login_required
def projects_list(request):
    user_audio_ids = AudioProject.objects.filter(user=request.user).values_list("id", flat=True)
    ready_releases_list = ProjectVideoRelease.objects.filter(
        project_id__in=user_audio_ids
    ).order_by("-video_created_at")

    paginator = Paginator(ready_releases_list, 6)
    page = request.GET.get("page")

    try:
        ready_releases = paginator.page(page)
    except PageNotAnInteger:
        ready_releases = paginator.page(1)
    except EmptyPage:
        ready_releases = paginator.page(paginator.num_pages)

    projects_extended_list = []

    for release in ready_releases:
        p = AudioProject.objects.filter(id=release.project_id).first()
        if not p:
            continue

        art_id = p.article_id
        image_project = None
        if art_id:
            image_project = ImageProject.objects.filter(article_id=art_id).first()

        redirect_url = f"/video/project/{p.id}/"
        button_text = "🛠️ Открыть видеоредактор"
        status_type = "all_ready"

        first_frame_url = None
        if image_project:
            first_prompt = (
                ImagePrompt.objects.filter(project=image_project)
                .exclude(image="")
                .order_by("order")
                .first()
            )
            if first_prompt and first_prompt.image:
                first_url = first_prompt.image.url
                path_str = urllib.parse.unquote(str(first_url))
                first_frame_url = sanitize_media_path(path_str)

        projects_extended_list.append(
            {
                "audio_project": p,
                "release": release,
                "action_url": redirect_url,
                "action_text": button_text,
                "status_type": status_type,
                "first_frame_url": first_frame_url,
                "download_url": f"/video/project/{p.id}/download/",
            }
        )

    return render(
        request,
        "videoeditor/projects_list.html",
        {"projects": projects_extended_list, "page_obj": ready_releases},
    )


def make_video_processing_task(
    timeline_list,
    project_id,
    s_file_path,
    out_dir,
    out_path,
    v_url,
    project_media_dir=None,
):
    # Извлекаем task_id прямо из имени файла статуса, чтобы связать его с фронтендом
    try:
        t_id = os.path.basename(s_file_path).replace("status_", "").replace(".json", "")
    except Exception:
        t_id = str(uuid.uuid4())

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
                    # Масштабируем оставшиеся проценты (от 48% до 99%)
                    render_percent = int((current_frame / total_frames) * 51) + 48
                    now = time.time()
                    if now - self.last_update_time > 0.4 or render_percent >= 99:
                        self.last_update_time = now
                        p_data = {
                            "percent": render_percent,
                            "progress": render_percent,
                            "message": f"🚀 Кодирование кадров: {current_frame} из {total_frames}...",
                            "status": "running",
                            "task_id": t_id,
                        }
                        cache.set(f"progress_{t_id}", p_data, timeout=3600)
                        try:
                            with open(s_file_path, "w", encoding="utf-8") as f:
                                json.dump(p_data, f, ensure_ascii=False)
                        except:  # noqa: E722
                            pass

    video_clips = []
    audio_clips = []
    final_audio_track = None
    final_video_track = None
    final_clip = None

    try:
        total_scenes = len(timeline_list)
        print(f"🎰 [ПОТОК РЕНДЕРА] Получено сцен для сборки: {total_scenes} (ID задачи: {t_id})")
        if total_scenes == 0:
            raise ValueError("Список сцен пуст.")

        # =========================================================================
        # ЭТАП 1: АВТОНОМНАЯ СБОРКА АУДИОТРЕКА (ВСЕЯДНЫЙ СКАНИРУЮЩИЙ КАТЧЕР) V2
        # =========================================================================
        current_audio_time = 0.0
        transition_overlap = 0.6  # Нахлёст переходов (должен совпадать с ЭТАПОМ 2)
        positioned_audio_clips = []

        print("🔍 [АУДИО] Начинаем сканирование JSON на наличие аудиодорожек...")

        db_tracks = list(AudioTrack.objects.filter(project_id=project_id).order_by("order"))

        for idx, track in enumerate(db_tracks, start=1):
            if track.audio_file and track.audio_file.path:
                absolute_audio_path = sanitize_media_path(track.audio_file.path)

                try:
                    a_clip = AudioFileClip(absolute_audio_path)

                    audio_fx = {"volume": 100, "fade_in": 0, "fade_out": 0}
                    if idx <= len(timeline_list):
                        meta_settings = timeline_list[idx - 1].get("meta_settings", {})
                        audio_fx = meta_settings.get("audio_effects", audio_fx)

                    a_clip = VideoEffects.apply_audio_effects(a_clip, audio_fx)

                    a_clip = a_clip.with_start(current_audio_time)
                    current_audio_time += a_clip.duration

                    positioned_audio_clips.append(a_clip)
                    audio_clips.append(a_clip)
                    print(
                        f"✅ [АУДИО] Добавлен трек из БД №{idx}: {track.audio_file.name} ({a_clip.duration:.2f} сек.)"
                    )
                except Exception as aud_err:
                    print(
                        f"❌ [АУДИО] Ошибка чтения файла из БД {absolute_audio_path}: {str(aud_err)}"
                    )
            else:
                print(f"⚠️ [АУДИО] У трека №{idx} в базе данных отсутствует физический файл.")

        if positioned_audio_clips:
            final_audio_track = CompositeAudioClip(positioned_audio_clips)
            total_audio_duration = final_audio_track.duration
            print(
                f"🎉 [УСПЕХ] Аудиодорожка успешно восстановлена из БД! Общая длина: {total_audio_duration:.2f} sec."
            )
        else:
            total_audio_duration = 0.0
            final_audio_track = None
            print("🚨 [КРИТИЧЕСКИ] База данных вернула 0 аудиофайлов для этого проекта!")

        if total_audio_duration > 0 and total_scenes > 0:
            if total_scenes > 1:
                total_transitions_time = (total_scenes - 1) * transition_overlap
                ideal_scene_duration = (
                    total_audio_duration + total_transitions_time
                ) / total_scenes
            else:
                ideal_scene_duration = total_audio_duration
            print(
                f"📏 Расчетная базовая длина одной сцены (с учетом нахлёста): {ideal_scene_duration:.2f} сек."
            )
        else:
            ideal_scene_duration = None

        # =========================================================================
        # ЭТАП 2: СБОРКА ВИДЕОКЛИПОВ С ПОЗИЦИОНИРОВАНИЕМ ДРУГ ЗА ДРУГОМ (С НАХЛЁСТОМ)
        # =========================================================================
        current_video_time = 0.0

        for i, item in enumerate(timeline_list):
            current_num = i + 1
            percent = int((i / total_scenes) * 40) + 5
            p_data = {
                "percent": percent,
                "progress": percent,
                "message": f"📹 Подготовка сцены {current_num} из {total_scenes}...",
                "status": "running",
                "task_id": t_id,
            }
            cache.set(f"progress_{t_id}", p_data, timeout=3600)
            try:
                with open(s_file_path, "w", encoding="utf-8") as f:
                    json.dump(p_data, f, ensure_ascii=False)
            except Exception as e:
                print(f"Ошибка при записи прогресса: {e}")

            meta_settings = item.get("meta_settings", {})
            scene_duration = (
                ideal_scene_duration
                if ideal_scene_duration
                else float(meta_settings.get("duration", 5.0))
            )

            video_fx = meta_settings.get("video_effects", "none")
            color_filter = meta_settings.get("filter", "none")
            text_fx = meta_settings.get("text_overlay", {})
            transition_type = meta_settings.get("transition", "none")
            mirror_x = meta_settings.get("mirror_x", False)
            mirror_y = meta_settings.get("mirror_y", False)

            image_name = meta_settings.get("image_name")
            image_path = None
            test_absolute_path = "Путь не формировался"

            if image_name:
                clean_path = urllib.parse.unquote(str(image_name)).strip("/")
                path_segments = clean_path.split("/")
                pure_filename = path_segments[-1]

                if len(path_segments) >= 2:
                    detected_slug = path_segments[-2]
                    test_absolute_path = os.path.join(
                        settings.MEDIA_ROOT, "projects", detected_slug, pure_filename
                    )
                    if os.path.exists(test_absolute_path):
                        image_path = sanitize_media_path(test_absolute_path)
                    else:
                        test_absolute_path = (
                            f"{test_absolute_path} (Файл не найден в папке '{detected_slug}')"
                        )
                else:
                    test_absolute_path = f"Не удалось разобрать путь {clean_path} по слэшам."

            if not image_path or not os.path.exists(image_path):
                raise FileNotFoundError(
                    f"Кадр №{current_num} упал. Проверенный путь: {test_absolute_path}"
                )

            # Инициализация ImageClip и принудительное включение маски для прозрачности переходов
            # СТАЛО:
            base_image_clip = ImageClip(image_path, is_mask=False).with_duration(scene_duration)
            # base_image_clip = ImageClip(image_path).with_duration(scene_duration).with_mask(True)
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

            if effects_stack:
                final_video_clip = final_video_clip.with_effects(effects_stack)

            # Передаем клип в метод переходов, где применятся FadeIn/FadeOut под маску
            final_video_clip = VideoEffects.apply_transition(
                final_video_clip, transition_type, duration=transition_overlap
            )

            # ХИТРОЕ ПОЗИЦИОНИРОВАНИЕ НА ОБЩЕМ ТАЙМЛАЙНЕ СДВИГОМ НАХЛЁСТА НАЗАД
            if i > 0:
                start_at = current_video_time - transition_overlap
                final_video_clip = final_video_clip.with_start(max(0.0, start_at))
                current_video_time += scene_duration - transition_overlap
            else:
                final_video_clip = final_video_clip.with_start(0.0)
                current_video_time += scene_duration

            video_clips.append(final_video_clip)

        # =========================================================================
        # ЭТАП 3: СБОРКА КОМПОЗИТНОГО ХОЛСТА И ФИНАЛЬНЫЙ РЕНДЕР
        # =========================================================================
        if video_clips:
            print(f"🎬 Собираем многослойный холст через CompositeVideoClip...")

            if final_audio_track and total_audio_duration > 0:
                final_duration = total_audio_duration
            else:
                final_duration = current_video_time

            # Создаем черную фоновую подложку. На нее будут накладываться клипы с прозрачностью переходов
            from moviepy.video.VideoClip import ColorClip

            bg_clip = ColorClip(size=(1080, 1920), color=(0, 0, 0)).with_duration(final_duration)

            # Собираем холст: подложка идет первой, поверх накладываются сдвинутые друг на друга клипы
            final_clip = CompositeVideoClip([bg_clip] + video_clips, size=(1080, 1920))
            final_clip = final_clip.with_duration(final_duration)

            if final_audio_track and total_audio_duration > 0:
                print("🔊 Накладываем аудиопоток на композитный холст...")
                final_clip.audio = final_audio_track

            os.makedirs(out_dir, exist_ok=True)
            print(f"🚀 Запускаем FFmpeg. Выходной файл: {out_path}")

            final_clip.write_videofile(
                out_path,
                fps=30,
                codec="libx264",
                audio_codec="aac",
                audio_bitrate="192k",
                audio_fps=44100,
                temp_audiofile=os.path.join(out_dir, f"temp_render_{project_id}.m4a"),
                remove_temp=True,
                threads=4,
                logger=DjangoProgressLogger(),
            )

            print("Video duration:", final_clip.duration)
            print("Audio duration:", final_clip.audio.duration if final_clip.audio else None)

            try:
                relative_mp4_path = os.path.relpath(out_path, settings.MEDIA_ROOT)
                ProjectVideoRelease.objects.filter(project_id=project_id).update(
                    pj_status="ready", pj_link=relative_mp4_path
                )
            except Exception as db_err:
                print(f"⚠️ Ошибка БД: {str(db_err)}")

            final_data = {
                "percent": 100,
                "progress": 100,
                "message": "✅ Успешно собрано!",
                "status": "success",
                "task_id": t_id,
                "completed": True,
                "video_url": v_url,
            }
            cache.set(f"progress_{t_id}", final_data, timeout=3600)
            try:
                with open(s_file_path, "w", encoding="utf-8") as f:
                    json.dump(final_data, f, ensure_ascii=False)
            except Exception as e:
                print(f"❌ ОШИБКА ПРИ СОХРАНЕНИИ ДАННЫХ: {str(e)}")

    except Exception as e:
        import traceback

        print(f"❌ ОШИБКА В СБОРКЕ ВИДЕО:\n{traceback.format_exc()}")
        try:
            ProjectVideoRelease.objects.filter(project_id=project_id).update(pj_status="failed")
        except Exception as db_ex:
            print(f"❌ ОШИБКА ПРИ ОБНОВЛЕНИИ СТАТУСА В БД: {str(db_ex)}")

        err_data = {
            "status": "error",
            "message": f"Ошибка таймлайна: {str(e)}",
            "percent": 0,
            "progress": 0,
        }
        cache.set(f"progress_{t_id}", err_data, timeout=3600)
        try:
            with open(s_file_path, "w", encoding="utf-8") as f:
                json.dump(err_data, f, ensure_ascii=False)
        except Exception as write_ex:
            print(f"❌ ОШИБКА ПРИ СОХРАНЕНИИ ДАННЫХ ОБ ОШИБКЕ: {str(write_ex)}")
    finally:
        for c in video_clips:
            try:
                c.close()
            except Exception as e:
                print(f"❌ ОШИБКА ПРИ ЗАКРЫТИИ ВИДЕОКЛИПА: {str(e)}")
        for ac in audio_clips:
            try:
                ac.close()
            except Exception as e:
                print(f"❌ ОШИБКА ПРИ ЗАКРЫТИИ АУДИОКЛИПА: {str(e)}")
        if final_audio_track:
            try:
                final_audio_track.close()
            except Exception as e:
                print(f"❌ ОШИБКА ПРИ ЗАКРЫТИИ АУДИОTРЕКА: {str(e)}")
        if final_video_track:
            try:
                final_video_track.close()
            except Exception as e:
                print(f"❌ ОШИБКА ПРИ ЗАКРЫТИИ ВИДЕОTРЕКА: {str(e)}")
        if final_clip:
            try:
                final_clip.close()
            except Exception as e:
                print(f"❌ ОШИБКА ПРИ ЗАКРЫТИИ ФИНАЛЬНОГО КЛИПА: {str(e)}")
        connection.close()


# 🔥 ЖЕЛЕЗНО ВЫДЕЛЕННЫЙ ЭНДПОИНТ ДЛЯ ЖИВОГО АВТОСОХРАНЕНИЯ (ЧИСТЫЙ AJAX)
@login_required
@csrf_exempt
def save_live_draft(request, project_id):
    if request.method != "POST":
        return JsonResponse({"error": "Method not allowed"}, status=405)

    try:
        req_data = json.loads(request.body.decode("utf-8"))
        # Берем только таймлайн
        frontend_timeline = req_data.get("timeline", [])

        # Получаем объект релиза
        release = ProjectVideoRelease.objects.get(project_id=project_id)

        # Прямое сохранение в текущий конфиг
        release.pj_current_config = frontend_timeline
        release.save(update_fields=["pj_current_config"])

        return JsonResponse({"success": True, "message": "Конфиг обновлен"})
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)


# 🔥 ЭНДПОИНТ ДЛЯ ВОССТАНОВЛЕНИЯ КОНФИГУРАЦИИ ИЗ ИСТОРИИ СБОРОК
@login_required
def restore_config_view(request, project_id, config_id):
    release = get_object_or_404(ProjectVideoRelease, project_id=project_id)
    release.add_or_update_config(config_id_to_move_up=config_id)
    release.save()
    messages.success(request, "Конфигурация успешно восстановлена в редакторе!")
    return redirect(f"/video/project/{project_id}/")


# 🛠️ ГЛАВНЫЙ ВИДЕОРЕДАКТОР: ОТВЕЧАЕТ СТРОГО ЗА ОТРИСОВКУ СТРАНИЦЫ
@login_required
def video_editor_view(request, project_id):
    # 1. Базовые пути и объекты проекта
    output_dir = os.path.join(settings.MEDIA_ROOT, "rendered_videos")
    filename = f"project_{project_id}.mp4"
    expected_mp4 = os.path.join(output_dir, filename)
    video_url = f"/media/rendered_videos/{filename}"

    audio_project = get_object_or_404(AudioProject, id=project_id, user=request.user)
    clean_title = audio_project.title.strip()

    # 2. Получение или создание записи релиза
    release_info, created = ProjectVideoRelease.objects.get_or_create(
        project_id=project_id,
        defaults={
            "pj_title": clean_title,
            "pj_status": "draft",
            "pj_config": [],
            "pj_current_config": [],
        },
    )

    if not created and release_info.pj_title != clean_title:
        release_info.pj_title = clean_title
        release_info.save(update_fields=["pj_title"])

    # 3. Получение данных проекта (треки и промпты)
    image_project = (
        ImageProject.objects.filter(title__icontains=clean_title).first()
        or ImageProject.objects.filter(article_id=audio_project.article_id).first()
    )

    tracks = list(AudioTrack.objects.filter(project=audio_project).order_by("order"))
    prompts = (
        list(ImagePrompt.objects.filter(project=image_project).order_by("order"))
        if image_project
        else []
    )
    # Расчет длительности треков
    for t in tracks:
        t.calculated_duration = 5.0
        if t.audio_file:
            try:
                audio_path = sanitize_media_path(t.audio_file.path)
                if os.path.exists(audio_path):
                    with AudioFileClip(audio_path) as audio_meta:
                        t.calculated_duration = round(audio_meta.duration, 2)
            except Exception:
                t.calculated_duration = 3.5

    # 4. Выбор активной конфигурации
    restore_cfg_id = request.GET.get("restore_cfg")
    active_config = None

    if restore_cfg_id and release_info.pj_config:
        found_archived = next(
            (cfg for cfg in release_info.pj_config if cfg.get("config_id") == restore_cfg_id), None
        )
        if found_archived:
            active_config = found_archived.get("timeline_state", [])

    if active_config is None:
        active_config = release_info.pj_current_config

    # 5. Сборка таймлайна (логика визуализации)
    timeline_data = []
    if active_config and len(active_config) > 0:
        for idx, saved_item in enumerate(active_config):
            # 1. Разделяем путь на части (папка + файл)
            meta_settings = saved_item.get("meta_settings", {})
            current_order = saved_item.get("order", idx + 1)
            saved_relative_path = meta_settings.get("image_name")

            # if saved_relative_path and saved_relative_path.startswith("/media/"):
            #     saved_relative_path = saved_relative_path.replace("/media/", "", 1)
            prompt = None
            if saved_relative_path and prompts:
                file_name_only = os.path.basename(saved_relative_path).lower().strip()
                prompt = next(
                    (
                        p
                        for p in prompts
                        if p.image
                        and os.path.basename(p.image.name).lower().strip() == file_name_only
                    ),
                    None,
                )

            track = tracks[idx] if idx < len(tracks) else None
            timeline_data.append(
                {
                    "order": current_order,
                    "track": track,
                    "prompt": prompt,
                    "audio_duration": getattr(track, "calculated_duration", 5.0),
                    "meta_settings": meta_settings,
                }
            )
    else:
        # Дефолтный расклад при первом запуске
        all_orders = set([t.order for t in tracks] + [p.order for p in prompts if p.image])
        for idx in range(max(all_orders) if all_orders else 0):
            current_order = idx + 1
            track = next((t for t in tracks if t.order == current_order), None)
            prompt = next((p for p in prompts if p.order == current_order), None)
            if track or (prompt and prompt.image):
                timeline_data.append(
                    {
                        "order": current_order,
                        "track": track,
                        "prompt": prompt,
                        "audio_duration": getattr(track, "calculated_duration", 5.0),
                        "meta_settings": {},
                    }
                )

    video_render = (
        {"status": "success", "video_file": {"url": video_url}}
        if os.path.exists(expected_mp4)
        else None
    )
    # 6. Рендер страницы
    return render(
        request,
        "videoeditor/video_editor.html",
        {
            "project": audio_project,
            "timeline_data": timeline_data,
            "video_render": video_render,
            "release_info": release_info,
            "current_config": active_config,
            "prompts": prompts,
        },
    )


# 🔥 ЭНДПОИНТ ДЛЯ СТАРТА СБОРКИ ВИДЕО (ЗАПУСКАЕМ В ОТДЕЛЬНОМ ПОТОКЕ, ЧТОБЫ НЕ БЛОКИРОВАТЬ СЕРВЕР)
@login_required
def start_video_render(request, project_id):
    # Если пришел GET — отдаем фронтенду состояние файла прогресса
    if request.method == "GET":
        task_id = request.GET.get("task_id")
        if not task_id:
            return JsonResponse({"error": "task_id отсутствует"}, status=400)

        status_file_path = os.path.join(settings.MEDIA_ROOT, f"status_{task_id}.json")
        if not os.path.exists(status_file_path):
            return JsonResponse(
                {"status": "processing", "progress": 5, "message": "🎬 Инициализация рендеринга..."}
            )

        try:
            with open(status_file_path, "r", encoding="utf-8") as f:
                status_data = json.load(f)
            return JsonResponse(status_data)
        except Exception:
            return JsonResponse(
                {"status": "processing", "progress": 8, "message": "Чтение состояния..."}
            )

    if request.method != "POST":
        return JsonResponse({"error": "Метод не разрешен"}, status=405)

    try:
        req_data = json.loads(request.body.decode("utf-8"))
    except Exception as e:
        return JsonResponse({"error": "Ошибка JSON " + str(e)}, status=400)

    # 1. Извлекаем переданный таймлайн
    serialized_timeline = req_data.get("timeline", [])

    # 2. Вытаскиваем слаг из бд, чтобы знать точную папку проекта
    audio_project = get_object_or_404(AudioProject, id=project_id, user=request.user)

    # 🔥 НАША ИСТИННАЯ РОТАЦИОННАЯ СИСТЕМА (3 ПОСЛЕДНИЕ СБОРКИ ПО ШАБЛОНУ)
    try:
        # Находим существующий или создаем новый релиз
        release, created = ProjectVideoRelease.objects.get_or_create(
            project_id=project_id,
            defaults={
                "pj_title": audio_project.title.strip(),
                "pj_status": "processing",
                "pj_config": [],  # Массив сборок
                "pj_current_config": serialized_timeline,
            },
        )

        # 1. Безопасно достаем историю прошлых сборок из поля pj_config
        history_configs = release.pj_config

        # Если из БД пришла строка (потому что поле TextField), парсим её в Python-список
        if isinstance(history_configs, str):
            try:
                history_configs = json.loads(history_configs)
            except:
                history_configs = []

        # На всякий случай проверяем, что это список
        if not isinstance(history_configs, list):
            history_configs = []

        # 2. Формируем структуру новой архивной записи ОДИН В ОДИН по твоему примеру
        new_config_entry = {
            "config_id": str(uuid.uuid4())[:8],  # Уникальный короткий ID сборки
            "scenes_count": len(serialized_timeline),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "timeline_state": serialized_timeline,  # Чистый исходный массив таймлайна
        }

        # Добавляем новую конфигурацию в начало архива
        history_configs.insert(0, new_config_entry)

        # Строго удерживаем лимит в 3 последние записи
        history_configs = history_configs[:3]

        # 3. Фиксируем изменения
        release.pj_status = "processing"

        # Убираем двойное экранирование слэшей:
        # Если в Django поле является JSONField, передаем чистый Python-объект (список)
        # Если это TextField (строка), то превращаем в чистую строку ОДИН РАЗ через json.dumps
        from django.db.models import JSONField

        # Проверяем тип поля pj_config в базе
        pj_config_field = release._meta.get_field("pj_config")
        if isinstance(pj_config_field, JSONField):
            release.pj_config = history_configs
        else:
            release.pj_config = json.dumps(history_configs, ensure_ascii=False)

        # То же самое делаем для текущего живого черновика pj_current_config
        pj_current_field = release._meta.get_field("pj_current_config")
        if isinstance(pj_current_field, JSONField):
            release.pj_current_config = serialized_timeline
        else:
            release.pj_current_config = json.dumps(serialized_timeline, ensure_ascii=False)

        release.video_created_at = time.strftime("%Y-%m-%d %H:%M:%S")

        # Сохраняем измененные поля в базу данных
        release.save(
            update_fields=[
                "pj_status",
                "pj_config",
                "pj_current_config",
                "video_created_at",
            ]
        )
        print(
            f"💾 [БАЗА ДАННЫХ] Сборка сохранена по правильному шаблону. Всего в истории: {len(history_configs)}/3"
        )

    except Exception as db_err:
        print(f"⚠️ Ошибка автоматического сохранения ротации конфигов в БД: {str(db_err)}")

    # Пытаемся взять слаг из модели
    if hasattr(audio_project, "project_slug") and audio_project.project_slug:
        folder_name = audio_project.project_slug
    elif hasattr(audio_project, "slug") and audio_project.slug:
        folder_name = audio_project.slug
    else:
        folder_name = f"project_{project_id}"

    project_media_dir = os.path.join(settings.MEDIA_ROOT, "projects", folder_name)

    # Вычисляем пути для рендера
    output_dir = os.path.join(settings.MEDIA_ROOT, "rendered_videos")
    os.makedirs(output_dir, exist_ok=True)

    filename = f"project_{project_id}.mp4"
    expected_mp4 = os.path.join(output_dir, filename)
    video_url = f"/media/rendered_videos/{filename}"

    task_id = str(uuid.uuid4())
    status_file_path = os.path.join(settings.MEDIA_ROOT, f"status_{task_id}.json")

    # 3. Запускаем сборку в потоке
    thread = threading.Thread(
        target=make_video_processing_task,
        kwargs={
            "timeline_list": serialized_timeline,
            "project_id": project_id,
            "s_file_path": status_file_path,
            "out_dir": output_dir,
            "out_path": expected_mp4,
            "v_url": video_url,
            "project_media_dir": project_media_dir,
        },
    )
    thread.start()

    return JsonResponse({"status": "success", "success": True, "task_id": task_id})


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


@login_required
def download_project_media(request, project_id):
    """
    Скачивание ВСЕГО проекта в ZIP:
    - Все аудиофайлы (audio_01.wav, audio_02.wav...)
    - Все сгенерированные картинки (image_01.jpg, image_02.jpg...)
    - project_metadata.json (полная информация о проекте)
    - voices_meta_<lang>.json (метаданные озвучки)
    """
    # Получаем аудиопроект
    audio_project = get_object_or_404(AudioProject, id=project_id, user=request.user)

    # Получаем статью (кластер)
    article_cluster = audio_project.article
    if not article_cluster:
        messages.error(request, "⚠️ У проекта нет связанной статьи!")
        return redirect("audio:audio_edit", pk=project_id)

    # Получаем все треки
    tracks = audio_project.tracks.filter(status="success").order_by("order")

    if not tracks.exists():
        messages.error(request, "⚠️ В проекте нет готовых аудиофайлов!")
        return redirect("audio:audio_edit", pk=project_id)

    # Получаем все промпты картинок для этой статьи
    image_prompts = ImageProject.objects.filter(article__cluster=article_cluster).order_by(
        "scene_type__order"
    )

    # Создаём ZIP в памяти
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        project_lang = (audio_project.language or "ru").lower()
        article_title = article_cluster.translations.filter(language__code="ru").first()
        article_title = article_title.title if article_title else f"Project_{project_id}"
        safe_title = "".join(c if c.isalnum() or c in " _-" else "_" for c in article_title[:50])

        # === 1. АУДИОФАЙЛЫ ===
        audio_count = 0
        for track in tracks:
            if track.audio_file:
                file_path = os.path.join(settings.MEDIA_ROOT, track.audio_file)

                if os.path.exists(file_path):
                    # Имя в ZIP: audio_01.wav, audio_02.wav...
                    ext = os.path.splitext(file_path)[1]
                    arcname = f"audio/audio_{track.order:02d}{ext}"
                    zip_file.write(file_path, arcname)
                    audio_count += 1

        # === 2. ИЗОБРАЖЕНИЯ ===
        image_count = 0
        for idx, img_prompt in enumerate(image_prompts, 1):
            if img_prompt.image_url:
                # Извлекаем путь из URL
                image_path_str = img_prompt.image_url.replace(settings.MEDIA_URL, "")
                image_path = os.path.join(settings.MEDIA_ROOT, image_path_str)

                if os.path.exists(image_path):
                    ext = os.path.splitext(image_path)[1]
                    arcname = f"images/image_{idx:02d}{ext}"
                    zip_file.write(image_path, arcname)
                    image_count += 1

        # === 3. METADATA JSON ===
        # Получаем основной перевод статьи
        main_translation = article_cluster.translations.filter(language__code="ru").first()
        if not main_translation:
            main_translation = article_cluster.translations.first()

        metadata = {
            "project_info": {
                "title": article_title,
                "language": project_lang,
                "provider": audio_project.provider,
                "created_at": audio_project.created_at.isoformat(),
                "total_tracks": tracks.count(),
                "total_images": image_prompts.count(),
            },
            "audio_tracks": [],
            "images": [],
        }

        # Добавляем информацию о треках
        for track in tracks:
            track_meta = {
                "order": track.order,
                "text": track.text,
                "status": track.status,
                "speaker": getattr(track, "speaker_name", "unknown"),
            }

            # Пытаемся найти длительность
            if track.audio_file:
                file_path = os.path.join(settings.MEDIA_ROOT, track.audio_file)
                if os.path.exists(file_path):
                    try:
                        audio_info = mutagen.File(file_path)
                        if audio_info and audio_info.info:
                            track_meta["duration"] = round(audio_info.info.length, 2)
                    except:
                        pass

            metadata["audio_tracks"].append(track_meta)

        # Добавляем информацию о картинках
        for idx, img_prompt in enumerate(image_prompts, 1):
            img_meta = {
                "order": idx,
                "scene_type": img_prompt.scene_type.name if img_prompt.scene_type else "unknown",
                "prompt": img_prompt.prompt_text,
                "image_url": img_prompt.image_url,
            }
            metadata["images"].append(img_meta)

        # Сохраняем metadata.json в ZIP
        zip_file.writestr(
            "project_metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2)
        )

        # === 4. README ===
        readme_text = f"""
PROJECT: {article_title}
LANGUAGE: {project_lang.upper()}
CREATED: {audio_project.created_at.strftime("%Y-%m-%d %H:%M")}

STRUCTURE:
├── audio/           - Аудиофайлы для озвучки (audio_01.wav, audio_02.wav...)
├── images/          - Сгенерированные изображения (image_01.jpg, image_02.jpg...)
└── project_metadata.json - Полная информация о проекте

HOW TO USE IN CAPCUT:
1. Распакуйте архив
2. Импортируйте все файлы из папки audio/ на таймлайн
3. Добавьте изображения из папки images/ между аудиофрагментами
4. Откройте project_metadata.json для просмотра текстов и промптов

TOTAL AUDIO TRACKS: {audio_count}
TOTAL IMAGES: {image_count}
"""
        zip_file.writestr("README.txt", readme_text.strip())

    # Подготовка файла к отдаче
    buffer.seek(0)
    filename = f"media_project_{project_id}_{safe_title.replace(' ', '_')}.zip"

    response = HttpResponse(buffer.getvalue(), content_type="application/zip")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'

    messages.success(
        request, f"✅ Проект упакован: {audio_count} аудио + {image_count} изображений"
    )
    return response
