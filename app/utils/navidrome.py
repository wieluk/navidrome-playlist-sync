import csv
import logging
import pathlib
from difflib import SequenceMatcher
from typing import Iterable, List, Tuple

from libsonic.connection import Connection

from .helperClasses import Playlist, Track, UserInputs


logger = logging.getLogger(__name__)


def _write_csv(tracks: List[Track], name: str, path: str = "/data") -> None:
    """Write given tracks with given name as a csv."""
    data_folder = pathlib.Path(path)
    data_folder.mkdir(parents=True, exist_ok=True)
    file = data_folder / f"{name}.csv"

    logger.debug("Writing CSV with %s missing tracks at %s", len(tracks), file)

    with open(file, "w", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(Track.__annotations__.keys())
        for track in tracks:
            writer.writerow([track.title, track.artist, track.album, track.url])


def _delete_csv(name: str, path: str = "/data") -> None:
    """Delete file associated with given name."""
    file = pathlib.Path(path) / f"{name}.csv"
    if file.exists():
        logger.debug("Deleting CSV %s", file)
        file.unlink()


def _normalize(value: str | None) -> str:
    return value.lower().strip() if value else ""


def _sequence_score(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).quick_ratio()


def _score_candidate(candidate: dict, track: Track) -> float:
    title_score = _sequence_score(_normalize(candidate.get("title")), _normalize(track.title))
    artist_score = _sequence_score(_normalize(candidate.get("artist")), _normalize(track.artist))
    album_score = _sequence_score(_normalize(candidate.get("album")), _normalize(track.album))
    # Weight title highest, then artist, then album
    return (title_score * 0.6) + (artist_score * 0.3) + (album_score * 0.1)


def _ensure_iterable_songs(songs: Iterable | None) -> List[dict]:
    if songs is None:
        return []
    if isinstance(songs, list):
        return songs
    return [songs]


def _search_tracks(navidrome: Connection, track: Track, limit: int = 25) -> List[dict]:
    query_parts = [track.title, track.artist]
    query = " ".join(part for part in query_parts if part)
    if not query:
        return []

    logger.debug("Searching Navidrome for track '%s'", query)

    try:
        response = navidrome.search2(
            query=query,
            artistCount=0,
            albumCount=0,
            songCount=limit,
        )
    except Exception as exc:  # noqa: BLE001
        logger.info("Navidrome search failed for '%s': %s", track.title, exc)
        return []

    songs = response.get("searchResult2", {}).get("song")
    return _ensure_iterable_songs(songs)


def _pick_best_match(candidates: List[dict], track: Track) -> Tuple[dict | None, float]:
    best_candidate = None
    best_score = 0.0
    for candidate in candidates:
        score = _score_candidate(candidate, track)
        if score > best_score:
            best_candidate = candidate
            best_score = score
    return best_candidate, best_score


def _get_available_navidrome_tracks(
    navidrome: Connection, tracks: List[Track]
) -> Tuple[List[str], List[Track]]:
    available_ids: List[str] = []
    missing_tracks: List[Track] = []

    logger.debug("Resolving availability for %s tracks", len(tracks))

    for track in tracks:
        candidates = _search_tracks(navidrome, track)
        best_candidate, best_score = _pick_best_match(candidates, track)

        if best_candidate and best_score >= 0.6:
            track_id = best_candidate.get("id")
            if track_id:
                available_ids.append(str(track_id))
                if logger.isEnabledFor(logging.DEBUG):
                    logger.debug(
                        "Matched track '%s - %s' with Navidrome id %s (score=%.2f)",
                        track.title,
                        track.artist,
                        track_id,
                        best_score,
                    )
            else:
                missing_tracks.append(track)
        else:
            missing_tracks.append(track)
            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "No suitable Navidrome match for '%s - %s' (best score %.2f)",
                    track.title,
                    track.artist,
                    best_score,
                )

    return available_ids, missing_tracks


def _find_existing_playlist(navidrome: Connection, playlist_name: str) -> dict | None:
    try:
        response = navidrome.getPlaylists()
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch Navidrome playlists: %s", exc)
        return None

    playlists = response.get("playlists", {}).get("playlist")
    for item in _ensure_iterable_songs(playlists):
        if item.get("name") == playlist_name:
            return item
    return None


