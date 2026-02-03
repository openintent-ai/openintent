"""
OpenIntent CLI - Command-line interface for running workflows.

Commands:
    openintent demo                  Run the complete demo (server + agents + workflow)
    openintent run workflow.yaml     Run a workflow
    openintent validate workflow.yaml    Validate a workflow
    openintent list                  List sample workflows
"""

import argparse
import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path


def cmd_run(args: argparse.Namespace) -> None:
    """Run a workflow from a YAML file."""
    from .workflow import (
        WorkflowError,
        WorkflowNotFoundError,
        WorkflowSpec,
        WorkflowValidationError,
    )

    try:
        spec = WorkflowSpec.from_yaml(args.workflow)
    except WorkflowNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except WorkflowValidationError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except WorkflowError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════════════════════╗
║              OpenIntent Workflow Runner                      ║
╠══════════════════════════════════════════════════════════════╣
║  Workflow: {spec.name[:50]:<50}║
║  Phases: {len(spec.phases):<52}║
║  Server: {args.server[:50]:<50}║
╚══════════════════════════════════════════════════════════════╝
""")

    # Print phases
    print("Workflow Phases:")
    for i, phase in enumerate(spec.phases, 1):
        deps = f" (after: {', '.join(phase.depends_on)})" if phase.depends_on else ""
        print(f"  {i}. {phase.title} -> {phase.assign}{deps}")
    print()

    if args.dry_run:
        print("Dry run mode - not executing workflow")
        portfolio = spec.to_portfolio_spec()
        print("\nPortfolioSpec:")
        print(f"  name: {portfolio.name}")
        print(f"  intents: {len(portfolio.intents)}")
        for intent in portfolio.intents:
            print(f"    - {intent.title} -> {intent.assign}")
        return

    # Check if server is reachable
    import httpx

    try:
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{args.server}/.well-known/openintent.json")
            if resp.status_code != 200:
                print(f"Warning: Server at {args.server} may not be running")
    except Exception as e:
        print(f"Error: Cannot reach server at {args.server}")
        print(f"  {e}")
        print("\nStart the server with: openintent-server")
        sys.exit(1)

    print("Starting workflow execution...")
    print("(Make sure your agents are running)\n")

    try:
        result = asyncio.run(
            spec.run(
                server_url=args.server,
                api_key=args.api_key,
                timeout=args.timeout,
                verbose=not args.quiet,
            )
        )

        print("\n" + "=" * 60)
        print("WORKFLOW COMPLETE")
        print("=" * 60)

        if args.output:
            import json

            with open(args.output, "w") as f:
                json.dump(result, f, indent=2, default=str)
            print(f"Result saved to: {args.output}")
        else:
            import json

            print(json.dumps(result, indent=2, default=str))

    except TimeoutError:
        print(f"\nWorkflow timed out after {args.timeout}s")
        print("  - Check that all required agents are running")
        print("  - Increase timeout with --timeout flag")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nWorkflow cancelled")
        sys.exit(0)
    except Exception as e:
        print(f"\nWorkflow failed: {e}")
        sys.exit(1)


def cmd_validate(args: argparse.Namespace) -> None:
    """Validate a workflow YAML file."""
    from .workflow import (
        WorkflowError,
        WorkflowSpec,
        WorkflowValidationError,
        validate_workflow,
    )

    try:
        warnings = validate_workflow(args.workflow)
        spec = WorkflowSpec.from_yaml(args.workflow)

        print(f"Workflow '{spec.name}' is valid!")
        print(f"  Phases: {len(spec.phases)}")
        print(f"  Agents: {len(spec.agents)}")

        if warnings:
            print(f"\nWarnings ({len(warnings)}):")
            for warning in warnings:
                print(f"  - {warning}")

    except WorkflowValidationError as e:
        print(f"Validation Error: {e}", file=sys.stderr)
        sys.exit(1)
    except WorkflowError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def cmd_list(args: argparse.Namespace) -> None:
    """List sample workflows."""
    from .workflow import list_sample_workflows

    samples = list_sample_workflows()

    if not samples:
        print("No sample workflows found.")
        print("\nCreate workflows in: examples/workflows/")
        return

    print("Available Sample Workflows:\n")
    for sample in samples:
        print(f"  {sample['name']}")
        print(f"    Phases: {sample['phases']}")
        print(f"    Path: {sample['path']}")
        if sample["description"]:
            print(f"    {sample['description'][:60]}...")
        print()


def cmd_new(args: argparse.Namespace) -> None:
    """Create a new workflow from template."""
    name = args.name or "my_workflow"
    filename = f"{name.lower().replace(' ', '_')}.yaml"

    template = f"""openintent: "1.0"

info:
  name: "{name}"
  version: "1.0.0"
  description: "Description of your workflow"

