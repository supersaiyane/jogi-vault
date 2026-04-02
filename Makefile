# =============================================================
# JOGI VAULT — Makefile
# =============================================================
# Run from the project ROOT (one level above vault/):
#   make -f vault/Makefile <target>
# Or from inside vault/:
#   make <target>
#
# All CLI targets accept:
#   P=<password or VLT-... machine token>   (or set VAULT_PASSWORD in env)
#   K=<key name>   V=<value>   NS=<namespace>
# =============================================================

ROOT    := $(shell cd .. && pwd)
PYTHON  := PYTHONPATH=$(ROOT) python
CLI     := $(PYTHON) $(ROOT)/vault/cli.py
PORT    ?= 5111
P       ?= $(VAULT_PASSWORD)
K       ?=
V       ?=
NS      ?= default

# ─────────────────────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────────────────────

.PHONY: up
up: ## Start vault UI locally → http://localhost:$(PORT)
	@echo "  Starting Vault UI → http://localhost:$(PORT)"
	@cd $(ROOT) && $(PYTHON) vault/ui.py

.PHONY: docker-up
docker-up: ## Start vault UI via docker-compose (detached)
	@cd $(ROOT) && docker-compose up vault-ui -d
	@echo "  Vault UI → http://localhost:$(PORT)"

.PHONY: docker-build
docker-build: ## Rebuild Docker image + restart
	@cd $(ROOT) && docker-compose up vault-ui --build -d

.PHONY: docker-down
docker-down: ## Stop the vault container
	@cd $(ROOT) && docker-compose stop vault-ui

.PHONY: docker-logs
docker-logs: ## Tail live logs from the vault container
	@cd $(ROOT) && docker-compose logs -f vault-ui

# ─────────────────────────────────────────────────────────────
# SECRETS  (P=password  K=key  V=value  NS=namespace)
# ─────────────────────────────────────────────────────────────

.PHONY: list
list: _require_p ## List all keys (values masked)   P=xxx [NS=name]
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) list

.PHONY: set
set: _require_p _require_k _require_v ## Add / update a key   P=xxx K=KEY V=value [NS=name]
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) set "$(K)" "$(V)"

.PHONY: get
get: _require_p _require_k ## Read a key value   P=xxx K=KEY [NS=name]
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) get "$(K)"

.PHONY: delete
delete: _require_p _require_k ## Delete a key   P=xxx K=KEY
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) delete "$(K)"

.PHONY: import-env
import-env: _require_p ## Import all keys from ../.env   P=xxx
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) import-env .env

# ─────────────────────────────────────────────────────────────
# NAMESPACES
# ─────────────────────────────────────────────────────────────

.PHONY: namespaces
namespaces: ## List all namespaces
	@cd $(ROOT) && $(PYTHON) -c \
	  "from src.vault import Vault; [print(' ', n) for n in Vault.list_namespaces()]"

.PHONY: new-namespace
new-namespace: _require_p _require_ns ## Create a namespace   P=xxx NS=name
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(PYTHON) -c \
	  "from src.vault import Vault; \
	   v = Vault(password='$(P)', _skip_totp=True); \
	   v.create_namespace('$(NS)'); \
	   print('  Namespace \"$(NS)\" created')"

.PHONY: delete-namespace
delete-namespace: _require_p _require_ns ## Delete a namespace   P=xxx NS=name
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(PYTHON) -c \
	  "from src.vault import Vault; \
	   v = Vault(password='$(P)', _skip_totp=True); \
	   v.delete_namespace('$(NS)'); \
	   print('  Namespace \"$(NS)\" deleted')"

# ─────────────────────────────────────────────────────────────
# PASSWORD / 2FA
# ─────────────────────────────────────────────────────────────

.PHONY: change-password
change-password: ## Change master password (prompts interactively)
	@cd $(ROOT) && $(CLI) change-password

.PHONY: forgot-password
forgot-password: ## Reset password using recovery key (prompts interactively)
	@cd $(ROOT) && $(CLI) forgot-password