def _create_playlist(navidrome: Connection, playlist_name: str) -> str:
    logger.debug("Creating Navidrome playlist '%s'", playlist_name)
    response = navidrome.createPlaylist(name=playlist_name)
    playlist = response.get("playlist", {})
    playlist_id = playlist.get("id")
    if playlist_id is None:
        raise RuntimeError(
            f"Navidrome did not return an id for playlist '{playlist_name}'"
        )
    return str(playlist_id)


def _ensure_playlist_id(
    navidrome: Connection,
    playlist: Playlist,
    append: bool,
) -> str:
    existing = _find_existing_playlist(navidrome, playlist.name)
    if existing and not append:
        try:
            navidrome.deletePlaylist(pid=existing.get("id"))
            logger.info(
                "Reset existing Navidrome playlist '%s' before syncing",
                playlist.name,
            )
            existing = None
        except Exception as exc:  # noqa: BLE001
            raise RuntimeError(
                f"Failed to reset Navidrome playlist '{playlist.name}': {exc}"
            ) from exc

    if existing:
        return str(existing.get("id"))

    return _create_playlist(navidrome, playlist.name)


def _add_tracks(navidrome: Connection, playlist_id: str, track_ids: List[str]) -> None:
    if not track_ids:
        return

    logger.debug(
        "Adding %s tracks to Navidrome playlist id %s",
        len(track_ids),
        playlist_id,
    )

    try:
        navidrome.updatePlaylist(lid=playlist_id, songIdsToAdd=track_ids)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            f"Failed to add tracks {', '.join(track_ids)} to playlist {playlist_id}: {exc}"
        ) from exc


def update_or_create_navidrome_playlist(
    navidrome: Connection,
    playlist: Playlist,
    tracks: List[Track],
    userInputs: UserInputs,
) -> None:
    available_track_ids, missing_tracks = _get_available_navidrome_tracks(
        navidrome, tracks
    )

    logger.info(
        "Playlist '%s': %s tracks matched in Navidrome, %s missing",
        playlist.name,
        len(available_track_ids),
        len(missing_tracks),
    )

    if not available_track_ids:
        logger.info(
            "No songs for playlist %s were found on Navidrome, skipping",
            playlist.name,
        )
        if missing_tracks and userInputs.write_missing_as_csv:
            try:
                _write_csv(missing_tracks, playlist.name)
                logger.info("Missing tracks written to %s.csv", playlist.name)
            except Exception as exc:  # noqa: BLE001
                logger.info(
                    "Failed to write missing tracks for %s: %s",
                    playlist.name,
                    exc,
                )
        return

    try:
        playlist_id = _ensure_playlist_id(
            navidrome, playlist, userInputs.append_instead_of_sync
        )
    except RuntimeError as exc:
        logger.error(
            "Unable to prepare Navidrome playlist %s: %s", playlist.name, exc
        )
        return

    try:
        _add_tracks(navidrome, playlist_id, available_track_ids)
    except RuntimeError as exc:
        logger.error(
            "Failed to update Navidrome playlist %s: %s", playlist.name, exc
        )
        return

    if playlist.description and userInputs.add_playlist_description:
        try:
            navidrome.updatePlaylist(lid=playlist_id, comment=playlist.description)
        except Exception as exc:  # noqa: BLE001
            logger.info(
                "Failed to update description for Navidrome playlist %s: %s",
                playlist.name,
                exc,
            )

    if playlist.poster and userInputs.add_playlist_poster:
        logger.info(
            "Navidrome API does not support updating playlist posters; skipping"
        )

    logger.info("Updated Navidrome playlist %s", playlist.name)

    if userInputs.write_missing_as_csv:
        if missing_tracks:
            try:
                _write_csv(missing_tracks, playlist.name)
                logger.info("Missing tracks written to %s.csv", playlist.name)
            except Exception as exc:  # noqa: BLE001
                logger.info(
                    "Failed to write missing tracks for %s: %s",
                    playlist.name,
                    exc,
                )
        else:
            try:
                _delete_csv(playlist.name)
                logger.info("Deleted old %s.csv", playlist.name)
            except Exception as exc:  # noqa: BLE001
                logger.info(
                    "Failed to delete %s.csv: %s",
                    playlist.name,
                    exc,
                )
