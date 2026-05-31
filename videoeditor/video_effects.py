import numpy as np
from PIL import Image


class VideoEffects:
    """
    Центральный класс для применения визуальных, аудио-эффектов,
    пользовательских фильтров и генерации титров на основе актуального синтаксиса MoviePy 2.x+.
    """

    @staticmethod
    def apply_visual_effect(clip, effect_type):
        if not effect_type or effect_type == "none":
            return clip

        w, h = clip.size
        duration = clip.duration if clip.duration and clip.duration > 0 else 5.0

        if effect_type == "zoom_in":

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

        return clip

    @staticmethod
    def apply_color_filter(clip, filter_type):
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

        return clip

    @staticmethod
    def apply_audio_effects(audio_clip, audio_settings):
        """
        Безопасный вызов аудиоэффектов через встроенные методы самого AudioClip.
        """
        if not audio_clip:
            return audio_clip

        try:
            volume_pct = audio_settings.get("volume", 100)
            fade_in = float(audio_settings.get("fade_in", 0))
            fade_out = float(audio_settings.get("fade_out", 0))

            if volume_pct != 100:
                audio_clip = audio_clip.multiply_volume(volume_pct / 100.0)

            if fade_in > 0:
                audio_clip = audio_clip.audio_fadein(fade_in)

            if fade_out > 0:
                audio_clip = audio_clip.audio_fadeout(fade_out)
        except Exception as e:
            print(f"⚠️ Ошибка применения аудиоэффектов: {e}")

        return audio_clip

    @staticmethod
    def attach_text_overlay(video_clip, text_settings):
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

            from moviepy.video.compositing import CompositeVideoClip

            return CompositeVideoClip([video_clip, text_clip]).with_duration(video_clip.duration)
        except Exception as e:
            print(f"⚠️ Титры пропущены: {e}")
            return video_clip
