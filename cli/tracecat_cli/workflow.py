import asyncio
import json
from pathlib import Path

import httpx
import orjson
import rich
import typer
from rich.console import Console

from ._client import Client
from ._utils import dynamic_table, read_input

app = typer.Typer(no_args_is_help=True, help="Manage workflows.")


@app.command(help="Create a workflow")
def create(
    title: str = typer.Option(None, "--title", "-t", help="Title of the workflow"),
    description: str = typer.Option(None, "--description", "-d", help="Description"),
    activate_workflow: bool = typer.Option(
        False, "--activate", help="Activate the workflow"
    ),
    activate_webhook: bool = typer.Option(
        False, "--webhook", help="Activate the webhook"
    ),
    defn_file: Path = typer.Option(
        None, "--commit", "-c", help="Create with workflow definition"
    ),
):
    """Create a new workflow."""

    result = _create_workflow(title=title, description=description)
    rich.print(result)
    if activate_workflow:
        _activate_workflow(result["id"], activate_webhook)
    if defn_file:
        _commit_workflow(defn_file, result["id"])


@app.command(help="Commit a workflow definition")
def commit(
    workflow_id: str = typer.Argument(..., help="ID of the workflow"),
    file: Path = typer.Option(
        None, "--file", "-f", help="Path to the workflow definition YAML file"
    ),
):
    """Commit a workflow definition to the database."""
    return _commit_workflow(file, workflow_id)


@app.command(name="list", help="List all workflow definitions")
def list_workflows(
    as_json: bool = typer.Option(False, "--json", help="Display as JSON"),
):
    """Commit a workflow definition to the database."""
    result = _list_workflows()
    if as_json:
        out = orjson.dumps(result, option=orjson.OPT_INDENT_2).decode()
        rich.print(out)
    elif not result:
        rich.print("[cyan]No workflows found[/cyan]")
    else:
        table = dynamic_table(result, "Workflows")
        Console().print(table)


@app.command(help="Run a workflow", no_args_is_help=True)
def run(
    workflow_id: str = typer.Argument(..., help="ID of the workflow to run"),
    data: str = typer.Option(None, "--data", "-d", help="JSON Payload to send"),
    proxy: bool = typer.Option(
        False,
        "--proxy",
        help="If set, run the workflow through the external-facing webhook",
    ),
    test: bool = typer.Option(
        False, "--test", help="If set, run the workflow with runtime action tests"
    ),
):
    """Triggers a webhook to run a workflow."""
    rich.print(f"Running workflow {workflow_id!r} {"proxied" if proxy else 'directly'}")
    payload = read_input(data) if data else None
    return _run_workflow(workflow_id, payload=payload, proxy=proxy, test=test)


@app.command(help="Activate a workflow", no_args_is_help=True)
def up(
    workflow_id: str = typer.Argument(..., help="ID of the workflow to activate."),
    with_webhook: bool = typer.Option(
        False, "--webhook", help="Activate its webhook as well."
    ),
):
    """Triggers a webhook to run a workflow."""
    rich.print(f"Activating workflow {workflow_id!r}")
    return _activate_workflow(workflow_id, with_webhook)


@app.command(help="List cases.", no_args_is_help=True)
def cases(
    workflow_id: str = typer.Argument(..., help="ID of the workflow to get cases."),
    table: bool = typer.Option(False, "--table", "-t", help="Display as table"),
):
    """Triggers a webhook to run a workflow."""
    results = _get_cases(workflow_id)
    if table:
        Console().print(dynamic_table(results, "Cases"))
    else:
        rich.print(results)


@app.command(help="Delete a workflow")
def delete(
    workflow_ids: list[str] = typer.Argument(..., help="IDs of the workflow to delete"),
):
    """Delete workflows"""

    if typer.confirm(f"Are you sure you want to delete {workflow_ids!r}"):
        asyncio.run(_delete_workflows(workflow_ids))
    else:
        rich.print("Aborted")


@app.command(help="Inspect a workflow")
def inspect(
    workflow_id: str = typer.Argument(..., help="ID of the workflow to inspect"),
):
    """Inspect a workflow"""

    with Client() as client:
        res = client.get(f"/workflows/{workflow_id}")
        result = Client.handle_response(res)
    rich.print(result)


def _commit_workflow(yaml_path: Path, workflow_id: str):
    """Commit a workflow definition to the database."""

    kwargs = {}
    if yaml_path:
        with yaml_path.open() as f:
            yaml_content = f.read()
        kwargs["files"] = {
            "yaml_file": (yaml_path.name, yaml_content, "application/yaml")
        }

    try:
        with Client() as client:
            res = client.post(f"/workflows/{workflow_id}/commit", **kwargs)
            Client.handle_response(res)
            rich.print(f"Successfully committed to workflow {workflow_id!r}!")
    except httpx.HTTPStatusError as e:
        rich.print(f"[red]Failed to commit to workflow {workflow_id!r}![/red]")
        rich.print(orjson.dumps(e.response.json(), option=orjson.OPT_INDENT_2).decode())


def _run_workflow(
    workflow_id: str,
    payload: dict[str, str] | None = None,
    proxy: bool = False,
    test: bool = False,
):
    with Client() as client:
        # Get the webhook url
        res = client.get(f"/workflows/{workflow_id}/webhook")
        webhook = Client.handle_response(res)
    content = orjson.dumps(payload) if payload else None
    if proxy:
        run_client = httpx.Client()
        url = webhook.url
    else:
        run_client = Client()
        url = f"/webhooks/{workflow_id}/{webhook.secret}"

    with run_client as client:
        res = client.post(
            url,
            content=content,
            headers={"X-Tracecat-Enable-Runtime-Tests": "true"} if test else None,
        )
        try:
            result = Client.handle_response(res)
            rich.print(result)
        except json.JSONDecodeError:
            rich.print(res.text)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                rich.print(
                    "Webhook or workflow not found. Are your workflow ID and webhook URL correct?."
                )
            elif e.response.status_code == 400:
                rich.print(
                    f"{e.response.text}. If the webhook or workflow is offline, "
                    "run `tracecat workflow up <workflow_id> --webhook` first."
                )
            else:
                rich.print(e.response.json())


def _create_workflow(title: str | None = None, description: str | None = None):
    with Client() as client:
        # Get the webhook url
        params = {}
        if title:
            params["title"] = title
        if description:
            params["description"] = description
        res = client.post("/workflows", content=orjson.dumps(params))
        result = Client.handle_response(res)
    rich.print("Created workflow")
    return result


def _activate_workflow(workflow_id: str, with_webhook: bool = False):
    with Client() as client:
        res = client.patch(
            f"/workflows/{workflow_id}", content=orjson.dumps({"status": "online"})
        )
        Client.handle_response(res)
        if with_webhook:
            res = client.patch(
                f"/workflows/{workflow_id}/webhook",
                content=orjson.dumps({"status": "online"}),
            )
            Client.handle_response(res)


def _list_workflows():
    with Client() as client:
        res = client.get("/workflows")
        return Client.handle_response(res)


def _get_cases(workflow_id: str):
    with Client() as client:
        res = client.get(f"/workflows/{workflow_id}/cases")
        return Client.handle_response(res)


async def _delete_workflows(workflow_ids: list[str]):
    async with Client() as client, asyncio.TaskGroup() as tg:
        for workflow_id in workflow_ids:
            tg.create_task(client.delete(f"/workflows/{workflow_id}"))

    rich.print("[green]Deleted workflows successfully![/green]")
