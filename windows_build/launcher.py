from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    import sys
    if not getattr(sys, "frozen", False):
        from pathlib import Path
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

        raise SystemExit(main(sys.argv[2:]))
    from main import main

    raise SystemExit(main())
