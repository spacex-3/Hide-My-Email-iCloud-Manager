import time

from rich.console import Console
from rich.table import Table

from hme_core import delete_hme, deactivate_hme, export_hme_list, fetch_hme_list, load_cookies

console = Console()


def main() -> None:
    console.print("[bold green]🚀 Hide My Email Manager[/]")

    try:
        cookies = load_cookies()
    except Exception as exc:
        console.print(f"[bold red]{exc}[/]")
        return

    try:
        hme_list = fetch_hme_list(cookies)
    except Exception as exc:
        console.print(f"[bold red]{exc}[/]")
        return

    if not hme_list:
        console.print("[yellow]No Hide My Email entries found.[/]")
        return

    export_hme_list(hme_list)
    console.print(f"[green]Saved {len(hme_list)} entries to emails.txt[/]\n")

    table = Table(title="Hide My Email Entries")
    table.add_column("ID")
    table.add_column("Email")
    table.add_column("Active")

    for item in hme_list:
        table.add_row(item["anonymousId"], item["email"], str(item["isActive"]))

    console.print(table)
    console.print("\n[bold red]Starting deactivation + deletion...[/]")

    for item in hme_list:
        anon = item["anonymousId"]
        email = item["email"]

        console.print("\n[cyan]────────────────────────────────────────[/]")
        console.print(f"[white]📧 Email:[/] {email}")
        console.print(f"[white]🔑 ID:[/] {anon}")

        if item["isActive"]:
            console.print("[yellow]🟡 Status: ACTIVE[/]")
            ok, message = deactivate_hme(cookies, anon)
            icon = "✔" if ok else "✖"
            console.print(f" → Deactivating... {icon} {message}")
            time.sleep(1)
        else:
            console.print("[blue]🔵 Status: INACTIVE (skipping deactivation)[/]")

        ok, message = delete_hme(cookies, anon)
        icon = "✔" if ok else "✖"
        console.print(f" → Deleting....... {icon} {message}")
        time.sleep(1)
        console.print("[cyan]────────────────────────────────────────[/]")

    console.print("\n[bold green]✔ All entries processed successfully![/]")


if __name__ == "__main__":
    main()
