from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scroll_review_tooling.operator_doctor import build_doctor_payload, write_doctor_outputs


def main() -> None:
    parser = argparse.ArgumentParser(description="Check whether the local no-claim operator can run on this machine.")
    parser.add_argument("--session", default="demo/session_manifest.json")
    parser.add_argument("--out-json", default="demo/out/operator_doctor.json")
    parser.add_argument("--out-md", default="demo/out/operator_doctor.md")
    parser.add_argument("--out-html", default="demo/out/operator_doctor.html")
    args = parser.parse_args()

    payload = build_doctor_payload(ROOT, Path(args.session))
    write_doctor_outputs(
        payload,
        out_json=ROOT / args.out_json,
        out_md=ROOT / args.out_md,
        out_html=ROOT / args.out_html,
    )
    print(json.dumps(payload, indent=2))
    if not payload.get("status_ok"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
