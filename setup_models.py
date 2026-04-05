from __future__ import annotations

import os
import sys


def _check_ollama() -> None:
    try:
        import requests
    except ImportError:
        print("WARNING: requests not installed. Skipping Ollama connectivity check.")
        return

    base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = os.environ.get("OLLAMA_MODEL", "gpt-oss:20b")

    print(f"Checking Ollama connectivity at {base_url} ...")

    try:
        resp = requests.get(f"{base_url}/api/tags", timeout=5)
        resp.raise_for_status()
    except requests.exceptions.ConnectionError:
        print(f"WARNING: Cannot connect to Ollama at {base_url}.")
        print("  Start Ollama first: ollama serve")
        print("  Signal explanations will use template fallback.")
        return
    except Exception as exc:
        print(f"WARNING: Ollama check failed: {exc}")
        print("  Signal explanations will use template fallback.")
        return

    models = resp.json().get("models", [])
    model_names = [m.get("name", "") for m in models]

    for name in model_names:
        if model_name in name or name.startswith(model_name.split(":")[0]):
            print(f"OK: Ollama model '{model_name}' is available.")
            return

    print(f"WARNING: Model '{model_name}' not found in Ollama.")
    print(f"  Available models: {model_names}")
    print(f"  Pull it with: ollama pull {model_name}")
    print("  Signal explanations will use template fallback until model is pulled.")


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
    else:
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

    print()
    _check_ollama()


if __name__ == "__main__":
    main()