.PHONY: save-password
save-password: ## Save password/token securely to macOS Keychain
	@cd $(ROOT) && $(PYTHON) -c "\
import getpass, subprocess; \
from src.vault import Vault; \
pwd = getpass.getpass('Vault password or machine token: '); \
Vault(password=pwd, _skip_totp=True); \
subprocess.run(['security', 'add-generic-password', \
  '-a', 'jogi-vault', '-s', 'JogiVault', '-w', pwd, '-U'], check=True); \
print('  Saved to macOS Keychain (JogiVault)'); \
print('  Load with:'); \
print('  export VAULT_PASSWORD=\$$(security find-generic-password -a jogi-vault -s JogiVault -w)')"

.PHONY: load-password
load-password: ## Print the shell command to load password from Keychain
	@echo ""
	@echo "  Run this in your terminal:"
	@echo ""
	@echo "  export VAULT_PASSWORD=\$$(security find-generic-password -a jogi-vault -s JogiVault -w)"
	@echo ""

.PHONY: setup-totp
setup-totp: _require_p ## Enable TOTP 2FA   P=xxx
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) setup-totp

.PHONY: disable-totp
disable-totp: _require_p ## Disable TOTP 2FA   P=xxx
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) disable-totp

.PHONY: new-emergency-key
new-emergency-key: _require_p ## Rotate emergency key   P=xxx
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(CLI) new-emergency-key

# ─────────────────────────────────────────────────────────────
# MACHINE TOKEN
# ─────────────────────────────────────────────────────────────

.PHONY: generate-token
generate-token: _require_p ## Generate a VLT-… machine token   P=real-password
	@cd $(ROOT) && $(PYTHON) -c "\
from src.vault import Vault; \
v = Vault(password='$(P)', _skip_totp=True); \
tok = v.generate_machine_token(); \
print(); \
print('  Machine token (copy this — shown once):'); \
print(); \
print('  ' + tok); \
print(); \
print('  Use as: VAULT_PASSWORD=' + tok); \
print()"

.PHONY: revoke-token
revoke-token: _require_p ## Revoke the active machine token   P=xxx
	@cd $(ROOT) && $(PYTHON) -c "\
from src.vault import Vault; \
v = Vault(password='$(P)', _skip_totp=True); \
v.revoke_machine_token(); \
print('  Machine token revoked')"

# ─────────────────────────────────────────────────────────────
# BACKUP
# ─────────────────────────────────────────────────────────────

.PHONY: backup
backup: _require_p ## Trigger a manual Google Drive backup   P=xxx
	@cd $(ROOT) && $(PYTHON) -c "\
from src.vault import Vault; \
from vault.services.backup import BackupManager; \
v  = Vault(password='$(P)', _skip_totp=True); \
bm = BackupManager(v); \
name = bm.backup_now(); \
print('  Backup complete:', name)"

# ─────────────────────────────────────────────────────────────
# EXPIRY
# ─────────────────────────────────────────────────────────────

.PHONY: set-expiry
set-expiry: _require_p _require_k ## Set a key with expiry   P=xxx K=KEY V=value E=2026-12-31
	@[ -n "$(V)" ] || (echo "  Error: V=<value> is required"; exit 1)
	@[ -n "$(E)" ] || (echo "  Error: E=<expiry date> is required  (ISO-8601, e.g. 2026-12-31)"; exit 1)
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(PYTHON) -c "\
from src.vault import Vault; \
v = Vault(password='$(P)', _skip_totp=True); \
v.set_with_expiry('$(K)', '$(V)', '$(E)T00:00:00+00:00'); \
print('  Set $(K) with expiry $(E)')"

.PHONY: expiring
expiring: _require_p ## List secrets expiring within N days (default 30)   P=xxx [DAYS=30]
	@cd $(ROOT) && VAULT_PASSWORD="$(P)" $(PYTHON) -c "\
from src.vault import Vault; \
v = Vault(password='$(P)', _skip_totp=True); \
items = v.list_expiring(within_days=int('$(or $(DAYS),30)')); \
if not items: print('  No secrets expiring within $(or $(DAYS),30) days.'); \
else: \
    print(); \
    for k, exp in items: print('  {} → expires {}'.format(k, exp[:10])); \
    print()"

# ─────────────────────────────────────────────────────────────
# AUDIT
# ─────────────────────────────────────────────────────────────

