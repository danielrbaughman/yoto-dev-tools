"""MYO playlist tools: CRUD, folder import, downloads, media uploads."""

from pathlib import Path
from typing import Annotated, Any

from fastmcp import FastMCP
from pydantic import Field

from yoto.adapters.mcp._common import get_services, logger, tool_errors
from yoto.adapters.serialize import to_jsonable
from yoto.application import content as content_uc
from yoto.application import downloads as downloads_uc
from yoto.application import uploads as uploads_uc
from yoto.domain.content import CARD_JSON_EXAMPLE

CardId = Annotated[str, Field(description="Card/playlist id (5 chars).")]
READ_ONLY = {"readOnlyHint": True}


def register(mcp: FastMCP) -> None:
    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def playlist_list() -> list[dict[str, Any]]:
        """List all MYO playlists/cards in the account (API-native camelCase)."""
        return to_jsonable(content_uc.list_cards(get_services().content))

    @mcp.tool(annotations=READ_ONLY)
    @tool_errors
    def playlist_get(
        card_id: CardId,
        playable: Annotated[
            bool, Field(description="Include signed, playable track URLs.")
        ] = False,
    ) -> dict[str, Any]:
        """Get one playlist/card, including chapters and tracks. The result is
        valid input for playlist_update."""
        card = content_uc.get_card(get_services().content, card_id, playable=playable)
        return to_jsonable(card)

    @mcp.tool(
        description="Create a playlist from a JSON card object.\n\n" + CARD_JSON_EXAMPLE
    )
    @tool_errors
    def playlist_create(
        card: Annotated[dict[str, Any], Field(description="The card JSON object.")],
    ) -> dict[str, Any]:
        return to_jsonable(content_uc.create_card(get_services().content, card))

    @mcp.tool(
        description=(
            "Update a playlist with MERGE semantics: the current card is fetched, "
            "the patch is deep-merged over it (lists and scalars replace, objects "
            "merge), and the result is saved. Unknown fields are preserved.\n\n"
            + CARD_JSON_EXAMPLE
        ),
        annotations={"idempotentHint": True},
    )
    @tool_errors
    def playlist_update(
        card_id: CardId,
        patch: Annotated[
            dict[str, Any], Field(description="Partial card JSON to merge in.")
        ],
    ) -> dict[str, Any]:
        return to_jsonable(
            content_uc.update_card(get_services().content, card_id, patch)
        )

    @mcp.tool(annotations={"destructiveHint": True, "idempotentHint": True})
    @tool_errors
    def playlist_delete(card_id: CardId) -> dict[str, Any]:
        """Permanently delete a playlist/card."""
        content_uc.delete_card(get_services().content, card_id)
        return {"deleted": card_id}

    @mcp.tool
    @tool_errors
    def playlist_create_from_folder(
        folder: Annotated[
            str,
            Field(
                description="Local directory of audio files (mp3, m4a, ogg, flac, "
                "wav, ...). One chapter per file, natural sort order."
            ),
        ],
        title: Annotated[
            str | None, Field(description="Playlist title (default: folder name).")
        ] = None,
        cover: Annotated[
            str | None, Field(description="Local image file to upload as the cover.")
        ] = None,
        icon_media_id: Annotated[
            str | None,
            Field(description="Icon mediaId for every chapter (see icon_search)."),
        ] = None,
        loudnorm: Annotated[
            bool, Field(description="Ask Yoto to loudness-normalize the audio.")
        ] = False,
    ) -> dict[str, Any]:
        """Upload every audio file in a local folder and create one playlist
        from them. Slow: each file is uploaded and transcoded."""
        services = get_services()
        card = uploads_uc.create_playlist_from_folder(
            services.content,
            services.media,
            services.clock,
            Path(folder),
            title=title,
            cover=Path(cover) if cover else None,
            icon_media_id=icon_media_id,
            loudnorm=loudnorm,
            on_progress=logger.info,
        )
        return to_jsonable(card)

    @mcp.tool(annotations={"idempotentHint": True})
    @tool_errors
    def playlist_download(
        card_id: CardId,
        directory: Annotated[
            str | None,
            Field(
                description="Target directory on the machine running this server "
                "(default: ./<playlist title> under the server's working directory)."
            ),
        ] = None,
        cover: Annotated[bool, Field(description="Also save the cover image.")] = True,
        icons: Annotated[
            bool, Field(description="Also save resolvable chapter icons.")
        ] = True,
        overwrite: Annotated[
            bool, Field(description="Re-download files that already exist.")
        ] = False,
        concurrency: Annotated[
            int, Field(ge=1, description="Files to transfer at once.")
        ] = downloads_uc.DEFAULT_CONCURRENCY,
    ) -> dict[str, Any]:
        """Download a playlist's tracks as "NN - Title.<format>" (the original
        format Yoto stores, usually opus) plus cover, icons and card.json.
        Existing files are skipped unless overwrite. Slow for large playlists."""
        services = get_services()
        result = downloads_uc.download_playlist(
            services.content,
            services.media,
            card_id,
            Path(directory) if directory else None,
            cover=cover,
            icons=icons,
            overwrite=overwrite,
            concurrency=concurrency,
            on_progress=logger.info,
        )
        return to_jsonable(result)

    @mcp.tool
    @tool_errors
    def upload_audio(
        paths: Annotated[list[str], Field(description="Local audio files.")],
        loudnorm: Annotated[
            bool, Field(description="Ask Yoto to loudness-normalize.")
        ] = False,
    ) -> list[dict[str, Any]]:
        """Upload audio files and return their `yoto:#<sha256>` trackUrl values
        (plus transcoded format/duration/fileSize) for use in a card's tracks."""
        services = get_services()
        results = []
        for raw in paths:
            path = Path(raw)
            result = uploads_uc.upload_audio(
                services.media,
                services.clock,
                path,
                loudnorm=loudnorm,
                on_progress=logger.info,
            )
            results.append(
                {"file": str(path), "trackUrl": result.track_url, **result.to_api()}
            )
        return results

    @mcp.tool
    @tool_errors
    def upload_cover(
        path: Annotated[str, Field(description="Local image file.")],
        cover_type: Annotated[
            str,
            Field(
                description="default, myo, stories, music, podcast, radio, "
                "activities, or sfx."
            ),
        ] = "default",
    ) -> dict[str, Any]:
        """Upload a cover image; use the returned mediaUrl as metadata.cover.imageL."""
        cover = uploads_uc.upload_cover(
            get_services().media, Path(path), cover_type=cover_type
        )
        return {"mediaId": cover.media_id, "mediaUrl": cover.media_url}
