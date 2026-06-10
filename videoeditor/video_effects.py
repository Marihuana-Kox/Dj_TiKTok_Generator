import numpy as np
from PIL import Image

# В MoviePy v2 все эффекты импортируются через vfx и afx
from moviepy import vfx, afx
from moviepy.video.compositing.CompositeVideoClip import CompositeVideoClip


class VideoEffects:
    """
    Центральный класс для применения визуальных, аудио-эффектов,
    пользовательских фильтров и генерации титров на основе актуального синтаксиса MoviePy 2.x+.
    """

    @staticmethod
    def apply_video_effects(clip, meta_settings):
        """
        ГЛАВНЫЙ ДИСПЕТЧЕР: Вызывается во views.py.
        Применяет все настройки по очереди, строго возвращая изменённые копии (out-place).
        """
        if not meta_settings:
            return clip

        # 1. Применяем визуальный эффект (zoom_in, zoom_out, move_up, move_down, flash)
        effect_type = meta_settings.get("video_effects") or meta_settings.get("effect")
        clip = VideoEffects.apply_visual_effect(clip, effect_type)

        # 2. Применяем цветовой фильтр (grayscale, sepia, vhs_glitch)
        filter_type = meta_settings.get("filter")
        clip = VideoEffects.apply_color_filter(filter_type)

        # 3. Применяем отражение (Mirror), если включено на фронтенде
        fx_list = []
        if meta_settings.get("mirror_x"):
            fx_list.append(vfx.MirrorX())
        if meta_settings.get("mirror_y"):
            fx_list.append(vfx.MirrorY())
        if fx_list:
            clip = clip.with_effects(fx_list)

        # 4. Применяем переход (переходы в v2 накладываются как эффекты FadeIn/FadeOut или трансформации)
        transition_type = meta_settings.get("transition")
        clip = VideoEffects.apply_transition(clip, transition_type)

        # 5. Накладываем текст (титры)
        text_overlay = meta_settings.get("text_overlay")
        if text_overlay:
            clip = VideoEffects.attach_text_overlay(clip, text_overlay)

        return clip

    @staticmethod
    def resize_to_tiktok(clip):
        """Вспомогательный метод для приведения картинок к формату TikTok 9:16"""
        return clip.with_effects([vfx.Resize(size=(1080, 1920))])

    @staticmethod
    def apply_visual_effect(clip, effect_type):
        """
        Применение визуальных эффектов анимации камеры (FX).
        Для движений применяется умный кроп с увеличением на 20%, чтобы не ломать края кадра.
        """
        if not effect_type or effect_type == "none":
            return clip

        w, h = 1080, 1920  # Целевое разрешение TikTok холста
        duration = clip.duration if clip.duration and clip.duration > 0 else 5.0

        try:
            # === ДВИЖЕНИЕ СВЕРХУ ВНИЗ ===
            if effect_type == "move_down":
                w, h = clip.size
                enlarged = clip.resized(1.2)
                new_w, new_h = enlarged.size
                max_scroll = new_h - h

                def pos_down(t):
                    # Старт: -max_scroll (выше экрана), финиш: 0 (центр)
                    y = int(-max_scroll + (t / duration) * max_scroll) if t < duration else 0
                    return ("center", y)

                # ✅ Порядок: 1) кроп, 2) позиция
                return enlarged.with_effects(
                    [vfx.Crop(x_center=new_w // 2, y_center=new_h // 2, width=w, height=h)]
                ).with_position(pos_down)

            # === ДВИЖЕНИЕ СНИЗУ ВВЕРХ ===
            elif effect_type == "move_up":
                w, h = clip.size
                enlarged = clip.resized(1.2)
                new_w, new_h = enlarged.size
                max_scroll = new_h - h

                def pos_up(t):
                    # Старт: +max_scroll (ниже экрана), финиш: 0 (центр)
                    y = int(max_scroll - (t / duration) * max_scroll) if t < duration else 0
                    return ("center", y)

                # ✅ Порядок: 1) кроп, 2) позиция
                return enlarged.with_effects(
                    [vfx.Crop(x_center=new_w // 2, y_center=new_h // 2, width=w, height=h)]
                ).with_position(pos_up)

            # === ЭФФЕКТ: ПЛАВНОЕ ПРИБЛИЖЕНИЕ (Zoom In) ===
            elif effect_type == "zoom_in":

                def zoom_in_anim(get_frame, t):
                    frame = get_frame(t)
                    scale = 1.0 + (t / duration) * 0.15
                    pil_img = Image.fromarray(frame)
                    new_w, new_h = int(w * scale), int(h * scale)
                    resized_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    left = (new_w - w) // 2
                    top = (new_h - h) // 2
                    return np.array(resized_img.crop((left, top, left + w, top + h)))

                return clip.transform(zoom_in_anim)

            # === ЭФФЕКТ: ПЛАВНОЕ ОТДАЛЕНИЕ (Zoom Out) ===
            elif effect_type == "zoom_out":

                def zoom_out_anim(get_frame, t):
                    frame = get_frame(t)
                    scale = 1.15 - (t / duration) * 0.15
                    pil_img = Image.fromarray(frame)
                    new_w, new_h = int(w * scale), int(h * scale)
                    resized_img = pil_img.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    left = (new_w - w) // 2
                    top = (new_h - h) // 2
                    return np.array(resized_img.crop((left, top, left + w, top + h)))

                return clip.transform(zoom_out_anim)

            # === ЭФФЕКТ: КИНОШНАЯ ВСПЫШКА (Flash) ===
            elif effect_type == "flash":

                def flash_anim(get_frame, t):
                    frame = get_frame(t).astype(np.int16)
                    if t < 0.4:
                        intensity = int((1.0 - (t / 0.4)) * 120)
                        frame = np.clip(frame + intensity, 0, 255)
                    return frame.astype(np.uint8)

                return clip.transform(flash_anim)

        except Exception as e:
            print(f"⚠️ Ошибка применения визуального эффекта {effect_type}: {e}")

        return clip

    @staticmethod
    def apply_color_filter(clip, filter_type):
        """Применение цветовых фильтров"""
        if not filter_type or filter_type == "none":
            return clip

        if filter_type == "grayscale":

            def to_grayscale(image):
                dot_product = np.dot(image[..., :3], [0.2989, 0.5870, 0.1140])
                return np.stack((dot_product,) * 3, axis=-1).astype(np.uint8)

            return clip.image_transform(to_grayscale)

        elif filter_type == "sepia":

            def to_sepia(image):
                sepia_matrix = np.array(
                    [[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]]
                )
                sepia_img = np.dot(image[..., :3], sepia_matrix.T)
                return np.clip(sepia_img, 0, 255).astype(np.uint8)

            return clip.image_transform(to_sepia)

        elif filter_type == "vhs_glitch":

            def to_vhs(image):
                r_channel = np.roll(image[..., 0], shift=-4, axis=1)
                g_channel = image[..., 1]
                b_channel = np.roll(image[..., 2], shift=4, axis=1)
                return np.stack((r_channel, g_channel, b_channel), axis=-1)

            return clip.image_transform(to_vhs)

        return clip

    @staticmethod
    def apply_audio_effects(audio_clip, audio_settings):
        """Применение аудиоэффектов строго по синтаксису MoviePy v2 через afx"""
        if not audio_clip or not audio_settings:
            return audio_clip

        try:
            volume_pct = audio_settings.get("volume", 100)
            fade_in = float(audio_settings.get("fade_in", 0))
            fade_out = float(audio_settings.get("fade_out", 0))

            audio_fx_list = []

            if volume_pct != 100:
                audio_fx_list.append(afx.MultiplyVolume(volume_pct / 100.0))

            if fade_in > 0:
                audio_fx_list.append(afx.AudioFadeIn(duration=fade_in))

            if fade_out > 0:
                audio_fx_list.append(afx.AudioFadeOut(duration=fade_out))

            if audio_fx_list:
                audio_clip = audio_clip.with_effects(audio_fx_list)

        except Exception as e:
            print(f"⚠️ Ошибка применения аудиоэффектов: {e}")

        return audio_clip

    @staticmethod
    def attach_text_overlay(video_clip, text_settings):
        """Накладывание субтитров и текстовых блоков поверх видео"""
        text_string = text_settings.get("text", "").strip()
        if not text_string:
            return video_clip

        font_name = text_settings.get("font", "Arial")
        font_size = int(text_settings.get("font_size", 30))
        font_color = text_settings.get("font_color", "#FFFFFF")
        position = text_settings.get("position", "bottom")

        try:
            from moviepy.video.VideoClip import TextClip

            text_clip = TextClip(
                text=text_string,
                font=font_name,
                font_size=font_size,
                color=font_color,
                stroke_color="#000000",
                stroke_width=1.5,
                size=(video_clip.size[0] - 40, None),
            )
            text_clip = text_clip.with_duration(video_clip.duration)

            if position == "bottom":
                pos_xy = ("center", video_clip.size[1] - text_clip.size[1] - 50)
            elif position == "top":
                pos_xy = ("center", 50)
            else:
                pos_xy = ("center", "center")

            text_clip = text_clip.with_position(pos_xy)

            return CompositeVideoClip([video_clip, text_clip]).with_duration(video_clip.duration)

        except Exception as e:
            print(f"⚠️ Титры пропущены: {e}")
            return video_clip

    @staticmethod
    def apply_transition(clip, transition_type, duration=0.6):
        """
        Применение переходов между сценами по правилам MoviePy v2.
        Восстановлена оригинальная сочная математика наездов и сдвигов.
        """
        if not transition_type or transition_type == "none":
            return clip

        try:
            w, h = clip.size
            fx_list = []

            # 1. Плавные наплывы (Кроссфейд и уход в черный)
            if transition_type in ["fade", "crossfade", "fade_black"]:
                fx_list.append(vfx.FadeIn(duration=duration))
                fx_list.append(vfx.FadeOut(duration=duration))
                if fx_list:
                    clip = clip.with_effects(fx_list)

            # 2. Сдвиг ВЛЕВО (Оригинальный алгоритм: кадр плавно смещается влево)
            elif transition_type == "slide_left":
                return clip.with_position(
                    lambda t: (int(-w + (t / duration) * w) if t < duration else 0, 0)
                )

            # 3. Сдвиг ВПРАВО (Тот самый крутой вариант, который был изначально!)
            elif transition_type == "slide_right":
                return clip.with_position(
                    lambda t: (int(w - (t / duration) * w) if t < duration else 0, 0)
                )

            # 4. Сдвиг СВЕРХУ ВНИЗ (Кадр плавно падает сверху в центр)
            elif transition_type == "slide_top_to_bottom":
                return clip.with_position(
                    lambda t: (0, int(-h + (t / duration) * h) if t < duration else 0)
                )

            # 5. Сдвиг СНИЗУ ВВЕРХ (Кадр плавно поднимается снизу в центр)
            elif transition_type == "slide_bottom_to_top":
                return clip.with_position(
                    lambda t: (0, int(h - (t / duration) * h) if t < duration else 0)
                )

            # 6. Переход: Динамичное КРУЧЕНИЕ И ЗУМ из центра (Spin Zoom)
            elif transition_type == "spin_zoom":
                # Генераторы работают только первые duration секунд, потом фиксируются
                angle_fn = lambda t: 360 * (t / duration) if t < duration else 0
                scale_fn = lambda t: 0.2 + 0.2 * (t / duration) if t < duration else 1.0

                animated = clip.with_effects(
                    [vfx.Resize(scale_fn), vfx.Rotate(angle_fn)]
                ).with_position(("center", "center"))

                return animated.with_duration(clip.duration)

            return clip

        except Exception as e:
            print(f"⚠️ Ошибка применения перехода {transition_type}: {e}")

        return clip
