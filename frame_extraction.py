import cv2
import numpy as np
import os

video_root = "dataset"
categories = ["real", "fake"]

# Load face detection model
prototxt_path = "deploy.prototxt.txt"
model_path = "res10_300x300_ssd_iter_140000.caffemodel"
net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

# Frame enhancement
def enhance_frame(frame):
    frame = cv2.resize(frame, (640, 480))
    lab = cv2.cvtColor(frame, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    cl = clahe.apply(l)
    enhanced_lab = cv2.merge((cl, a, b))
    enhanced_frame = cv2.cvtColor(enhanced_lab, cv2.COLOR_LAB2BGR)
    return enhanced_frame

# Face detection
def detect_faces(frame):
    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                                 (104.0, 177.0, 123.0))
    net.setInput(blob)
    detections = net.forward()
    
    faces = []
    for i in range(detections.shape[2]):
        confidence = detections[0, 0, i, 2]
        if confidence > 0.5:
            box = detections[0, 0, i, 3:7] * np.array([w, h, w, h])
            (x1, y1, x2, y2) = box.astype("int")
            faces.append((x1, y1, x2, y2))
    return faces


# 🔥 MAIN LOOP
for category in categories:
    video_folder = os.path.join(video_root, category)
    
    for video_file in os.listdir(video_folder):
        video_path = os.path.join(video_folder, video_file)
        
        print(f"\nProcessing: {video_path}")
        
        # Create dataset folder
        dataset_path = os.path.join("dataset", category)
        os.makedirs(dataset_path, exist_ok=True)

        # Open video
        cap = cv2.VideoCapture(video_path)
        
        frame_count = 0
        interval = 6

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            if frame_count % interval == 0:
                
                enhanced_frame = enhance_frame(frame)
                faces = detect_faces(enhanced_frame)

                for i, (x1, y1, x2, y2) in enumerate(faces):
                    h, w = enhanced_frame.shape[:2]

                    # Padding
                    pad_x = int((x2 - x1) * 0.25)
                    pad_y = int((y2 - y1) * 0.35)

                    x1 = max(0, x1 - pad_x)
                    y1 = max(0, y1 - pad_y)
                    x2 = min(w, x2 + pad_x)
                    y2 = min(h, y2 + pad_y)

                    face = enhanced_frame[y1:y2, x1:x2]

                    # Unique name (VERY IMPORTANT)
                    face_name = f"{category}_{video_file}_frame{frame_count}_face{i}.jpg"
                    face_path = os.path.join(dataset_path, face_name)

                    cv2.imwrite(face_path, face)

            frame_count += 1

        cap.release()

print("\n✅ Dataset creation completed!")