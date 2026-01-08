"""Pre-built query templates for common operations."""

# Standard attributes to select for stories
STORY_SELECT = [
    "Number",
    "Name",
    "Description",
    "Status.Name",
    "Status",
    "Scope.Name",
    "Scope",
    "Owners.Name",
    "Owners",
    "Super.Name",
    "Super",
    "Estimate",
]

# Standard attributes for epics
EPIC_SELECT = [
    "Number",
    "Name",
    "Description",
    "Status.Name",
    "Status",
    "Scope.Name",
    "Scope",
]

# Standard attributes for tasks
TASK_SELECT = [
    "Name",
    "Parent",
    "Parent.Number",
    "Status.Name",
    "Status",
    "Owners.Name",
    "ToDo",
    "Actuals",
]

# Standard attributes for projects
PROJECT_SELECT = [
    "Name",
    "Description",
]

# Standard attributes for members
MEMBER_SELECT = [
    "Name",
    "Email",
    "Username",
]
