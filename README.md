# Navidrome Playlist Sync

Create Spotify playlists in your Navidrome account using tracks from your server and keep Navidrome playlists in sync with the originals.

This DOES NOT download any songs from anywhere.

## Features

* From Spotify: Sync all of the given user account's public playlists to Navidrome
* Option to write missing songs as a csv
* Option to include description in playlists.

## Prerequisites

### Navidrome

* Navidrome base URL and port
* Navidrome username and password (or app password)

### To use Spotify sync

* Spotify client ID and client secret - Can be obtained from [spotify developer](https://developer.spotify.com/dashboard/login)
* Spotify user ID - This can be found on spotify [account page](https://www.spotify.com/us/account/overview/)

## Docker Setup

You need either docker or docker with docker-compose to run this.

Configure the parameters as needed. Navidrome URL, credentials, and Spotify variables are mandatory.

### Docker Run

```bash
docker run -d \
  --name=navidrome-playlist-sync \
  -e NAVIDROME_BASE_URL=<your navidrome url> \
  -e NAVIDROME_PORT=<your navidrome port> \
  -e NAVIDROME_USERNAME=<your navidrome username> \
  -e NAVIDROME_PASSWORD=<your navidrome password> \
  -e NAVIDROME_LEGACY_AUTH=<1 or 0> # Default 0, 1 = enable legacy auth if required
  -e WRITE_MISSING_AS_CSV=<1 or 0> # Default 0, 1 = writes missing tracks from each playlist to a csv
  -e APPEND_SERVICE_SUFFIX=<1 or 0> # Default 1, 1 = appends the service name to the playlist name
  -e ADD_PLAYLIST_POSTER=<1 or 0> # Default 0, 1 = add poster for each playlist
  -e ADD_PLAYLIST_DESCRIPTION=<1 or 0> # Default 1, 1 = add description for each playlist
  -e APPEND_INSTEAD_OF_SYNC=0 # Default 0, 1 = Sync tracks, 0 = Append only
  -e SECONDS_TO_WAIT=84000 # Seconds to wait between syncs \
  -e SPOTIFY_CLIENT_ID=<your spotify client id> # Option 1 \
  -e SPOTIFY_CLIENT_SECRET=<your spotify client secret> # Option 1 \
  -e SPOTIFY_USER_ID=<your spotify user id from the account page> # Option 1 \
  -v <Path where you want to write missing tracks>:/data \
  --restart unless-stopped \
  ghcr.io/wieluk/navidrome-playlist-sync:latest
```

#### Notes

* Include `http://` or `https://` in the NAVIDROME_BASE_URL

### Docker Compose

docker-compose.yml can be configured as follows

```yaml
services:
  navidrome-playlist-sync:
    container_name: navidrome-playlist-sync
    image: ghcr.io/wieluk/navidrome-playlist-sync:latest
    # optional only necessary if you chose WRITE_MISSING_AS_CSV=1 in env
    #volumes:
    #  - ./data:/data
    environment:
      - NAVIDROME_BASE_URL=${NAVIDROME_BASE_URL}
      - NAVIDROME_PORT=443 # Default 443 for https, 80 for http, 4533 default navidrome port
      - NAVIDROME_USERNAME=${NAVIDROME_USERNAME}
      - NAVIDROME_PASSWORD=${NAVIDROME_PASSWORD}
      - NAVIDROME_LEGACY_AUTH=0 # Default 0, set to 1 only if your server requires legacy auth
      - WRITE_MISSING_AS_CSV=1 # Default 0, 1 = writes missing tracks from each playlist to a csv
      - APPEND_SERVICE_SUFFIX=0 # Default 1, 1 = appends the service name to the playlist name
      - ADD_PLAYLIST_POSTER=1 # Default 1, 1 = add poster for each playlist
      - ADD_PLAYLIST_DESCRIPTION=1 # Default 1, 1 = add description for each playlist
      - APPEND_INSTEAD_OF_SYNC=0 # Default 0, 1 = Sync tracks, 0 = Append only
      - SECONDS_TO_WAIT=40000
      - SPOTIFY_CLIENT_ID=${SPOTIFY_CLIENT_ID}
      - SPOTIFY_CLIENT_SECRET=${SPOTIFY_CLIENT_SECRET}
      - SPOTIFY_USER_ID=${SPOTIFY_USER_ID}
      - PUID=1000
      - PGID=100
    restart: unless-stopped
```

And run with :

```bash
docker-compose up
```

### Issues

Something's off? See room for improvement? Feel free to open an issue with as much info as possible. Cheers!
