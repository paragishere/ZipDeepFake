import os
import cv2
import torch
import sqlite3
import numpy as np

from datetime import datetime
from flask import request
from torchvision import transforms, models
from torchvision.models import ResNet18_Weights

from .db import get_db


# ==================================================
# CREATE LOG FOLDER
# ==================================================
os.makedirs("logs", exist_ok=True)
LOG_FILE = "logs/events.log"


# ==================================================
# DEVICE
# ==================================================
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ==================================================
# LOAD MODEL
# ==================================================
model = models.resnet18(weights=ResNet18_Weights.DEFAULT)

model.fc = torch.nn.Sequential(
    torch.nn.Linear(model.fc.in_features, 1),
    torch.nn.Sigmoid()
)

model.load_state_dict(
    torch.load(
        "deepfake_model.pth",
        map_location=device
    )
)

model = model.to(device)
model.eval()


# ==================================================
# IMAGE TRANSFORM
# ==================================================
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.5, 0.5, 0.5],
        [0.5, 0.5, 0.5]
    )
])


# ==================================================
# FACE DETECTOR
# ==================================================
prototxt_path = "deploy.prototxt.txt"
model_path = "res10_300x300_ssd_iter_140000.caffemodel"

net = cv2.dnn.readNetFromCaffe(
    prototxt_path,
    model_path
)


# ==================================================
# LOG EVENT
# ==================================================
def log_event(event_type, status="OK"):

    try:
        conn = get_db()
        cursor = conn.cursor()

        ip = request.remote_addr
        user_agent = request.headers.get("User-Agent")
        endpoint = request.path
        method = request.method

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        cursor.execute("""
            INSERT INTO events
            (event_type, ip, endpoint, method, user_agent, status)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            event_type,
            ip,
            endpoint,
            method,
            user_agent,
            status
        ))

        conn.commit()
        conn.close()

        line = f"{timestamp} | {event_type} | {ip} | {endpoint} | {method} | {status}\n"

        with open(LOG_FILE, "a") as f:
            f.write(line)

    except sqlite3.OperationalError as e:
        print("DB Lock:", e)

    except Exception as e:
        print("Log Error:", e)


# ==================================================
# DETECT FACE
# ==================================================
def detect_faces(frame):

    (h, w) = frame.shape[:2]

    blob = cv2.dnn.blobFromImage(
        frame,
        1.0,
        (300, 300),
        (104.0, 177.0, 123.0)
    )

    net.setInput(blob)
    detections = net.forward()

    faces = []

    for i in range(detections.shape[2]):

        confidence = detections[0, 0, i, 2]

        if confidence > 0.5:

            box = detections[0, 0, i, 3:7] * np.array(
                [w, h, w, h]
            )

            (x1, y1, x2, y2) = box.astype("int")

            x1 = max(0, x1)
            y1 = max(0, y1)
            x2 = min(w, x2)
            y2 = min(h, y2)

            faces.append((x1, y1, x2, y2))

    return faces


# ==================================================
# PREDICT SINGLE FACE
# ==================================================
def predict_face(face):

    face = transform(face).unsqueeze(0).to(device)

    with torch.no_grad():
        output = model(face)

    return output.item()


# ==================================================
# MAIN VIDEO PREDICTION
# ==================================================
def predict_video(video_path):

    cap = cv2.VideoCapture(video_path)

    frame_count = 0
    interval = 6

    scores = []

    while True:

        ret, frame = cap.read()

        if not ret:
            break

        if frame_count % interval == 0:

            faces = detect_faces(frame)

            for (x1, y1, x2, y2) in faces:

                face = frame[y1:y2, x1:x2]

                if face.size == 0:
                    continue

                score = predict_face(face)
                scores.append(score)

        frame_count += 1

    cap.release()

    # ==========================================
    # NO FACE FOUND
    # ==========================================
    if len(scores) == 0:
        return "NO FACE DETECTED"

    scores = np.array(scores)

    # ==========================================
    # ANALYSIS
    # ==========================================
    avg_score = np.mean(scores)

    fake_ratio = np.sum(
        scores < 0.5
    ) / len(scores)

    variance = np.var(scores)

    gradients = np.abs(np.diff(scores))

    avg_gradient = (
        np.mean(gradients)
        if len(gradients) > 0
        else 0
    )

    # ==========================================
    # SEGMENT ANALYSIS
    # ==========================================
    window = 5

    segments = [
        scores[i:i+window]
        for i in range(0, len(scores), window)
    ]

    fake_segments = 0

    for seg in segments:

        seg_fake_ratio = np.sum(
            seg < 0.5
        ) / len(seg)

        if seg_fake_ratio > 0.6:
            fake_segments += 1

    # ==========================================
    # FINAL DECISION
    # ==========================================
    if fake_segments > 0:
        decision = "FAKE"

    elif fake_ratio > 0.6:
        decision = "FAKE"

    elif variance > 0.05:
        decision = "FAKE"

    elif avg_gradient > 0.2:
        decision = "FAKE"

    else:
        decision = "REAL"

    # ==========================================
    # FUSION SCORE
    # ==========================================
    final_score = (
        0.4 * avg_score +
        0.2 * (1 - fake_ratio) +
        0.2 * (1 - variance) +
        0.2 * (1 - avg_gradient)
    )

    # ==========================================
    # RETURN FULL DATA
    # ==========================================
    return {
        "result": decision,
        "score": round(float(final_score), 2),
        "avg_score": round(float(avg_score), 2),
        "fake_ratio": round(float(fake_ratio), 2),
        "variance": round(float(variance), 4)
    }