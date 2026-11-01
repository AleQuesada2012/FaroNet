"""Terminal demos and explicitly selected hardware bring-up commands."""

import argparse

from faronet import __version__


def main() -> int:
    """Show status, run simulations or explicitly request GPIO bring-up."""
    parser = argparse.ArgumentParser(
        prog="faronet",
        description="FaroNet development tools and local simulations.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="Show the scaffold's components and status.")
    from faronet import demos

    simulator = commands.add_parser("simulate", help="Run synthetic optical waveform scenarios.")
    simulator.add_argument("--scenario", choices=["all", *demos.SCENARIOS], default="all")
    commands.add_parser("auth-demo", help="Demonstrate synthetic HMAC and replay admission.")
    commands.add_parser("mesh-demo", help="Relay a padded onion message across a simulated mesh.")
    from faronet.faro import commands as optical_commands
    from faronet.node import chat
    from faronet.gateway import commands as gateway_commands

    optical_commands.add_commands(commands)
    chat.add_commands(commands)
    gateway_commands.add_commands(commands)
    args = parser.parse_args()
    if args.command.startswith(("gpio-", "optical-")):
        return optical_commands.run(args)
    if args.command in ("chat", "mesh-node"):
        return chat.run(args)
    if args.command in gateway_commands.NAMES:
        return gateway_commands.run(args)
    if args.command == "simulate":
        return demos.simulate(args.scenario)
    if args.command == "auth-demo":
        return demos.authentication()
    if args.command == "mesh-demo":
        return demos.mesh()

    print(f"FaroNet Python {__version__}: development scaffold ready")
    print("node: signed directory, onion envelopes, LAN links, chat and relay nodes ready")
    print("gateway: HMAC client for the Edge relay and dead drop ready")
    print("faro: GPIO optical bring-up commands ready; physical qualification and autonomous turns pending")
    print("DispositivoLuzAdaptador: frame/Manchester codec and simulator ready")
    return 0
