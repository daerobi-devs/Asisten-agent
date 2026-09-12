import asyncio
import sys
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.prompt import Prompt
from rich.text import Text
from rich import box

from lxion.core.config import settings
from lxion.core.context import SessionContext
from lxion.core.agent import Agent
from lxion.llm.router_client import NineRouterClient
from lxion.llm.token_tracker import tracker
from lxion.tools.registry import registry

console = Console()

BANNER = """
[bold cyan]  ██╗     ██╗  ██╗██╗ ██████╗ ███╗   ██╗[/bold cyan]
[bold cyan]  ██║     ╚██╗██╔╝██║██╔═══██╗████╗  ██║[/bold cyan]
[bold magenta]  ██║      ╚███╔╝ ██║██║   ██║██╔██╗ ██║[/bold magenta]
[bold magenta]  ██║      ██╔██╗ ██║██║   ██║██║╚██╗██║[/bold magenta]
[bold blue]  ███████╗██╔╝ ██╗██║╚██████╔╝██║ ╚████║[/bold blue]
[bold blue]  ╚══════╝╚═╝  ╚═╝╚═╝ ╚═════╝ ╚═╝  ╚═══╝[/bold blue]
[dim italic cyan]  Autonomous Full-Featured AI Agent • 9Router Gateway[/dim italic cyan]
"""

def print_header():
    console.print(BANNER)
    
    table = Table(box=box.SIMPLE, show_header=False, padding=(0, 2))
    table.add_row("[bold cyan]Version:[/bold cyan]", "0.3.0 (Hermes-Class Agentic)")
    table.add_row("[bold cyan]Gateway:[/bold cyan]", f"{settings.NINE_ROUTER_BASE_URL}")
    table.add_row("[bold cyan]Default Model:[/bold cyan]", f"[bold green]{settings.DEFAULT_MODEL}[/bold green]")
    table.add_row("[bold cyan]Active Tools:[/bold cyan]", f"{len(registry.get_all_tools())} loaded")
    table.add_row("[bold cyan]Workspace:[/bold cyan]", f"{settings.WORKSPACE_DIR.resolve()}")
    
    panel = Panel(
        table,
        title="[bold magenta]System Status[/bold magenta]",
        border_style="magenta",
        box=box.ROUNDED
    )
    console.print(panel)
    console.print("[dim]Type [bold cyan]/help[/bold cyan] for commands, or [bold cyan]/exit[/bold cyan] to quit.[/dim]\n")

async def show_models(client: NineRouterClient):
    with console.status("[bold cyan]Fetching models from 9Router...[/bold cyan]", spinner="dots"):
        models = await client.list_models()
    
    if not models:
        console.print("[yellow]No models returned or 9Router unreachable. Check API Key & URL.[/yellow]")
        return

    table = Table(title="Available 9Router Models", box=box.ROUNDED, border_style="cyan")
    table.add_column("Model ID", style="bold green")
    table.add_column("Owned By", style="dim")
    
    for m in models[:25]:  # show top 25
        table.add_row(m.get("id", "unknown"), m.get("owned_by", "9router"))
    
    console.print(table)
    if len(models) > 25:
        console.print(f"[dim]... and {len(models) - 25} more models available.[/dim]")

def show_tools():
    table = Table(title="Registered Agent Tools", box=box.ROUNDED, border_style="blue")
    table.add_column("Tool Name", style="bold green")
    table.add_column("Description", style="white")

    for t in registry.get_all_tools():
        table.add_row(t.name, t.description)

    console.print(table)

def show_stats():
    stats = tracker.get_summary()
    table = Table(title="Session Token Usage & Telemetry", box=box.ROUNDED, border_style="magenta")
    table.add_column("Metric", style="bold cyan")
    table.add_column("Value", style="bold yellow")

    table.add_row("Total Requests", str(stats["total_requests"]))
    table.add_row("Prompt Tokens", str(stats["prompt_tokens"]))
    table.add_row("Completion Tokens", str(stats["completion_tokens"]))
    table.add_row("Total Tokens", str(stats["total_tokens"]))
    table.add_row("Last Model Used", stats["last_model"] or "N/A")
    table.add_row("Last Latency", f"{stats['last_latency_ms']} ms")

    console.print(table)

async def cli_loop():
    print_header()
    client = NineRouterClient()
    agent = Agent(router_client=client)
    context = SessionContext()

    while True:
        try:
            user_input = Prompt.ask("[bold cyan]LXION[/bold cyan] [bold green]❯[/bold green]").strip()
            if not user_input:
                continue

            # Command Handlers
            if user_input.lower() in ("/exit", "exit", "quit"):
                console.print("[bold red]Shutting down LXION CLI. Goodbye![/bold red]")
                break
            elif user_input.lower() == "/clear":
                context = SessionContext()
                console.print("[bold yellow]✓ Conversation context cleared.[/bold yellow]\n")
                continue
            elif user_input.lower() == "/models":
                await show_models(client)
                continue
            elif user_input.lower() == "/tools":
                show_tools()
                continue
            elif user_input.lower() == "/stats":
                show_stats()
                continue
            elif user_input.lower() == "/help":
                console.print(Panel("""[bold cyan]Available Commands:[/bold cyan]
  [bold green]/models[/bold green] - List all available models from 9Router
  [bold green]/tools[/bold green]  - List currently active tools in registry
  [bold green]/stats[/bold green]  - View token usage and performance telemetry
  [bold green]/clear[/bold green]  - Clear conversation history
  [bold green]/exit[/bold green]   - Exit the CLI
                """, title="Help Menu", border_style="cyan", box=box.ROUNDED))
                continue

            def on_tool_start(name: str, args: dict):
                console.print(f"[bold yellow]⚙ Executing tool:[/bold yellow] [bold cyan]{name}[/bold cyan] [dim]({args})[/dim]")

            def on_tool_end(name: str, result: any):
                res_preview = str(result)
                if len(res_preview) > 120:
                    res_preview = res_preview[:120] + "..."
                console.print(f"[bold green]✓ Tool result ({name}):[/bold green] [dim]{res_preview}[/dim]")

            with console.status("[bold magenta]LXION thinking...[/bold magenta]", spinner="dots"):
                answer = await agent.run(
                    user_prompt=user_input,
                    context=context,
                    on_tool_start=on_tool_start,
                    on_tool_end=on_tool_end
                )

            console.print("\n[bold magenta]LXION[/bold magenta]:")
            console.print(Markdown(answer))
            console.print("")

        except (KeyboardInterrupt, EOFError):
            console.print("\n[bold red]Session terminated.[/bold red]")
            break
        except Exception as e:
            console.print(f"[bold red]Unexpected error: {e}[/bold red]")

def main():
    try:
        asyncio.run(cli_loop())
    except Exception as e:
        console.print(f"[bold red]Fatal error: {e}[/bold red]")
        sys.exit(1)

if __name__ == "__main__":
    main()