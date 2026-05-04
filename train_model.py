import torch
import torch.nn as nn
import torch.optim as optim
from torchvision import datasets, transforms, models
from torch.utils.data import DataLoader
import os

# -----------------------------
# 1. Device Configuration
# -----------------------------
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# -----------------------------
# 2. Data Transformations
# -----------------------------
transform = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.ToTensor(),
    transforms.Normalize([0.5], [0.5])
])

# -----------------------------
# 3. Load Dataset
# -----------------------------
dataset = datasets.ImageFolder("dataset", transform=transform)

# Split dataset
train_size = int(0.8 * len(dataset))
val_size = len(dataset) - train_size

train_dataset, val_dataset = torch.utils.data.random_split(dataset, [train_size, val_size])

train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
val_loader = DataLoader(val_dataset, batch_size=16)

print("Classes:", dataset.classes)

# -----------------------------
# 4. Load Pretrained Model
# -----------------------------
from torchvision.models import ResNet18_Weights

model = models.resnet18(weights=ResNet18_Weights.DEFAULT)

# Freeze layers (important)
for param in model.parameters():
    param.requires_grad = False

# Modify final layer
model.fc = nn.Sequential(
    nn.Linear(model.fc.in_features, 1),
    nn.Sigmoid()
)

model = model.to(device)

# -----------------------------
# 5. Loss & Optimizer
# -----------------------------
criterion = nn.BCELoss()
optimizer = optim.Adam(model.fc.parameters(), lr=0.001)

# -----------------------------
# 6. Training Loop
# -----------------------------
epochs = 5

for epoch in range(epochs):
    model.train()
    running_loss = 0

    for images, labels in train_loader:
        images = images.to(device)
        labels = labels.float().unsqueeze(1).to(device)

        outputs = model(images)
        loss = criterion(outputs, labels)

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        running_loss += loss.item()

    print(f"Epoch [{epoch+1}/{epochs}], Loss: {running_loss:.4f}")

# -----------------------------
# 7. Validation
# -----------------------------
model.eval()
correct = 0
total = 0

with torch.no_grad():
    for images, labels in val_loader:
        images = images.to(device)
        labels = labels.to(device)

        outputs = model(images)
        predicted = (outputs > 0.5).int()

        correct += (predicted.squeeze() == labels).sum().item()
        total += labels.size(0)

accuracy = 100 * correct / total
print(f"Validation Accuracy: {accuracy:.2f}%")

# -----------------------------
# 8. Save Model
# -----------------------------
torch.save(model.state_dict(), "deepfake_model.pth")

print("✅ Model saved successfully!")