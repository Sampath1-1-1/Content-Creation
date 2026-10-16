"""Kids Video Studio — one command runs the whole pipeline.

Examples
  python studio.py --topic "numbers 1 to 10"            # run / resume everything
  python studio.py --topic "numbers 1 to 10" --preview  # fast low-res test run
  python studio.py --topic "numbers 1 to 10" --only-stage 1
  python studio.py --topic "numbers 1 to 10" --from-stage 4 --force
  python studio.py doctor [--online]                    # check your setup
  python studio.py status --topic "numbers 1 to 10"     # what's done so far
  python studio.py quota                                # free quota used today
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Windows consoles default to an old code page; make emoji/✓ print safely.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

from studio.core.config import load_config, load_env  # noqa: E402
from studio.core.errors import StudioError, friendly_from_exception  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="studio.py",
        description="Free, copyright-safe kids' educational video studio.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Examples", 1)[1] if __doc__ else "",
    )
    p.add_argument("command", nargs="?", default="run", choices=["run", "doctor", "status", "quota"])
    p.add_argument("--topic", help='e.g. "numbers 1 to 10"')
    p.add_argument("--preview", action="store_true", help="fast, low-resolution test mode")
    p.add_argument("--from-stage", type=int, default=1, metavar="N", help="start at stage N")
    p.add_argument("--only-stage", type=int, metavar="N", help="run only stage N")
    p.add_argument("--force", action="store_true", help="redo stages even if already done")
    p.add_argument("--fixture", metavar="FILE",
                   help="Stage 1 offline demo: use saved sample data instead of the YouTube API")
    p.add_argument("--online", action="store_true", help="doctor: also test your API keys")
    p.add_argument("--config", metavar="FILE", help="use a different config.yaml")
    p.add_argument("--verbose", "-v", action="store_true", help="show debug details")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    load_env()
    try:
        cfg = load_config(args.config, mode="preview" if args.preview else "final")

        if args.command == "doctor":
            from studio.core.doctor import run_doctor
            return run_doctor(cfg, online=args.online)

        from studio.core.context import RunContext, build_quota
        from studio.core.log import setup_logging
        from studio.core.manifest import Manifest
        from studio.core.paths import slugify

        cache_root = cfg.root_path("project.cache_dir")
        cache_root.mkdir(parents=True, exist_ok=True)
        quota = build_quota(cfg, cache_root)

        if args.command == "quota":
            print(quota.summary())
            return 0

        if not args.topic:
            raise StudioError("No topic given.", fix='Add --topic "numbers 1 to 10"')

        slug = slugify(args.topic)
        if args.preview:
            slug += "__preview"
        if args.fixture:
            slug += "__demo"  # offline demo data never mixes with real results
        project_dir = cfg.root_path("project.projects_dir") / slug
        manifest = Manifest(project_dir)

        if args.command == "status":
            print(json.dumps(manifest.data, indent=2, ensure_ascii=False))
            return 0

        log = setup_logging(project_dir / "logs" / "run.log", verbose=args.verbose)
        log.info(f"🎬 Topic: {args.topic}   Mode: {cfg['mode']}   Folder: {project_dir}")

        ctx = RunContext(cfg=cfg, topic=args.topic, slug=slug, project_dir=project_dir,
                         cache_root=cache_root, manifest=manifest, quota=quota,
                         options={"fixture": args.fixture, "force": args.force})

        from studio.core.pipeline import run_pipeline
        run_pipeline(ctx, from_stage=args.from_stage, only_stage=args.only_stage, force=args.force)
        log.info("\n" + quota.summary())
        return 0
    except BaseException as exc:  # noqa: BLE001 - top-level friendly handler
        if isinstance(exc, SystemExit):
            raise
        print(friendly_from_exception(exc), file=sys.stderr)
        return 130 if isinstance(exc, KeyboardInterrupt) else 1


if __name__ == "__main__":
    sys.exit(main())
