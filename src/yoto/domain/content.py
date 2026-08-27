"""Content (card/playlist) domain models.

A "card" and a "playlist" are the same API object: a playlist becomes a card
when linked to a physical MYO card (which can only be done from the app/player,
not the API). The documented schema is loose in places, so every field here is
optional and unknown fields ride along in the models' extras.
"""

from pydantic import Field

from yoto.domain.base import ApiModel

CARD_JSON_EXAMPLE = """The JSON card schema (only "title" and one chapter/track are required; unknown fields are passed through untouched):

{
  "title": "My Playlist",                    // required, 1-140 chars
  "content": {
    "chapters": [                            // 1+ chapters
      {
        "key": "01",
        "title": "Chapter One",
        "display": {"icon16x16": "yoto:#<mediaId>"},   // see `yoto myo icon`
        "tracks": [                          // 1+ tracks per chapter
          {
            "key": "01",
            "title": "Track One",
            "trackUrl": "yoto:#<sha256>",    // from `myo playlist upload audio`,
            "type": "audio",                 //   or a URL with type "stream"
            "format": "opus",                // opus | mp3 | aac | wav | ...
            "duration": 185,                 // seconds (optional)
            "fileSize": 2960000              // bytes (optional)
          }
        ]
      }
    ],
    "config": {"autoadvance": "next"}        // next | repeat | none
  },
  "metadata": {
    "cover": {"imageL": "https://..."},      // from `myo playlist upload cover`
    "description": "...",
    "author": "...",
    "category": "stories",  // stories|music|radio|podcast|sfx|activities|none
    "languages": ["en"],
    "minAge": 3,
    "maxAge": 8
  }
}

Tip: `yoto myo playlist get <id> --json` prints a real card in exactly this shape, ready to edit and feed back in."""


class TrackDisplay(ApiModel):
    # Explicit aliases: to_camel would mangle these to icon16X16.
    icon16x16: str | None = Field(default=None, alias="icon16x16")
    """A "yoto:#<mediaId>" reference to an uploaded icon."""
    icon_url16x16: str | None = Field(default=None, alias="iconUrl16x16")
    """Fully-qualified URL to a 16x16 RGBA PNG (dynamic icons)."""


class Track(ApiModel):
    key: str | None = None
    title: str | None = None
    track_url: str | None = None  # "yoto:#<sha256>" for uploads, URL for streams
    format: str | None = None  # mp3 | aac | opus | ...
    type: str | None = "audio"  # audio | stream
    duration: int | float | None = None  # seconds
    file_size: int | None = None  # bytes
    channels: int | str | None = None  # documented as both 2 and "stereo"
    overlay_label: str | None = None
    display: TrackDisplay | None = None


class Chapter(ApiModel):
    key: str | None = None
    title: str | None = None
    tracks: list[Track] = Field(default_factory=list)
    display: TrackDisplay | None = None
    overlay_label: str | None = None
    duration: int | float | None = None
    file_size: int | None = None


class ShuffleRange(ApiModel):
    """0-based chapter range (end inclusive); limit crops after shuffling."""

    start: int | None = None
    end: int | None = None
    limit: int | None = None


class CardConfig(ApiModel):
    autoadvance: str | None = None  # next | repeat | none
    online_only: bool | None = None
    resume_timeout: int | None = None  # seconds
    shuffle: list[ShuffleRange] | None = None


class CardContent(ApiModel):
    chapters: list[Chapter] = Field(default_factory=list)
    config: CardConfig | None = None
    playback_type: str | None = None  # linear | interactive
    version: str | None = None


class Cover(ApiModel):
    image_l: str | None = None  # serialized as "imageL"


class MediaInfo(ApiModel):
    duration: int | float | None = None
    file_size: int | None = None


class CardMetadata(ApiModel):
    cover: Cover | None = None
    description: str | None = None
    author: str | None = None
    category: str | None = None  # stories | music | podcast | ...
    genres: list[str] | None = None
    languages: list[str] | None = None
    min_age: int | None = None
    max_age: int | None = None
    note: str | None = None
    media: MediaInfo | None = None


class Card(ApiModel):
    card_id: str | None = None  # 5 chars, server-assigned on create
    title: str | None = None
    content: CardContent | None = None
    metadata: CardMetadata | None = None
    slug: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
