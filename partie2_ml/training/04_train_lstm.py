"""
TeleSight AI — Train LSTM with Attention (time-series anomaly prediction)
Input: sequences of 20 time steps × 4 features per cell_id
Output: binary anomaly label for the next time step
"""

import pickle
import sys
import importlib.util
from pathlib import Path
import numpy as np
import pandas as pd
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset, random_split

_spec = importlib.util.spec_from_file_location(
    "prepare_features", Path(__file__).parent / "01_prepare_features.py"
)
_mod = importlib.util.module_from_spec(_spec)
sys.modules["prepare_features"] = _mod
_spec.loader.exec_module(_mod)
load_and_engineer = _mod.load_and_engineer
MODELS_DIR        = _mod.MODELS_DIR

MODELS_DIR.mkdir(exist_ok=True)

# ─── Hyperparameters ─────────────────────────────────────────────────────────
SEQ_LEN     = 20
FEATURES    = ["sinr", "latency", "throughput_dl", "packet_loss"]   # 4 features
HIDDEN_SIZE = 64
N_LAYERS    = 2
DROPOUT     = 0.2
BATCH_SIZE  = 128
N_EPOCHS    = 30
LR          = 1e-3
DEVICE      = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ─── Model ───────────────────────────────────────────────────────────────────
class AttentionLayer(nn.Module):
    def __init__(self, hidden_size: int):
        super().__init__()
        self.attention = nn.Linear(hidden_size, 1)

    def forward(self, lstm_out):
        # lstm_out: (batch, seq_len, hidden)
        weights = torch.softmax(self.attention(lstm_out), dim=1)  # (batch, seq_len, 1)
        context = (weights * lstm_out).sum(dim=1)                 # (batch, hidden)
        return context


class LSTMWithAttention(nn.Module):
    def __init__(self, n_features, hidden_size, n_layers, dropout):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=n_features,
            hidden_size=hidden_size,
            num_layers=n_layers,
            batch_first=True,
            dropout=dropout if n_layers > 1 else 0.0,
        )
        self.attention   = AttentionLayer(hidden_size)
        self.dropout     = nn.Dropout(dropout)
        self.classifier  = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(32, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        lstm_out, _ = self.lstm(x)           # (batch, seq_len, hidden)
        context     = self.attention(lstm_out)  # (batch, hidden)
        context     = self.dropout(context)
        out         = self.classifier(context)  # (batch, 1)
        return out.squeeze(1)


# ─── Data preparation ────────────────────────────────────────────────────────
def build_sequences(df: pd.DataFrame):
    """Build (X, y) sequences per cell, concatenate across all cells."""
    Xs, ys = [], []

    # Compute normalization stats
    means = df[FEATURES].mean().values.astype(np.float32)
    stds  = df[FEATURES].std().values.astype(np.float32) + 1e-8

    for cell_id, group in df.groupby("cell_id"):
        group   = group.sort_values("timestamp").reset_index(drop=True)
        vals    = group[FEATURES].fillna(0).values.astype(np.float32)
        labels  = group["is_anomaly"].values.astype(np.float32)

        vals = (vals - means) / stds

        for i in range(SEQ_LEN, len(vals)):
            Xs.append(vals[i - SEQ_LEN : i])
            ys.append(labels[i])

    if not Xs:
        raise ValueError("No sequences generated — dataset too small?")

    X_arr = np.array(Xs, dtype=np.float32)
    y_arr = np.array(ys, dtype=np.float32)
    print(f"  ✓ Built {len(X_arr)} sequences (shape: {X_arr.shape})")
    print(f"  ✓ Anomaly rate in sequences: {y_arr.mean()*100:.1f}%")
    return X_arr, y_arr, means, stds


def train():
    print(f"=== TeleSight AI — LSTM Training (device: {DEVICE}) ===\n")

    df = load_and_engineer()
    X, y, means, stds = build_sequences(df)

    # Save normalization params
    np.save(MODELS_DIR / "ts_means.npy", means)
    np.save(MODELS_DIR / "ts_stds.npy",  stds)

    # Datasets
    dataset  = TensorDataset(torch.from_numpy(X), torch.from_numpy(y))
    n_val    = int(0.2 * len(dataset))
    n_train  = len(dataset) - n_val
    train_ds, val_ds = random_split(dataset, [n_train, n_val])

    train_loader = DataLoader(train_ds, batch_size=BATCH_SIZE, shuffle=True,  num_workers=0)
    val_loader   = DataLoader(val_ds,   batch_size=BATCH_SIZE, shuffle=False, num_workers=0)

    # Model
    model = LSTMWithAttention(
        n_features=len(FEATURES),
        hidden_size=HIDDEN_SIZE,
        n_layers=N_LAYERS,
        dropout=DROPOUT,
    ).to(DEVICE)

    n_pos = int(y.sum())
    n_neg = len(y) - n_pos
    pos_weight = torch.tensor([n_neg / (n_pos + 1e-6)]).to(DEVICE)
    criterion  = nn.BCEWithLogitsLoss(pos_weight=pos_weight)

    # Replace sigmoid in classifier for BCEWithLogitsLoss
    model.classifier[-1] = nn.Identity()

    optimizer  = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-4)
    scheduler  = torch.optim.lr_scheduler.ReduceLROnPlateau(optimizer, patience=3, factor=0.5)

    best_val_loss = float("inf")
    best_path     = MODELS_DIR / "lstm_best.pt"

    print(f"\n[3/4] Training ({N_EPOCHS} epochs)...")
    for epoch in range(1, N_EPOCHS + 1):
        # ── Train ──
        model.train()
        train_loss = 0.0
        for xb, yb in train_loader:
            xb, yb = xb.to(DEVICE), yb.to(DEVICE)
            optimizer.zero_grad()
            logits = model(xb)
            loss   = criterion(logits, yb)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            train_loss += loss.item() * len(xb)
        train_loss /= len(train_ds)

        # ── Validate ──
        model.eval()
        val_loss = 0.0
        correct  = 0
        with torch.no_grad():
            for xb, yb in val_loader:
                xb, yb = xb.to(DEVICE), yb.to(DEVICE)
                logits  = model(xb)
                loss    = criterion(logits, yb)
                val_loss += loss.item() * len(xb)
                preds    = (torch.sigmoid(logits) >= 0.5).float()
                correct += (preds == yb).sum().item()
        val_loss /= len(val_ds)
        val_acc   = correct / len(val_ds)

        scheduler.step(val_loss)
        print(f"  Epoch {epoch:3d}/{N_EPOCHS} | Train Loss: {train_loss:.4f} | Val Loss: {val_loss:.4f} | Val Acc: {val_acc:.3f}")

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            torch.save(model.state_dict(), best_path)
            print(f"  ✓ New best model saved (val_loss={best_val_loss:.4f})")

    # Save config
    lstm_config = {
        "n_features":  len(FEATURES),
        "hidden_size": HIDDEN_SIZE,
        "n_layers":    N_LAYERS,
        "dropout":     DROPOUT,
        "seq_len":     SEQ_LEN,
        "features":    FEATURES,
    }
    pickle.dump(lstm_config, open(MODELS_DIR / "lstm_config.pkl", "wb"))
    print(f"\n[4/4] ✓ LSTM training complete. Best val_loss: {best_val_loss:.4f}")
    print(f"  Saved: lstm_best.pt, lstm_config.pkl, ts_means.npy, ts_stds.npy")


if __name__ == "__main__":
    train()
