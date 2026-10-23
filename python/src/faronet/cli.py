"""Small terminal entry point with no hardware or network side effects."""

import argparse

from faronet import __version__


def main() -> int:
    """Show status or run first-milestone demonstrations without hardware."""
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
    args = parser.parse_args()
    if args.command == "simulate":
        return demos.simulate(args.scenario)
    if args.command == "auth-demo":
        return demos.authentication()
    if args.command == "mesh-demo":
        return demos.mesh()

    print(f"FaroNet Python {__version__}: development scaffold ready")
    print("node: signed directory, onion envelopes and mesh simulation ready; transport/chat UI pending")
    print("gateway: offline HMAC/replay helpers ready; live HTTPS relay pending")
    print("faro: Raspberry Pi GPIO and autonomous link implementation pending")
    print("DispositivoLuzAdaptador: frame/Manchester codec and simulator ready")
    return 0
