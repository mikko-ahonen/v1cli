# v1cli

An opinionated CLI and TUI tool for VersionOne, designed to get V1 out of the way so developers can focus on work.

## Features

- **CLI commands** for quick actions and scripting
- **Interactive TUI** dashboard for browsing stories and tasks
- **Opinionated 5-stage workflow**: Backlog → Ready → In Progress → Review → Done
- **Project bookmarks** stored locally for quick access
- **Status mapping** to translate your V1 statuses to the workflow

## Installation

```bash
pip install -e .
```

## Configuration

Set environment variables for authentication:

```bash
export V1_URL='https://www7.v1host.com/YourInstance'
export V1_TOKEN='your-api-token'
```

To generate an API token:
1. Log into your VersionOne instance
2. Go to your profile settings
3. Create a new access token

### First-Time Setup

Run the setup wizard to map your V1 statuses to the workflow:

```bash
v1 setup
```

This discovers available statuses and lets you map them to: Backlog, Ready, In Progress, Review, and Done.

## Usage

### Daily Workflow

```bash
# See what's on your plate
v1 mine

# Start working on a story
v1 status S-12345 progress

# View tasks for a story
v1 tasks S-12345

# Create a task
v1 task create S-12345 "Write unit tests" --estimate 2

# Move to review
v1 status S-12345 review

# Launch interactive dashboard
v1 tui
```

### Project Management

```bash
# List all accessible projects
v1 projects

# Bookmark a project
v1 project add "Backend API"

# Set default project
v1 project default "Backend API"

# Remove bookmark
v1 project remove "Backend API"
```

### Story Operations

```bash
# List stories in default project
v1 stories

# List stories in specific project
v1 stories -p "Backend API"

# View story details
v1 story S-12345

# Change status (backlog/ready/progress/review/done)
v1 status S-12345 review

# Assign story to yourself
v1 take S-12345

# Create a story
v1 story create "Add user authentication" --estimate 5

# Create story under an epic
v1 story create "Implement OAuth" --epic E-100 --estimate 3
```

### Epic Operations

```bash
# List epics
v1 epics

# Create an epic
v1 epic create "Q1 Security Improvements"
```

### Task Operations

```bash
# List tasks for a story
v1 tasks S-12345

# Create a task
v1 task create S-12345 "Write tests" --estimate 2

# Mark task as done
v1 task done Task:5678
```

## TUI Mode

Launch the interactive dashboard:

```bash
v1 tui
```

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `q` | Quit |
| `d` | Dashboard |
| `p` | Projects |
| `r` | Refresh |
| `Enter` | View selected item |
| `s` | Change status |
| `t` | View tasks |
| `Esc` | Go back |

## Workflow

v1cli enforces a linear workflow with valid transitions:

```
Backlog → Ready → In Progress → Review → Done
    ↑        ↓          ↓           ↓       ↓
    └────────┴──────────┴───────────┴───────┘
              (can move backwards)
```

Status shortcuts:
- `backlog`, `todo`, `new`
- `ready`
- `progress`, `in_progress`, `wip`
- `review`
- `done`, `complete`, `completed`

## Configuration Files

Settings are stored in `~/.v1cli/config.toml`:

```toml
member_oid = "Member:20"
member_name = "John Doe"
default_project = "Scope:1234"

[[bookmarks]]
name = "Backend API"
oid = "Scope:1234"

[[bookmarks]]
name = "Frontend"
oid = "Scope:5678"

[status_mapping]
backlog = "StoryStatus:134"
ready = "StoryStatus:135"
in_progress = "StoryStatus:136"
review = "StoryStatus:137"
done = "StoryStatus:138"
```

## Future: 1Password Integration

Support for 1Password CLI is planned. Once implemented:

```bash
# Will read token from 1Password item named "VersionOne"
pip install v1cli[onepassword]
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Type checking
mypy src/v1cli

# Linting
ruff check src/v1cli
```

## License

MIT
