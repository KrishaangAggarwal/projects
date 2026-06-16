# Speech Emotion Recognition (SER)

## What This Project Does

This notebook builds a deep learning system that listens to audio clips of human speech and classifies the speaker's emotion into one of 8 categories: **neutral, calm, happy, sad, angry, fearful, disgust, and surprised**. It trains a 1D Convolutional Neural Network (CNN) on audio features extracted from four major speech-emotion datasets, then provides a function to predict emotion from any new `.wav` file.

## Architecture & How It Works

### Step 1 — Feature Extraction (MFCC)

Every audio file is loaded with `librosa` (3-second clips, 0.5s offset) and converted into **40 Mel-Frequency Cepstral Coefficients (MFCCs)**. MFCCs capture the spectral envelope of sound — essentially the "shape" of the frequency content that distinguishes different vocal tones. The 40 MFCC vectors across time are averaged into a single 40-dimensional feature vector per clip.

### Step 2 — Dataset Loading

Four publicly available datasets are loaded and labelled:

| Dataset | Source | Emotions Covered | Approx. Size |
|---------|--------|-----------------|--------------|
| **RAVDESS** | Ryerson Audio-Visual Database | 8 emotions | ~1,440 clips |
| **CREMA-D** | Crowd-sourced Emotional Multimodal Actors | 6 emotions | ~7,442 clips |
| **TESS** | Toronto Emotional Speech Set | 7 emotions | ~2,800 clips |
| **SAVEE** | Surrey Audio-Visual Expressed Emotion | 7 emotions | ~480 clips |

Each dataset uses a different file-naming convention to encode the emotion label — the notebook parses filenames accordingly.

### Step 3 — Preprocessing

- Labels are encoded with `LabelEncoder` (string → integer).
- Data is split 80/20 into train/test.
- Features are standardised with `StandardScaler` (zero mean, unit variance).
- Feature vectors are reshaped to `(samples, 40, 1)` for the Conv1D input.

### Step 4 — CNN Model

```
Conv1D(64, kernel=3, relu) → BatchNorm → MaxPool(2) → Dropout(0.2)
Conv1D(128, kernel=3, relu) → BatchNorm → MaxPool(2) → Dropout(0.2)
Conv1D(256, kernel=3, relu) → BatchNorm → MaxPool(2) → Dropout(0.2)
Flatten → Dense(256, relu) → BatchNorm → Dropout(0.3) → Dense(8, softmax)
```

The model uses `sparse_categorical_crossentropy` loss, the Adam optimiser, `EarlyStopping` (patience=10), and `ReduceLROnPlateau` (halves LR after 5 stagnant epochs).

### Step 5 — Evaluation & Inference

After training, it prints a full classification report, plots a confusion matrix heatmap, plots training/validation accuracy and loss curves, and saves the model as `multi_dataset_speech_emotion_model.h5`. A `predict_emotion()` function takes any `.wav` file path and returns the predicted emotion string.

## How to Run It

### Prerequisites

```bash
pip install numpy pandas librosa tensorflow scikit-learn matplotlib seaborn
```

### On Kaggle (Recommended)

1. Create a new Kaggle notebook.
2. Add these datasets via "Add Data":
   - `uwrfkaggler/ravdess-emotional-speech-audio`
   - `ejlok1/cremad`
   - `ejlok1/toronto-emotional-speech-set-tess`
   - `ejlok1/surrey-audiovisual-expressed-emotion-savee`
3. Upload/paste the notebook and run all cells.
4. Training takes ~10-15 minutes on Kaggle GPU.

### Locally

1. Download all four datasets and update the directory paths in the `load_all_data()` function:
   - `ravdess` → path to RAVDESS audio folders
   - `Crema` → path to CREMA-D AudioWAV folder
   - `Tess` → path to TESS data folder
   - `Savee` → path to SAVEE ALL folder
2. Run the notebook end-to-end.
3. Use the saved model:

```python
from tensorflow.keras.models import load_model
model = load_model('multi_dataset_speech_emotion_model.h5')
emotion = predict_emotion('/path/to/your/audio.wav')
print(f"Detected emotion: {emotion}")
```

## Key Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `librosa` | ≥0.9 | Audio loading & MFCC extraction |
| `tensorflow` | ≥2.10 | CNN model training |
| `scikit-learn` | ≥1.0 | Train/test split, scaling, metrics |
| `matplotlib` / `seaborn` | — | Visualisation |

## Output Files

- `multi_dataset_speech_emotion_model.h5` — Trained Keras model
- Confusion matrix plot (inline)
- Training history plots (inline)

## Limitations & Notes

- MFCC averaging across time loses temporal dynamics — an LSTM or attention layer could improve this.
- The 3-second clip window may truncate longer utterances.
- Class imbalance across datasets (CREMA-D is much larger) could bias the model.
- The `predict_emotion()` function requires the `scaler` and `le` (LabelEncoder) objects from the training session to be in memory — they are not persisted to disk.
