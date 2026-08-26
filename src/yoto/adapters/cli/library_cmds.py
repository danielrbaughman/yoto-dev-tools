"""`yoto playlist groups` and `yoto family images` commands."""

from pathlib import Path
from typing import Annotated

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import emit, note
from yoto.adapters.cli.params import JsonOpt, YesOpt, verbose
from yoto.application import library as library_uc

# groups_app is mounted under `yoto playlist` (see playlist_cmds).
groups_app = typer.Typer(help="Named groups organizing the family library.")

family_app = typer.Typer(help="Family resources.")
images_app = typer.Typer(help="Family images (usable as group images).")
family_app.add_typer(images_app, name="images")

GroupIdArg = Annotated[str, typer.Argument(help="Group id.")]


@groups_app.command("list")
@verbose()
@handle_errors
def groups_list(json_: JsonOpt = False) -> None:
    """List library groups."""
    groups = library_uc.list_groups(get_services().library)
    emit(groups, json_, presenters.show_groups)


@groups_app.command("get")
@verbose()
@handle_errors
def groups_get(group_id: GroupIdArg, json_: JsonOpt = False) -> None:
    """Show one group with its content."""
    group = library_uc.get_group(get_services().library, group_id)
    emit(group, json_, presenters.show_group)


@groups_app.command("create")
@verbose()
@handle_errors
def groups_create(
    name: Annotated[str, typer.Option("--name", help="Group name (max 100 chars).")],
    image: Annotated[
        str,
        typer.Option(
            help="Image id: a pre-made id or an uploaded family image id. "
            "The API rejects creation without one (observed live), hence "
            "the default."
        ),
    ] = "fp-cards",
    content: Annotated[
        list[str] | None,
        typer.Option("--content", help="Content id to include (repeatable)."),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Create a group (max 20 per family)."""
    group = library_uc.create_group(
        get_services().library, name=name, image_id=image, content_ids=content
    )
    emit(group, json_, presenters.show_group)


@groups_app.command("update")
@verbose()
@handle_errors
def groups_update(
    group_id: GroupIdArg,
    name: Annotated[str | None, typer.Option("--name")] = None,
    image: Annotated[str | None, typer.Option(help="Image id.")] = None,
    content: Annotated[
        list[str] | None,
        typer.Option(
            "--content",
            help="Content id (repeatable); replaces the group's items when given.",
        ),
    ] = None,
    json_: JsonOpt = False,
) -> None:
    """Update a group (only the provided fields change)."""
    group = library_uc.update_group(
        get_services().library,
        group_id,
        name=name,
        image_id=image,
        content_ids=content,
    )
    emit(group, json_, presenters.show_group)


@groups_app.command("delete")
@verbose()
@handle_errors
def groups_delete(group_id: GroupIdArg, yes: YesOpt = False) -> None:
    """Delete a group (content stays in the library)."""
    if not yes:
        typer.confirm(f"Delete group {group_id}?", abort=True, err=True)
    library_uc.delete_group(get_services().library, group_id)
    note(f"Deleted {group_id}.")


@images_app.command("list")
@verbose()
@handle_errors
def images_list(
    limit: Annotated[int | None, typer.Option(help="Max images to return.")] = None,
    json_: JsonOpt = False,
) -> None:
    """List uploaded family images."""
    images = library_uc.list_family_images(get_services().family_images, limit=limit)
    emit(images, json_, presenters.show_family_images)


@images_app.command("upload")
@verbose()
@handle_errors
def images_upload(
    file: Annotated[Path, typer.Argument(help="JPEG/PNG/GIF, max 8 MB.")],
    json_: JsonOpt = False,
) -> None:
    """Upload a family image (deduplicated by content hash)."""
    image = library_uc.upload_family_image(get_services().family_images, file)
    emit(
        image,
        json_,
        lambda i: presenters.show_kv({"imageId": i.image_id, "url": i.url}),
    )


@images_app.command("get")
@verbose()
@handle_errors
def images_get(
    image_id: Annotated[str, typer.Argument(help="Family image id (sha256).")],
    size: Annotated[
        str, typer.Option(help="640x480 or 320x320 (the only supported sizes).")
    ] = "640x480",
    json_: JsonOpt = False,
) -> None:
    """Print a signed URL for a family image (valid ~7 days)."""
    url = library_uc.resolve_family_image_url(
        get_services().family_images, image_id, size=size
    )
    emit({"imageId": image_id, "url": url}, json_, lambda kv: presenters.show_kv(kv))
