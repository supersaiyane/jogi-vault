#!/usr/bin/env python3
"""
Jogi Explains — Vault CLI
Usage:
  python vault_cli.py init                   # create vault + QR + emergency key
  python vault_cli.py setup-totp             # re-setup / replace TOTP
  python vault_cli.py disable-totp           # remove TOTP requirement
  python vault_cli.py set KEY VALUE          # add / update a secret
  python vault_cli.py get KEY                # retrieve a secret
  python vault_cli.py list                   # list all key names
  python vault_cli.py delete KEY             # remove a secret
  python vault_cli.py import-env [file]      # import from .env file
  python vault_cli.py export-env             # print keys (values masked)
  python vault_cli.py change-password        # change master password
  python vault_cli.py forgot-password        # reset via recovery key
  python vault_cli.py new-emergency-key      # rotate emergency key manually

Set VAULT_PASSWORD env var to skip password prompt.
All vault files are stored under vault/
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import qrcode
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from src.vault import Vault, VaultError, EmergencyKeyUsed

console = Console()


# ── QR helper ─────────────────────────────────────────────────────────────────

def print_qr(uri: str) -> None:
    qr = qrcode.QRCode(border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    console.print()
    for row in qr.get_matrix():
        line = "".join("█" if c else " " for c in row)
        console.print("  " + "".join(ch + ch for ch in line), highlight=False)
    console.print()


# ── Commands ──────────────────────────────────────────────────────────────────

def cmd_init() -> None:
    import getpass
    if Vault.is_initialised():
        console.print("[yellow]Vault already exists.[/] Use set/list/change-password.")
        sys.exit(0)

    pwd1 = getpass.getpass("Set vault password: ")
    pwd2 = getpass.getpass("Confirm password:   ")
    if not pwd1:
        console.print("[red]Password cannot be empty.[/]"); sys.exit(1)
    if pwd1 != pwd2:
        console.print("[red]Passwords do not match.[/]"); sys.exit(1)

    vault = Vault(password=pwd1, _skip_totp=True)

    # TOTP
    console.print("\n[bold cyan]Setting up authenticator 2FA...[/]")
    console.print("Works with YubiKey, Google Authenticator, Microsoft Authenticator,")
    console.print("Authy, 1Password, or any TOTP app.\n")
    uri = vault.setup_totp()
    print_qr(uri)
    console.print(f"[dim]URI: {uri}[/]\n")

    for attempt in range(3):
        code = input("Enter the 6-digit code to confirm: ").strip()
        if vault.verify_totp_code(code):
            console.print("[green]TOTP verified.[/]")
            break
        remaining = 2 - attempt
        if remaining:
            console.print(f"[red]Wrong code.[/] {remaining} attempt(s) left.")
    else:
        console.print("[red]TOTP verification failed. Run init again.[/]")
        vault.disable_totp()
        sys.exit(1)

    # Recovery key
    recovery_key  = vault.init_recovery_key()
    emergency_key = vault.generate_emergency_key()

    console.print()
    console.print(Panel(
        f"[bold white]{recovery_key}[/]",
        title="[yellow]RECOVERY KEY — resets your password. Save this.[/]",
        border_style="yellow",
    ))
    console.print(Panel(
        f"[bold white]{emergency_key}[/]",
        title="[red]EMERGENCY KEY — one-time TOTP bypass. Regenerates after use.[/]",
        border_style="red",
    ))
    console.print("[dim]Store both in a password manager or secure notes. Shown once.[/]")
    console.print("\n[green]Vault ready.[/] Run: make vault-save-password")


def _do_setup_totp(vault: Vault) -> None:
    uri = vault.setup_totp()
    console.print("\nScan with your authenticator app:\n")
    print_qr(uri)
    console.print(f"[dim]{uri}[/]\n")
    for attempt in range(3):
        code = input("Enter the 6-digit code to confirm: ").strip()
        if vault.verify_totp_code(code):
            console.print("[bold green]TOTP verified. 2FA is active.[/]")
            return
        remaining = 2 - attempt
        if remaining:
            console.print(f"[red]Wrong code.[/] {remaining} attempt(s) left.")
    console.print("[red]Could not verify. TOTP not saved.[/]")
    vault.disable_totp()
    sys.exit(1)


def cmd_setup_totp() -> None:
    _do_setup_totp(Vault())


def cmd_disable_totp() -> None:
    confirm = input("Type YES to disable TOTP: ").strip()
    if confirm != "YES":
        console.print("Aborted."); return
    Vault().disable_totp()
    console.print("[green]TOTP disabled.[/] Vault unlocks with password only.")


def cmd_set(key: str, value: str) -> None:
    Vault().set(key, value)
    console.print(f"[green]Set[/] {key}")


def cmd_get(key: str) -> None:
    try:
        console.print(Vault().get(key))
    except KeyError:
        console.print(f"[red]Not found:[/] {key}"); sys.exit(1)


def cmd_list() -> None:
    vault = Vault()
    keys  = vault.list_keys()
    if not keys:
        console.print("[yellow]Vault is empty.[/]"); return
    table = Table("Key", "Status", show_lines=False)
    for k in keys:
        table.add_row(k, "[green]set[/]")
    console.print(table)
    console.print(f"\n{len(keys)} secret(s) stored.")


def cmd_delete(key: str) -> None:
    try:
        Vault().delete(key)
        console.print(f"[red]Deleted[/] {key}")
    except KeyError:
        console.print(f"[red]Not found:[/] {key}"); sys.exit(1)


def cmd_import_env(env_file: str = ".env") -> None:
    try:
        count = Vault().import_from_env_file(Path(env_file))
        console.print(f"[green]Imported {count} key(s)[/] from {env_file}")
    except FileNotFoundError:
        console.print(f"[red]File not found:[/] {env_file}"); sys.exit(1)


def cmd_export_env() -> None:
    for key, value in sorted(Vault().to_env().items()):
        masked = value[:4] + "*" * max(0, len(value) - 4)
        console.print(f"{key}={masked}")


def cmd_change_password() -> None:
    import getpass
    current = getpass.getpass("Current password: ")
    if not current:
        console.print("[red]Cannot be empty.[/]"); sys.exit(1)
    try:
        vault = Vault(password=current)
    except VaultError as exc:
        console.print(f"[red]Wrong password:[/] {exc}"); sys.exit(1)
    new1 = getpass.getpass("New password: ")
    new2 = getpass.getpass("Confirm:      ")
    if new1 != new2:
        console.print("[red]Passwords do not match.[/]"); sys.exit(1)
    if not new1:
        console.print("[red]Cannot be empty.[/]"); sys.exit(1)
    vault.change_password(new1)
    console.print("[green]Password changed.[/] Run: make vault-save-password")


def cmd_forgot_password() -> None:
    import getpass
    console.print("[yellow]Password reset — identity check via recovery key.[/]\n")
    rk   = input("Recovery key (JOGI-…): ").strip()
    new1 = getpass.getpass("New password: ")
    new2 = getpass.getpass("Confirm:      ")
    if new1 != new2:
        console.print("[red]Passwords do not match.[/]"); sys.exit(1)
    if not new1:
        console.print("[red]Cannot be empty.[/]"); sys.exit(1)
    try:
        Vault.reset_password_with_recovery_key(rk, new1)
        console.print("[green]Password reset.[/] Run: make vault-save-password")
    except VaultError as exc:
        console.print(f"[red]Failed:[/] {exc}"); sys.exit(1)


def cmd_new_emergency_key() -> None:
    vault       = Vault()
    new_key     = vault.generate_emergency_key()
    console.print(Panel(
        f"[bold white]{new_key}[/]",
        title="[red]NEW EMERGENCY KEY — save this immediately[/]",
        border_style="red",
    ))


# ── Dispatch ──────────────────────────────────────────────────────────────────

COMMANDS = {
    "init":              (cmd_init,             0),
    "setup-totp":        (cmd_setup_totp,        0),
    "disable-totp":      (cmd_disable_totp,      0),
    "set":               (cmd_set,               2),
    "get":               (cmd_get,               1),
    "list":              (cmd_list,              0),
    "delete":            (cmd_delete,            1),
    "import-env":        (cmd_import_env,        0),
    "export-env":        (cmd_export_env,        0),
    "change-password":   (cmd_change_password,   0),
    "forgot-password":   (cmd_forgot_password,   0),
    "new-emergency-key": (cmd_new_emergency_key, 0),
}


def main() -> None:
    args = sys.argv[1:]
    if not args or args[0] not in COMMANDS:
        console.print(__doc__); sys.exit(0)

    cmd, remaining = args[0], args[1:]
    fn, expected   = COMMANDS[cmd]

    if cmd == "import-env":
        fn(remaining[0]) if remaining else fn(); return

    if len(remaining) != expected:
        console.print(
            f"[red]Usage:[/] python vault_cli.py {cmd} "
            + " ".join(f"<arg{i+1}>" for i in range(expected))
        ); sys.exit(1)

    fn(*remaining)


if __name__ == "__main__":
    main()
