# app/utils/face_utils.py

import base64
import numpy as np
from PIL import Image
import io
import os
import tempfile


def decode_base64_image(base64_string):
    """Convert base64 string to numpy array."""
    if ',' in base64_string:
        base64_string = base64_string.split(',')[1]

    image_data = base64.b64decode(base64_string)
    image      = Image.open(io.BytesIO(image_data)).convert('RGB')
    return np.array(image)


def save_temp_image(image_array):
    """
    Save numpy image array to a temporary file.
    DeepFace works best with file paths.
    Returns temp file path.
    """
    temp_file = tempfile.NamedTemporaryFile(
        suffix='.jpg',
        delete=False
    )
    img = Image.fromarray(image_array)
    img.save(temp_file.name, 'JPEG', quality=95)
    temp_file.close()
    return temp_file.name


def delete_temp_file(path):
    """Delete temp file after use."""
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


def extract_face_encoding(base64_image):
    """
    Extract face embedding (encoding) from base64 image using DeepFace.
    Uses ArcFace model — most accurate.
    Returns (embedding list, message)
    """
    from deepface import DeepFace

    temp_path = None
    try:
        # ── Decode image ──
        image_array = decode_base64_image(base64_image)
        temp_path   = save_temp_image(image_array)

        # ── Detect face first ──
        faces = DeepFace.extract_faces(
            img_path        = temp_path,
            detector_backend = 'opencv',   # fastest detector
            enforce_detection = True
        )

        if len(faces) == 0:
            return None, "No face detected. Please look directly at the camera."

        if len(faces) > 1:
            return None, "Multiple faces detected. Please ensure only you are in frame."

        # ── Extract embedding ──
        embedding_result = DeepFace.represent(
            img_path         = temp_path,
            model_name       = 'ArcFace',    # most accurate model
            detector_backend = 'opencv',
            enforce_detection = True
        )

        if not embedding_result:
            return None, "Could not extract face encoding. Please try again."

        embedding = embedding_result[0]['embedding']  # 512-point vector
        return embedding, "Success"

    except ValueError as e:
        error_msg = str(e)
        if "Face could not be detected" in error_msg:
            return None, "No face detected. Ensure good lighting and look at camera."
        return None, f"Face detection error: {error_msg}"

    except Exception as e:
        return None, f"Error processing image: {str(e)}"

    finally:
        delete_temp_file(temp_path)


def verify_face(captured_base64, stored_encoding_list, threshold=0.40):
    from deepface import DeepFace

    temp_path = None
    try:
        image_array = decode_base64_image(captured_base64)
        temp_path   = save_temp_image(image_array)

        # ── Anti-spoofing check first ──
        try:
            face_objs = DeepFace.extract_faces(
                img_path          = temp_path,
                detector_backend  = 'opencv',
                enforce_detection = True,
                anti_spoofing     = True       # ← blocks photo attacks
            )
            # Check if face is real
            if face_objs:
                is_real = face_objs[0].get('is_real', True)
                antispoof_score = face_objs[0].get('antispoof_score', 1.0)
                if not is_real:
                    return False, 0.0, "Spoof detected! Please show your real face, not a photo or screen."
        except Exception as spoof_err:
            # If anti-spoofing fails, log but continue
            print(f"Anti-spoof check error: {spoof_err}")

        embedding_result = DeepFace.represent(
            img_path          = temp_path,
            model_name        = 'ArcFace',
            detector_backend  = 'opencv',
            enforce_detection = True
        )

        if not embedding_result:
            return False, 0.0, "Could not process face. Please try again."

        captured_embedding = np.array(embedding_result[0]['embedding'])
        stored_embedding   = np.array(stored_encoding_list)

        # ── Calculate cosine distance ──
        dot_product = np.dot(captured_embedding, stored_embedding)
        norm_a      = np.linalg.norm(captured_embedding)
        norm_b      = np.linalg.norm(stored_embedding)
        cosine_sim  = dot_product / (norm_a * norm_b)
        distance    = 1 - cosine_sim

        confidence  = round((1 - distance) * 100, 2)
        match       = distance <= threshold

        if match:
            return True, confidence, f"Face verified! Confidence: {confidence}%"
        else:
            return False, confidence, f"Face not recognized. Confidence too low: {confidence}%"

    except ValueError as e:
        error_msg = str(e)
        if "Face could not be detected" in error_msg:
            return False, 0.0, "No face detected. Please look directly at camera."
        return False, 0.0, f"Face error: {error_msg}"

    except Exception as e:
        return False, 0.0, f"Error verifying face: {str(e)}"

    finally:
        delete_temp_file(temp_path)