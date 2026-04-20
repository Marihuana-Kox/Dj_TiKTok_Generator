import os
import time
import requests
from django.conf import settings

# Используем ту же модель, что и раньше (Flux Schnell - быстрая и качественная)
MODEL_ID = "black-forest-labs/FLUX.1-schnell"
API_URL = f"https://api-inference.huggingface.co/models/{MODEL_ID}"


def get_headers():
    # Пытаемся взять токен из переменных окружения (куда мы его положили в views.py)
    token = os.getenv("HF_API_TOKEN")
    if not token:
        raise Exception(
            "HF_API_TOKEN not found. Please set it in Config or .env")
    return {"Authorization": f"Bearer {token}"}


def generate_image(prompt: str, output_path: str, width: int = 1024, height: int = 1024):
    """Генерирует одну картинку."""
    print(f"   🎨 Generating: {prompt[:50]}...")

    full_prompt = f"{prompt}, high quality, detailed, masterpiece, 8k, photorealistic"
    negative_prompt = "blurry, ugly, distorted, low quality, watermark, text, signature, bad anatomy"

    payload = {
        "inputs": full_prompt,
        "parameters": {
            "negative_prompt": negative_prompt,
            "width": width,
            "height": height,
            "num_inference_steps": 25
        }
    }

    headers = get_headers()

    # Пробуем до 3 раз (на случай холодной загрузки модели)
    for attempt in range(3):
        try:
            response = requests.post(
                API_URL, headers=headers, json=payload, timeout=90)

            if response.status_code == 200:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(response.content)
                print(f"   ✅ Saved: {output_path}")
                return output_path

            elif response.status_code == 503:
                print(
                    f"   ⏳ Model loading... waiting 20s (attempt {attempt+1})")
                time.sleep(20)
                continue

            elif response.status_code == 401:
                raise Exception(
                    "Invalid HF Token (401). Check Config settings.")

            elif response.status_code == 404:
                raise Exception(f"Model not found (404): {MODEL_ID}")

            else:
                err_text = response.text[:150]
                raise Exception(f"HF Error {response.status_code}: {err_text}")

        except requests.exceptions.Timeout:
            print(f"   ⏳ Timeout, retrying...")
            time.sleep(5)
            continue

    raise Exception("Failed to generate image after 3 attempts.")


def generate_images_batch(prompts: list, output_folder: str, topic: str = ""):
    """Генерирует серию картинок по списку промптов."""
    paths = []
    print(f"\n   🖼️  Starting batch generation: {len(prompts)} images...")

    for i, p in enumerate(prompts):
        safe_topic = topic[:10].replace(" ", "_").replace("/", "_")
        filename = f"image_{i+1}_{safe_topic}.jpg"
        output_path = os.path.join(output_folder, filename)

        try:
            path = generate_image(p, output_path)
            paths.append(path)
            if i < len(prompts) - 1:
                time.sleep(2)  # Пауза между запросами
        except Exception as e:
            print(f"   ❌ Failed image {i+1}: {e}")
            # Не прерываем весь процесс, идем дальше

    print(f"   ✅ Batch finished: {len(paths)}/{len(prompts)} images.")
    return paths