.PHONY: audit
audit: ## Show last 20 audit log entries
	@echo ""
	@if [ -f $(ROOT)/vault/data/audit.log ]; then \
		tail -20 $(ROOT)/vault/data/audit.log | $(PYTHON) -c "\
import sys, json; \
for line in sys.stdin: \
    e = json.loads(line); \
    ok = '✓' if e['ok'] else '✗'; \
    key = '  ' + e['key'] if e['key'] else ''; \
    ns = ' [' + e['ns'] + ']' if e['ns'] != 'default' else ''; \
    detail = '  (' + e['detail'] + ')' if e.get('detail') else ''; \
    print('  {} {} {}{}{}{}'.format(e['ts'][:19], ok, e['action'], key, ns, detail))"; \
	else \
		echo "  No audit log yet (vault/data/audit.log)"; \
	fi
	@echo ""

.PHONY: audit-failures
audit-failures: ## Show all failed operations from audit log
	@echo ""
	@if [ -f $(ROOT)/vault/data/audit.log ]; then \
		grep '"ok":false' $(ROOT)/vault/data/audit.log | $(PYTHON) -c "\
import sys, json; \
lines = list(sys.stdin); \
if not lines: print('  No failures recorded.'); \
else: \
    for line in lines: \
        e = json.loads(line); \
        detail = '  (' + e['detail'] + ')' if e.get('detail') else ''; \
        print('  {} ✗ {}{}'.format(e['ts'][:19], e['action'], detail))"; \
	else \
		echo "  No audit log yet (vault/data/audit.log)"; \
	fi
	@echo ""

# ─────────────────────────────────────────────────────────────
# STATUS / INFO
# ─────────────────────────────────────────────────────────────

.PHONY: status
status: ## Show vault configuration and health
	@cd $(ROOT) && $(PYTHON) -c "\
from src.vault import (Vault, VAULT_DIR, SECRETS_FILE, TOTP_FILE, \
                        EMERGENCY_FILE, RECOVERY_FILE, MACHINE_TOKEN_FILE, AUDIT_FILE); \
from vault.services.backup import BackupManager, OAUTH_FILE; \
print(); \
print('  Vault directory :', VAULT_DIR.resolve()); \
print('  Encryption      : AES-256-GCM'); \
print('  Initialized     :', '✓' if Vault.is_initialised() else '✗ run: make up'); \
print('  TOTP enabled    :', '✓' if TOTP_FILE.exists() else '✗'); \
print('  Recovery key    :', '✓' if RECOVERY_FILE.exists() else '✗'); \
print('  Emergency key   :', '✓' if EMERGENCY_FILE.exists() else '✗'); \
print('  Machine token   :', '✓ active' if MACHINE_TOKEN_FILE.exists() else '✗  generate from API tab'); \
print('  Drive backup    :', '✓ configured' if OAUTH_FILE.exists() else '✗  configure in Backup tab'); \
print('  Audit log       :', '✓ {} lines'.format(sum(1 for _ in open(AUDIT_FILE))) if AUDIT_FILE.exists() else '✗  no entries yet'); \
print('  Namespaces      :', ', '.join(Vault.list_namespaces()) if Vault.is_initialised() else 'n/a'); \
print()"

.PHONY: help
help: ## Show this help
	@echo ""
	@echo "  JOGI VAULT"
	@echo ""
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ \
	  { printf "  \033[36m%-22s\033[0m %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
	@echo ""
	@echo "  Variables:  P=<password or VLT-token>  K=<key>  V=<value>  NS=<namespace>"
	@echo ""

# ─────────────────────────────────────────────────────────────
# Internal guards
# ─────────────────────────────────────────────────────────────
_require_p:
	@[ -n "$(P)" ] || (echo "  Error: P=<password> is required  (or export VAULT_PASSWORD=...)"; exit 1)

_require_k:
	@[ -n "$(K)" ] || (echo "  Error: K=<key name> is required"; exit 1)

_require_v:
	@[ -n "$(V)" ] || (echo "  Error: V=<value> is required"; exit 1)

_require_ns:
	@[ "$(NS)" != "default" ] || (echo "  Error: NS=<namespace> is required"; exit 1)

.DEFAULT_GOAL := help
