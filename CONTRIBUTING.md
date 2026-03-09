# Contributing

## Development Setup

### System Dependencies

To build dependencies from source (such as `psycopg2`), you'll need the following system packages installed:

**Fedora/RHEL/CentOS:**
```bash
sudo dnf install gcc python3-devel libpq-devel
```

**Ubuntu/Debian:**
```bash
sudo apt-get install gcc python3-dev libpq-dev
```

**macOS:**
```bash
brew install postgresql
```

### Python Environment

Install dependencies using `uv`:

```bash
# Install uv (if not already installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Navigate to the API directory
cd src/api

# Install project dependencies
uv sync
```

### Pre-commit Hooks

To ensure coding standards are followed, please install the pre-commit
hooks before beginning development:

```bash
pre-commit install
```

_You can install `pre-commit` with `pip install pre-commit`._

## Running Multiple Worktrees Simultaneously

Each git worktree needs its own isolated dev stack (separate containers, ports, and
volumes). Use `WORKTREE_ID` to assign a unique integer (1–9) to each worktree:

```bash
# Worktree 0 — default ports (8080, 8000, 3000, 5432, 50051)
make dev

# Worktree 1 — ports offset by 100 (8180, 8100, 3100, 5532, 50151)
WORKTREE_ID=1 make dev

# Worktree 2 — ports offset by 200 (8280, 8200, 3200, 5632, 50251)
WORKTREE_ID=2 make dev
```

Alternatively, use the helper script which generates an `.env.worktree` file and
prints a summary of all assigned ports before starting:

```bash
scripts/worktree-dev.sh 1   # Start dev stack for WORKTREE_ID=1
```

Always pass the same `WORKTREE_ID` to `make down` when stopping:

```bash
WORKTREE_ID=1 make down
```

The `COMPOSE_PROJECT_NAME` is automatically set to `kartograph-wt<ID>`, which
namespaces containers, networks, and volumes so they never collide.

Create worktrees in the gitignored `.worktrees/` directory:

```bash
git worktree add .worktrees/my-feature -b feat/my-feature
cd .worktrees/my-feature
WORKTREE_ID=1 make dev
```

Validate the port parameterization at any time:

```bash
make test-worktree-isolation
```