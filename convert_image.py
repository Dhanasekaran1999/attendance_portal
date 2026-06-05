# convert_image.py

import base64

def image_to_base64(image_path):
    with open(image_path, 'rb') as f:
        encoded = base64.b64encode(f.read()).decode('utf-8')
    return f"data:image/jpeg;base64,{encoded}"

# ── Change this to YOUR actual photo filename ──
image_path = r"C:\Users\LENOVO\PycharmProjects\attendance_portal\arjun.jpeg"

base64_string = image_to_base64(image_path)

# Save to a text file (easier to copy than terminal output)
with open("base64_output.txt", "w") as f:
    f.write(base64_string)

print("✅ Done! base64 string saved to base64_output.txt")
print(f"📏 Length: {len(base64_string)} characters")