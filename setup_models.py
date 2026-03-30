from __future__ import annotations

import os
import sys


def main() -> None:
    try:
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
    except ImportError:
        print("ERROR: transformers not installed. Run: pip install transformers torch")
        sys.exit(1)

    model_path = os.environ.get("FINBERT_MODEL_PATH", "models/finbert")
    model_name = "ProsusAI/finbert"

    config_file = os.path.join(model_path, "config.json")
    if os.path.exists(config_file):
        print(
            f"Model already exists at {model_path} (config.json found). Skipping download."
        )
        return

    os.makedirs(model_path, exist_ok=True)

    print(f"Downloading {model_name} to {model_path} ...")
    print("This may take a few minutes (~440 MB).")

    try:
        print("  Downloading model weights ...")
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.save_pretrained(model_path)

        print("  Downloading tokenizer ...")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        tokenizer.save_pretrained(model_path)

        print(f"SUCCESS: FinBERT model saved to {model_path}")
        print(f"  Files: {os.listdir(model_path)}")
    except Exception as exc:
        print(f"ERROR: Failed to download model: {exc}")
        print("Check your internet connection and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