agents:
  processor-agent:
    description: "Main processing agent"
    capabilities: ["processing"]

workflow:
  process:
    title: "Process Data"
    description: "Main processing phase"
    assign: processor-agent
    constraints:
      - "max_time_seconds: 60"
    initial_state:
      phase: "processing"
"""

    path = Path(filename)
    if path.exists() and not args.force:
        print(f"File already exists: {filename}")
        print("Use --force to overwrite")
        sys.exit(1)

    with open(path, "w") as f:
        f.write(template)

    print(f"Created workflow: {filename}")
    print("\nNext steps:")
    print(f"  1. Edit {filename} to define your workflow")
    print("  2. Start the server: openintent-server")
    print("  3. Run your agents")
    print(f"  4. Execute: openintent run {filename}")


def cmd_demo(args: argparse.Namespace) -> None:
    """Run the complete demo: server + agents + workflow."""
    import json
    import tempfile

    import httpx

    print("""
╔══════════════════════════════════════════════════════════════╗
║                    OpenIntent Demo                           ║
╠══════════════════════════════════════════════════════════════╣
║  This demo shows multi-agent coordination in action.         ║
║                                                              ║
║  What happens:                                               ║
║    1. Starts the OpenIntent server                           ║
║    2. Launches demo agents (researcher + summarizer)         ║
║    3. Runs the hello_world workflow                          ║
║    4. Shows coordinated results                              ║
╚══════════════════════════════════════════════════════════════╝
""")

    # Check for LLM API key
    has_openai = os.getenv("OPENAI_API_KEY")
    has_anthropic = os.getenv("ANTHROPIC_API_KEY")
    mock_mode = not has_openai and not has_anthropic

    if mock_mode:
        print("Note: No LLM API key found.")
        print("  Set OPENAI_API_KEY or ANTHROPIC_API_KEY for real LLM responses.")
        print("  Running in mock mode for demo purposes.\n")
    else:
        provider = "Anthropic" if has_anthropic else "OpenAI"
        print(f"Using {provider} for LLM responses.\n")

    processes = []
    agent_file = None
    workflow_file = None

    try:
        # Step 1: Start server
        print("[1/3] Starting OpenIntent server...")
        server_proc = subprocess.Popen(
            [sys.executable, "-m", "openintent.server"],
            stdout=subprocess.PIPE if not args.verbose else None,
            stderr=subprocess.PIPE if not args.verbose else None,
        )
        processes.append(server_proc)
        time.sleep(2)

        # Verify server
        try:
            with httpx.Client(timeout=5.0) as client:
                resp = client.get("http://localhost:8000/.well-known/openintent.json")
                if resp.status_code == 200:
                    print("       Server running at http://localhost:8000\n")
                else:
                    raise Exception(f"Server returned {resp.status_code}")
        except Exception as e:
            print(f"       Error: Server failed to start: {e}")
            sys.exit(1)

        # Step 2: Start demo agents using demo_agents module
        print("[2/3] Starting demo agents...")

        agent_script = """
import asyncio
import os
import hashlib

from openintent.agents import Agent, on_assignment

def check_llm():
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            return "anthropic", anthropic.Anthropic()
        except ImportError:
            pass
    if os.getenv("OPENAI_API_KEY"):
        try:
            from openai import OpenAI
            return "openai", OpenAI()
        except ImportError:
            pass
    return None, None

PROVIDER, LLM_CLIENT = check_llm()

def llm_call_with_adapter(prompt: str, oi_client, intent_id: str) -> str:
    \"\"\"Make LLM call using adapter for observability (token counts, cost).\"\"\"
    if not LLM_CLIENT:
        h = hashlib.md5(prompt.encode()).hexdigest()[:8]
        return f"[Mock #{h}] Multi-agent coordination enables scalable workflows through separation of concerns, parallel execution, and fault isolation."
    try:
        if PROVIDER == "anthropic":
            from openintent.adapters import AnthropicAdapter
            adapter = AnthropicAdapter(LLM_CLIENT, oi_client, intent_id)
            r = adapter.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )
            return r.content[0].text
        else:
            from openintent.adapters import OpenAIAdapter
            adapter = OpenAIAdapter(LLM_CLIENT, oi_client, intent_id)
            r = adapter.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )
            return r.choices[0].message.content
    except Exception as e:
        return f"[Error] {str(e)[:100]}"

@Agent("researcher", base_url="http://localhost:8000", api_key="dev-user-key")
class Researcher:
    @on_assignment
    async def work(self, intent):
        result = llm_call_with_adapter(f"Research: {intent.description}", self._client, intent.id)
        return {"findings": result}

