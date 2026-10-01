"""Small terminal entry point with no hardware or network side effects."""

import argparse

from faronet import __version__


def main() -> int:
    """Describe the scaffold until actual runtime commands are implemented."""
    parser = argparse.ArgumentParser(
        prog="faronet",
        description="FaroNet Python development scaffold.",
    )
    parser.add_argument("--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("info", help="Show the scaffold's components and status.")
    parser.parse_args()

    print(f"FaroNet Python {__version__}: development scaffold ready")
    print("node: mesh and private application implementation pending")
    print("gateway: authenticated edge relay implementation pending")
    print("faro: Raspberry Pi GPIO and optical protocol implementation pending")
    print("DispositivoLuzAdaptador: node/Faro communication library pending")
    return 0
