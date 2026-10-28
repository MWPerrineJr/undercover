"""Start a capped queue run, or one named claim, through the backend API."""

import argparse
import sys

import httpx

from agent import api


def main(argv: list[str] | None = None) -> int:
    """Ask the backend to start a run and print what it said."""
    parser = argparse.ArgumentParser(prog="agent")
    choice = parser.add_mutually_exclusive_group(required=True)
    choice.add_argument("--cap", type=int, help="work at most this many claims")
    choice.add_argument("--claim", help="work one named claim")
    args = parser.parse_args(argv)
    try:
        with api.backend() as client:
            response = (
                client.post("/api/queue/run", json={"cap": args.cap})
                if args.cap
                else client.post(f"/api/claims/{args.claim}/run")
            )
    except httpx.HTTPError as error:
        print(f"The backend is not reachable: {error}")
        return 1
    print(response.text)
    return 0 if response.is_success else 1


if __name__ == "__main__":
    sys.exit(main())
