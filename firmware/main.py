"""Entry point for the TICK handheld launcher and BOX RUN."""

from display_setup import ensure_system_pygame
from envfile import load_env_file

# Before the display bootstrap, which may re-exec with this environment.
load_env_file()
ensure_system_pygame()

from app import App  # noqa: E402


def main() -> None:
    App().run()


if __name__ == "__main__":
    main()
