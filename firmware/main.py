"""Entry point for the ETH Arcade handheld launcher and BOX RUN."""

from display_setup import ensure_system_pygame
from envfile import load_env_file

# Before the display bootstrap, which may re-exec with this environment.
load_env_file()
ensure_system_pygame()

import keeper  # noqa: E402
from app import App  # noqa: E402


def main() -> None:
    keeper.start()    # names and scores the players; the game runs with or without it
    App().run()


if __name__ == "__main__":
    main()
