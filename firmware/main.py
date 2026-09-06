"""Entry point for the Playdate-like home launcher."""

from display_setup import ensure_system_pygame

ensure_system_pygame()

from app import App  # noqa: E402


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
