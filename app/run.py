import logging
import os
import time

import spotipy
from libsonic.connection import Connection
from spotipy.oauth2 import SpotifyClientCredentials

from utils.helperClasses import UserInputs
from utils.spotify import spotify_playlist_sync


def _env_flag(name: str, default: str = "0") -> bool:
    value = os.getenv(name, default)
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        logging.getLogger(__name__).warning(
            "Invalid integer for %s=%s; using default %s", name, value, default
        )
        return default


def _env_float(name: str, default: float, minimum: float | None = None, maximum: float | None = None) -> float:
    value = os.getenv(name)
    if value is None:
        return default
    try:
        result = float(value)
    except ValueError:
        logging.getLogger(__name__).warning(
            "Invalid float for %s=%s; using default %.2f", name, value, default
        )
        return default

    if minimum is not None and result < minimum:
        logging.getLogger(__name__).warning(
            "%s below minimum %.2f; using %.2f", name, minimum, default
        )
        return default
    if maximum is not None and result > maximum:
        logging.getLogger(__name__).warning(
            "%s above maximum %.2f; using %.2f", name, maximum, default
        )
        return default

    return result


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL")
    verbose_requested = _env_flag("VERBOSE_LOGGING", "0")

    if level_name:
        level = getattr(logging, level_name.upper(), logging.INFO)
    elif verbose_requested:
        level = logging.DEBUG
    else:
        level = logging.INFO

    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    # Reduce third-party chatter unless explicitly requested via LOG_LEVEL
    if not level_name and not verbose_requested:
        logging.getLogger("spotipy").setLevel(logging.WARNING)
        logging.getLogger("libsonic").setLevel(logging.WARNING)


_configure_logging()

logger = logging.getLogger(__name__)

wait_seconds = max(_env_int("SECONDS_TO_WAIT", 86400), 0)
match_threshold = _env_float("NAVIDROME_MATCH_THRESHOLD", 0.6, 0.0, 1.0)


userInputs = UserInputs(
    navidrome_base_url=os.getenv("NAVIDROME_BASE_URL"),
    navidrome_port=_env_int("NAVIDROME_PORT", 4533),
    navidrome_username=os.getenv("NAVIDROME_USERNAME"),
    navidrome_password=os.getenv("NAVIDROME_PASSWORD"),
    navidrome_legacy_auth=_env_flag("NAVIDROME_LEGACY_AUTH", "0"),
    write_missing_as_csv=_env_flag("WRITE_MISSING_AS_CSV", "0"),
    append_service_suffix=_env_flag("APPEND_SERVICE_SUFFIX", "1"),
    add_playlist_description=_env_flag("ADD_PLAYLIST_DESCRIPTION", "1"),
    append_instead_of_sync=_env_flag("APPEND_INSTEAD_OF_SYNC", "0"),
    wait_seconds=wait_seconds,
    match_confidence_threshold=match_threshold,
    spotipy_client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    spotipy_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    spotify_user_id=os.getenv("SPOTIFY_USER_ID"),
)


def _has_required_navidrome_inputs(inputs: UserInputs) -> bool:
    missing = [
        name
        for name, value in (
            ("NAVIDROME_BASE_URL", inputs.navidrome_base_url),
            ("NAVIDROME_USERNAME", inputs.navidrome_username),
            ("NAVIDROME_PASSWORD", inputs.navidrome_password),
        )
        if not value
    ]

    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        return False
    return True



def run_sync_cycle(inputs: UserInputs) -> bool:
    if not _has_required_navidrome_inputs(inputs):
        return False

    logger.info("Starting playlist sync cycle")
    logger.debug(
        "Configured options: append_suffix=%s append_instead_of_sync=%s "
        "write_missing_as_csv=%s add_description=%s wait_seconds=%s match_threshold=%.2f",
        inputs.append_service_suffix,
        inputs.append_instead_of_sync,
        inputs.write_missing_as_csv,
        inputs.add_playlist_description,
        inputs.wait_seconds,
        inputs.match_confidence_threshold,
    )

    cycle_start = time.monotonic()

    try:
        navidrome = Connection(
            baseUrl=inputs.navidrome_base_url,
            port=inputs.navidrome_port,
            username=inputs.navidrome_username,
            password=inputs.navidrome_password,
            legacyAuth=inputs.navidrome_legacy_auth,
        )
        if hasattr(navidrome, "ping"):
            navidrome.ping()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to connect to Navidrome: %s", exc)
        return False

    logger.info("Starting Spotify playlist sync")

    spotify_client = None
    if (
        inputs.spotipy_client_id
        and inputs.spotipy_client_secret
        and inputs.spotify_user_id
    ):
        try:
            spotify_client = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    inputs.spotipy_client_id,
                    inputs.spotipy_client_secret,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "Spotify authorization error, skipping Spotify sync: %s",
                exc,
            )
    else:
        logger.info(
            "Missing one or more Spotify authorization variables, skipping Spotify sync",
        )

    if spotify_client is not None:
        try:
            spotify_playlist_sync(spotify_client, navidrome, inputs)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Spotify playlist sync failed: %s", exc)

    logger.info("Spotify playlist sync complete")
    logger.info(
        "Playlist sync cycle finished in %.2f seconds",
        time.monotonic() - cycle_start,
    )
    return True


def main() -> None:
    run_forever = not _env_flag("RUN_ONCE", "0")

    while True:
        should_continue = run_sync_cycle(userInputs)
        if not should_continue:
            break

        if not run_forever:
            break

        if userInputs.wait_seconds <= 0:
            logger.info("RUN_ONCE disabled and wait_seconds=0, restarting immediately")
            continue

        logger.info("Sleeping for %s seconds", userInputs.wait_seconds)
        time.sleep(userInputs.wait_seconds)


if __name__ == "__main__":
    main()
