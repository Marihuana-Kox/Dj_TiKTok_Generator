from ai_inspector.services import generate_image
try:
    print("Starting generation test...")
    img = generate_image('huggingface', 'Astronaut riding a horse on Mars')
    with open('test_result.jpg', 'wb') as f:
        f.write(img)
    print("OK: Image saved successfully")
except Exception as e:
    print(f"ERROR: {e}")
