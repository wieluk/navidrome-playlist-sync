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
    logging.info("Starting playlist sync")

    if not (
        userInputs.navidrome_base_url
        and userInputs.navidrome_username
        and userInputs.navidrome_password
    ):
        logging.error("Missing Navidrome configuration; stopping sync loop")
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
        logging.error("Failed to connect to Navidrome: %s", exc)
        break

    logging.info("Starting Spotify playlist sync")

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
            logging.info(
                "Spotify authorization error, skipping Spotify sync: %s",
                exc,
            )
    else:
        logging.info(
            "Missing one or more Spotify authorization variables, skipping"
            " Spotify sync",
        )

    if spotify_client is not None:
        spotify_playlist_sync(spotify_client, navidrome, userInputs)

    logging.info("Spotify playlist sync complete")

    logging.info("All playlist sync tasks complete")
    logging.info("Sleeping for %s seconds", userInputs.wait_seconds)

    time.sleep(userInputs.wait_seconds)
