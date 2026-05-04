import cv2
import torch
import numpy as np
from torchvision import transforms, models

# -----------------------------
# 1. Load Model
# -----------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

from torchvision.models import ResNet18_Weights
model = models.resnet18(weights=ResNet18_Weights.DEFAULT)

model.fc = torch.nn.Sequential(
    torch.nn.Linear(model.fc.in_features, 1),
    torch.nn.Sigmoid()
)

model.load_state_dict(torch.load("deepfake_model.pth", map_location=device))
model = model.to(device)
model.eval()

print("✅ Model Loaded")

# -----------------------------
# 2. Transform
# -----------------------------
transform = transforms.Compose([
    transforms.ToPILImage(),
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5,0.5,0.5], [0.5,0.5,0.5])
])

# -----------------------------
# 3. Face Detection Model
# -----------------------------
prototxt_path = "deploy.prototxt.txt"
model_path = "res10_300x300_ssd_iter_140000.caffemodel"

net = cv2.dnn.readNetFromCaffe(prototxt_path, model_path)

def detect_faces(frame):
    (h, w) = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(frame, 1.0, (300, 300),
                                 (104.0, 177.0, 123.0))
    net.setInput(blob)
    detections = net.forward()

    faces = []
    for i in range(detections.shape[2]):
        confidence = detections[0,0,i,2]
        if confidence > 0.5:
            box = detections[0,0,i,3:7] * np.array([w,h,w,h])
            (x1,y1,x2,y2) = box.astype("int")
            faces.append((x1,y1,x2,y2))
    return faces

# -----------------------------
# 4. Predict Face
# -----------------------------
def predict_face(face):
    face = transform(face).unsqueeze(0).to(device)
    with torch.no_grad():
        output = model(face)
    return output.item()  # REAL probability

# -----------------------------
# 5. Video Input
# -----------------------------
video_path = input("Enter video path: ")
cap = cv2.VideoCapture(video_path)

frame_count = 0
interval = 6

scores = []

# -----------------------------
# 6. Process Video
# -----------------------------
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

            print(f"Frame {frame_count} → Real Score: {score:.2f}")

    frame_count += 1

cap.release()

# -----------------------------
# 7. TEMPORAL ANALYSIS
# -----------------------------
if len(scores) == 0:
    print("❌ No faces detected")
    exit()

scores = np.array(scores)

avg_score = np.mean(scores)
fake_ratio = np.sum(scores < 0.5) / len(scores)
variance = np.var(scores)

gradients = np.abs(np.diff(scores))
avg_gradient = np.mean(gradients)

# -----------------------------
# 8. SEGMENT-BASED ANALYSIS 🔥
# -----------------------------
window = 5
segments = [scores[i:i+window] for i in range(0, len(scores), window)]

fake_segments = 0

for seg in segments:
    seg = np.array(seg)
    
    seg_fake_ratio = np.sum(seg < 0.5) / len(seg)
    
    if seg_fake_ratio > 0.6:
        fake_segments += 1

# -----------------------------
# 9. FUSION SCORE
# -----------------------------
final_score = (
    0.4 * avg_score +
    0.2 * (1 - fake_ratio) +
    0.2 * (1 - variance) +
    0.2 * (1 - avg_gradient)
)

# -----------------------------
# 10. FINAL DECISION 🔥
# -----------------------------
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

# -----------------------------
# 11. OUTPUT
# -----------------------------
print("\n==========================")
print(f"Average Score: {avg_score:.2f}")
print(f"Fake Ratio: {fake_ratio:.2f}")
print(f"Variance: {variance:.4f}")
print(f"Gradient: {avg_gradient:.4f}")
print(f"Fake Segments: {fake_segments}/{len(segments)}")
print(f"Fusion Score: {final_score:.2f}")

print(f"\n🚨 FINAL RESULT: {decision} VIDEO")