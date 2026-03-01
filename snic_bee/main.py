def _resolve_main():
    try:
        from snic_bee.bee import main as _main
        return _main
    except Exception:
        from bee import main as _main
        return _main


def main():
    _resolve_main()()


if __name__ == "__main__":
    main()
