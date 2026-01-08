# v1cli Development Environment
# Python 3.11 + Node.js (for Claude Code) + useful tools

FROM debian:bookworm-slim as base

LABEL maintainer="v1cli Project"
LABEL description="Python development environment for v1cli"

# Set the SHELL to bash with pipefail option
SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Prevent dialog during apt install
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install --no-install-recommends -y \
    # Python
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    # Build tools
    build-essential \
    # Networking
    curl \
    ca-certificates \
    libssl-dev \
    # Git
    git \
    # Useful utilities
    less \
    vim-tiny \
    jq \
    && rm -rf /var/lib/apt/lists/*

# Install additional packages
RUN apt-get update && \
    apt-get upgrade -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" && \
    apt-get install -y -o Dpkg::Options::="--force-confdef" -o Dpkg::Options::="--force-confold" \
        coreutils \
        util-linux \
        file \
        openssl \
        locales \
        ssh \
        wget \
        sudo \
        htop \
        tmux \
        zsh \
        xz-utils \
        bash-completion && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set locale
RUN sed -i '/en_US.UTF-8/s/^# //g' /etc/locale.gen && locale-gen
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US:en
ENV LC_ALL=en_US.UTF-8

# Add user "dev" as non-root user
RUN useradd -ms /bin/bash dev

# Set sudoer for "dev"
RUN echo 'dev ALL=(ALL) NOPASSWD: ALL' >> /etc/sudoers

# Switch to user "dev"
USER dev
WORKDIR /home/dev

# Create a script file sourced by both interactive and non-interactive bash shells
ENV BASH_ENV=/home/dev/.bash_env
RUN touch "$BASH_ENV"
RUN echo '. "$BASH_ENV"' >> "$HOME/.bashrc"

# Install nvm and Node.js (needed for Claude Code)
ENV NVM_DIR=/home/dev/.nvm
ENV NODE_VERSION=22.12.0

RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash \
    && . $NVM_DIR/nvm.sh \
    && nvm install $NODE_VERSION \
    && nvm alias default $NODE_VERSION \
    && nvm use default

# nvm setup in bash_env
RUN echo 'export NVM_DIR="$HOME/.nvm"' >> "$BASH_ENV"
RUN echo '[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"' >> "$BASH_ENV"
RUN echo '[ -s "$NVM_DIR/bash_completion" ] && . "$NVM_DIR/bash_completion"' >> "$BASH_ENV"

# Python virtual environment setup
ENV VIRTUAL_ENV=/home/dev/venv
RUN python3 -m venv $VIRTUAL_ENV
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Add venv activation to bash_env
RUN echo 'export VIRTUAL_ENV=/home/dev/venv' >> "$BASH_ENV"
RUN echo 'export PATH="$VIRTUAL_ENV/bin:$PATH"' >> "$BASH_ENV"

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install Python dev tools
RUN pip install \
    pytest \
    pytest-asyncio \
    pytest-httpx \
    ruff \
    mypy \
    ipython \
    httpx

# Create project directory
RUN mkdir -p /home/dev/v1cli

# Default command
CMD ["bash"]

# Claude Code target
FROM base AS claude

# Install Claude Code
RUN . $NVM_DIR/nvm.sh && npm install -g @anthropic-ai/claude-code

CMD ["bash"]
