# v1cli

An opinionated CLI and TUI tool for VersionOne, designed to get V1 out of the way so developers can focus on work.

## Features

- **CLI commands** for quick actions and scripting
- **Interactive TUI** dashboard for browsing stories and tasks
- **Opinionated 5-stage workflow**: Backlog → Ready → In Progress → Review → Done
- **Project bookmarks** stored locally for quick access
- **Status mapping** to translate your V1 statuses to the workflow
- **Per-project query configuration** with schema auto-detection
- **JSON output** for all list commands (`-f json`)
- **Row number caching** - reference items by number from previous list
- **Tree view** of project hierarchy with asset types

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

# List features, then drill into stories by row number
v1 features
v1 stories 3              # Stories under feature #3

# View tasks by row number from stories list
v1 tasks 2                # Tasks for story #2

# Start working on a story
v1 status S-12345 progress

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

### Project Tree

```bash
# View project hierarchy
v1 tree

# Show asset types and categories
v1 tree --types
# Output:
# Scope: My Project
# ├── Epic (Delivery Group): E-100 Q1 Release
# │   └── Epic (Feature): E-200 Login Feature
# │       └── Story: S-300 Implement OAuth

# Control tree depth
v1 tree --depth deliveries    # Only delivery groups
v1 tree --depth features      # DGs + features
v1 tree --depth stories       # DGs + features + stories (default)
v1 tree --depth tasks         # Full hierarchy including tasks

# Include closed items
v1 tree --all
```

### Story Operations

```bash
# List all stories under project (traverses DGs → Features)
v1 stories

# List stories under specific feature
v1 stories E-12345

# Use row number from previous 'v1 features' output
v1 stories 3

# List stories in specific project
v1 stories -p 1

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

### Feature Operations

```bash
# List all features (under project and all delivery groups)
v1 features

# Features show row numbers for quick reference
#  #   Number   Name            Status   Parent
#  1   E-100    Feature A       Active   DG 1
#  2   E-101    Feature B       Active   DG 1

# JSON output
v1 features -f json
```

### Epic Operations

```bash
# List epics
v1 epics

# Create an epic
v1 epic create "Q1 Security Improvements"

# View roadmap (delivery groups)
v1 roadmap
v1 roadmap -f json
```

### Task Operations

```bash
# List tasks for a story
v1 tasks S-12345

# Use row number from previous 'v1 stories' output
v1 tasks 3

# Create a task
v1 task create S-12345 "Write tests" --estimate 2

# Mark task as done
v1 task done Task:5678

# JSON output
v1 tasks S-12345 -f json
```

### JSON Output

All list commands support JSON output with `-f json`:

```bash
v1 features -f json
v1 stories -f json
v1 tasks S-12345 -f json
v1 mine -f json
v1 roadmap -f json
v1 projects -f json
```

### Query Configuration

Configure per-project query settings to match your V1 instance's available fields:

```bash
# Auto-detect available fields from V1 schema
v1 projects configure --auto-detect

# Show current configuration
v1 projects configure --show

# Reset to defaults
v1 projects configure --reset

# Configure specific project
v1 projects configure 1 --auto-detect
```

### Schema Discovery

Query your V1 instance's available fields:

```bash
# List available attributes for an asset type
v1 schema Epic
v1 schema Story
v1 schema Task
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
default_project = "Epic:1234"

[[bookmarks]]
name = "My Project"
oid = "Epic:1234"

# Per-project query configuration (auto-detected or manual)
[bookmarks.query_config]
version = 1
last_detected = "2025-01-15T10:30:00Z"

[bookmarks.query_config.stories]
select = ["Number", "Name", "Status.Name", "Estimate", "Owners.Name"]
filters = []
sort = ["-ChangeDateUTC"]

[[bookmarks.query_config.stories.columns]]
field = "Number"
label = "Number"
style = "cyan"

[[bookmarks.query_config.stories.columns]]
field = "Name"
label = "Name"

[status_mapping]
backlog = "StoryStatus:134"
ready = "StoryStatus:135"
in_progress = "StoryStatus:136"
review = "StoryStatus:137"
done = "StoryStatus:138"
```

Cache files are stored in `~/.v1cli/`:
- `features_cache.json` - Last features list for row number reference
- `stories_cache.json` - Last stories list for row number reference

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