@Agent("summarizer", base_url="http://localhost:8000", api_key="dev-user-key")
class Summarizer:
    @on_assignment
    async def work(self, intent):
        result = llm_call_with_adapter(f"Summarize: {intent.description}", self._client, intent.id)
        return {"summary": result}

async def main():
    await asyncio.gather(Researcher._run_async(), Summarizer._run_async())

if __name__ == "__main__":
    asyncio.run(main())
"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write(agent_script)
            agent_file = f.name

        agent_proc = subprocess.Popen(
            [sys.executable, agent_file],
            stdout=subprocess.PIPE if not args.verbose else None,
            stderr=subprocess.PIPE if not args.verbose else None,
        )
        processes.append(agent_proc)
        time.sleep(1)
        print("       Agents: researcher, summarizer\n")

        # Step 3: Run workflow
        print("[3/3] Running hello_world workflow...")

        # Try to find existing workflow, or create inline
        search_paths = [
            Path(__file__).parent.parent
            / "examples"
            / "workflows"
            / "hello_world.yaml",
            Path.cwd() / "examples" / "workflows" / "hello_world.yaml",
        ]

        workflow_path = None
        for p in search_paths:
            if p.exists():
                workflow_path = p
                break

        if not workflow_path:
            workflow_yaml = """openintent: "1.0"
info:
  name: "Hello World Demo"
  description: "Demo workflow showing multi-agent coordination"
workflow:
  research:
    title: "Research Topic"
    description: "Research the benefits of multi-agent coordination"
    assign: researcher
  summarize:
    title: "Summarize Findings"
    description: "Summarize the research findings"
    assign: summarizer
    depends_on: [research]
"""
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".yaml", delete=False
            ) as f:
                f.write(workflow_yaml)
                workflow_path = Path(f.name)
                workflow_file = workflow_path

        from .workflow import WorkflowSpec

        spec = WorkflowSpec.from_yaml(str(workflow_path))

        print(f"\nWorkflow: {spec.name}")
        print(f"Phases: {' -> '.join(p.title for p in spec.phases)}\n")

        result = asyncio.run(
            spec.run(
                server_url="http://localhost:8000",
                api_key="dev-user-key",
                timeout=60,
                verbose=True,
            )
        )

        print("\n" + "=" * 60)
        print("DEMO COMPLETE")
        print("=" * 60)
        print(json.dumps(result, indent=2, default=str))

    except KeyboardInterrupt:
        print("\n\nDemo interrupted.")
    except Exception as e:
        print(f"\nDemo failed: {e}")
        import traceback

        if args.verbose:
            traceback.print_exc()
        sys.exit(1)
    finally:
        print("\nCleaning up...")
        for proc in processes:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

        if agent_file:
            try:
                Path(agent_file).unlink(missing_ok=True)
            except Exception:
                pass
        if workflow_file:
            try:
                Path(workflow_file).unlink(missing_ok=True)
            except Exception:
                pass

        print("Done.")


def main() -> None:
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(
        prog="openintent",
        description="OpenIntent CLI - Run and manage multi-agent workflows",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.4.0",
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a workflow from YAML")
    run_parser.add_argument("workflow", help="Path to workflow YAML file")
    run_parser.add_argument(
        "--server",
        "-s",
        default="http://localhost:8000",
        help="OpenIntent server URL (default: http://localhost:8000)",
    )
    run_parser.add_argument(
        "--api-key",
        "-k",
        default="dev-user-key",
        help="API key for authentication (default: dev-user-key)",
    )
    run_parser.add_argument(
        "--timeout",
        "-t",
        type=int,
        default=300,
        help="Execution timeout in seconds (default: 300)",
    )
    run_parser.add_argument(
        "--output",
        "-o",
        help="Save result to JSON file",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show workflow without executing",
    )
    run_parser.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Suppress progress output",
    )
    run_parser.set_defaults(func=cmd_run)

    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate a workflow YAML")
    validate_parser.add_argument("workflow", help="Path to workflow YAML file")
    validate_parser.set_defaults(func=cmd_validate)

    # List command
    list_parser = subparsers.add_parser("list", help="List sample workflows")
    list_parser.set_defaults(func=cmd_list)

    # New command
    new_parser = subparsers.add_parser(
        "new", help="Create a new workflow from template"
    )
    new_parser.add_argument("name", nargs="?", help="Workflow name")
    new_parser.add_argument(
        "--force", action="store_true", help="Overwrite existing file"
    )
    new_parser.set_defaults(func=cmd_new)

    # Demo command
    demo_parser = subparsers.add_parser(
        "demo", help="Run the complete demo (server + agents + workflow)"
    )
    demo_parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show detailed output from server and agents",
    )
    demo_parser.set_defaults(func=cmd_demo)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    args.func(args)


if __name__ == "__main__":
    main()
