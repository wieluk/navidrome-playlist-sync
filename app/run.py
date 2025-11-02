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


userInputs = UserInputs(
    navidrome_base_url=os.getenv("NAVIDROME_BASE_URL"),
    navidrome_port=int(os.getenv("NAVIDROME_PORT", "4533")),
    navidrome_username=os.getenv("NAVIDROME_USERNAME"),
    navidrome_password=os.getenv("NAVIDROME_PASSWORD"),
    navidrome_legacy_auth=_env_flag("NAVIDROME_LEGACY_AUTH", "0"),
    write_missing_as_csv=_env_flag("WRITE_MISSING_AS_CSV", "0"),
    append_service_suffix=_env_flag("APPEND_SERVICE_SUFFIX", "1"),
    add_playlist_poster=_env_flag("ADD_PLAYLIST_POSTER", "0"),
    add_playlist_description=_env_flag("ADD_PLAYLIST_DESCRIPTION", "1"),
    append_instead_of_sync=_env_flag("APPEND_INSTEAD_OF_SYNC", "0"),
    wait_seconds=int(os.getenv("SECONDS_TO_WAIT", "86400")),
    spotipy_client_id=os.getenv("SPOTIFY_CLIENT_ID"),
    spotipy_client_secret=os.getenv("SPOTIFY_CLIENT_SECRET"),
    spotify_user_id=os.getenv("SPOTIFY_USER_ID"),
)

while True:
    logger.info("Starting playlist sync cycle")
    logger.debug(
        "Configured options: append_suffix=%s append_instead_of_sync=%s "
        "write_missing_as_csv=%s add_description=%s add_poster=%s wait_seconds=%s",
        userInputs.append_service_suffix,
        userInputs.append_instead_of_sync,
        userInputs.write_missing_as_csv,
        userInputs.add_playlist_description,
        userInputs.add_playlist_poster,
        userInputs.wait_seconds,
    )

    if not (
        userInputs.navidrome_base_url
        and userInputs.navidrome_username
        and userInputs.navidrome_password
    ):
        logger.error("Missing Navidrome configuration; stopping sync loop")
        break

    try:
        navidrome = Connection(
            baseUrl=userInputs.navidrome_base_url,
            port=userInputs.navidrome_port,
            username=userInputs.navidrome_username,
            password=userInputs.navidrome_password,
            legacyAuth=userInputs.navidrome_legacy_auth,
        )
        if hasattr(navidrome, "ping"):
            navidrome.ping()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to connect to Navidrome: %s", exc)
        break

    logger.info("Starting Spotify playlist sync")

    spotify_client = None
    if (
        userInputs.spotipy_client_id
        and userInputs.spotipy_client_secret
        and userInputs.spotify_user_id
    ):
        try:
            spotify_client = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    userInputs.spotipy_client_id,
                    userInputs.spotipy_client_secret,
                )
            )
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "Spotify authorization error, skipping Spotify sync: %s",
                exc,
            )
    else:
        logger.info(
            "Missing one or more Spotify authorization variables, skipping"
            " Spotify sync",
        )

    if spotify_client is not None:
        spotify_playlist_sync(spotify_client, navidrome, userInputs)

    logger.info("Spotify playlist sync complete")

    logger.info("All playlist sync tasks complete")
    logger.info("Sleeping for %s seconds", userInputs.wait_seconds)

    time.sleep(userInputs.wait_seconds)
