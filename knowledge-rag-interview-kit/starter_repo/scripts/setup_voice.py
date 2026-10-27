"""Download once; /voice/transcribe never downloads a model or sends audio out."""
import argparse
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", choices=["tiny", "base", "small", "medium", "large-v3"], default="base")
    parser.add_argument("--output", default=os.getenv("VOICE_MODEL_PATH", "var/models/whisper-base"))
    args = parser.parse_args()
    try:
        from faster_whisper import WhisperModel
        from huggingface_hub import snapshot_download
    except ImportError:
        raise SystemExit("Install first: .venv/bin/python -m pip install -e '.[voice]'")
    target = Path(args.output)
    target.mkdir(parents=True, exist_ok=True)
    print(f"Downloading multilingual Whisper {args.model} to {target}…", flush=True)
    try:
        snapshot_download(f"Systran/faster-whisper-{args.model}", local_dir=str(target),
                          allow_patterns=["config.json", "preprocessor_config.json", "model.bin",
                                          "tokenizer.json", "vocabulary.*"])
    except Exception as exc:
        raise SystemExit(f"Model download failed ({type(exc).__name__}). Check network access to Hugging Face, "
                         "or set HF_ENDPOINT to a trusted mirror and retry. Partial downloads can resume.") from exc
    WhisperModel(str(target), device="cpu", compute_type="int8", local_files_only=True)
    print(f"Speech model ready. VOICE_MODEL_PATH={target}", flush=True)
    print("For summaries: ollama pull qwen2.5:3b. Then start/restart the API and open /#voice.")


if __name__ == "__main__":
    main()
