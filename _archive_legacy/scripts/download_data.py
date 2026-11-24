
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import argparse

from core.config import get_settings
from data.akshare_client import AkShareClientV391
from data.price_loader import normalize_daily


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--code", default="300394")
    parser.add_argument("--start", default="20200101")
    parser.add_argument("--end", default="20261231")
    args = parser.parse_args()
    settings = get_settings()
    client = AkShareClientV391(settings.cache_dir)
    raw = client.get_daily(args.code, args.start, args.end)
    df = normalize_daily(raw, args.code)
    print(df.tail(20).to_string(index=False))


if __name__ == "__main__":
    main()
