import argparse
import hashlib
import shutil
import urllib.request
from pathlib import Path

MODNET_URL = (
    "https://github.com/yakhyo/modnet/releases/download/weights/"
    "modnet_photographic.onnx"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download open-source inference models")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("server/models/modnet_photographic.onnx"),
    )
    parser.add_argument("--sha256", default="", help="Optional expected SHA-256")
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".download")
    request = urllib.request.Request(MODNET_URL, headers={"User-Agent": "wechat-image-tools"})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            with temporary.open("wb") as target:
                shutil.copyfileobj(response, target)
        digest = sha256(temporary)
        if args.sha256 and digest.lower() != args.sha256.lower():
            raise RuntimeError("Downloaded model SHA-256 does not match")
        temporary.replace(args.output)
        print(f"Saved: {args.output}")
        print(f"SHA256: {digest}")
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    main()

