"""`yoto auth` commands."""

from typing import Annotated

import typer

from yoto.adapters.cli import presenters
from yoto.adapters.cli.deps import get_services
from yoto.adapters.cli.errors import handle_errors
from yoto.adapters.cli.output import emit, note
from yoto.adapters.cli.params import JsonOpt, verbose
from yoto.application import auth as auth_app_layer
from yoto.composition import build_services

auth_app = typer.Typer(help="Log in and inspect credentials.")


@auth_app.command()
@verbose()
@handle_errors
def login(
    port: Annotated[
        int | None,
        typer.Option(
            help="Loopback port; http://127.0.0.1:<port>/callback must be a "
            "registered redirect URI for your client id."
        ),
    ] = None,
    client_id: Annotated[
        str | None, typer.Option(help="Override the configured client id.")
    ] = None,
    no_browser: Annotated[
        bool, typer.Option("--no-browser", help="Print the URL instead of opening it.")
    ] = False,
) -> None:
    """Log in via the browser (OAuth authorization code + PKCE)."""
    services = get_services()
    overrides: dict[str, object] = {}
    if port is not None:
        overrides["redirect_port"] = port
    if client_id is not None:
        overrides["client_id"] = client_id
    if overrides:
        services = build_services(services.settings.model_copy(update=overrides))
    flow = services.login_flow(notify=note)
    info = flow.run(open_browser=not no_browser)
    note(f"Logged in as {info.sub or 'unknown user'}.")


@auth_app.command()
@verbose()
@handle_errors
def logout() -> None:
    """Forget the stored tokens."""
    services = get_services()
    auth_app_layer.logout(services.token_store)
    note("Logged out.")


@auth_app.command()
@verbose()
@handle_errors
def whoami(json_: JsonOpt = False) -> None:
    """Show the identity behind the current credentials."""
    services = get_services()
    info = auth_app_layer.whoami(services.token_provider, services.auth_gateway)
    emit(info, json_, presenters.show_user)


@auth_app.command()
@verbose()
@handle_errors
def token(
    refresh: Annotated[
        bool, typer.Option("--refresh", help="Force a refresh first.")
    ] = False,
) -> None:
    """Print a valid access token (for scripting: `curl -H "Authorization:
    Bearer $(yoto auth token)" ...`)."""
    services = get_services()
    provider = services.token_provider
    value = provider.on_unauthorized() if refresh else provider.access_token()
    typer.echo(value)
