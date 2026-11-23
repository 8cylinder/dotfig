Command reference
=================

SYNOPSIS
--------

``dotfig [OPTIONS] COMMAND [ARGS]...``

Run ``dotfig`` without a command to list the stored files.

DESCRIPTION
-----------

``dotfig`` keeps copies of individual files in a root directory that mirrors
their path in ``$HOME``. Store a file to copy it into the root; restore an
entry to copy it back. The root can be a git repository, so the stored copies
travel between machines.

COMMANDS
--------

.. click:: dotfig.cli:cli
   :prog: dotfig
   :nested: full

FILES
-----

``$XDG_CONFIG_HOME/dotfig/config.toml``
    The configuration file. It contains the absolute ``root`` path and the
    optional ``diff_tool`` executable name. Run ``dotfig --config`` to print
    the effective path. On macOS the path is
    ``~/Library/Application Support/dotfig/config.toml``; on Windows it is
    ``%LOCALAPPDATA%\dotfig\config.toml``.

``$XDG_DATA_HOME/bash-completion/completions/dotfig.bash``
    The generated bash completion script, unless ``BASH_COMPLETION_USER_DIR``
    is set. Run ``dotfig --completions`` to write it.

ENVIRONMENT
-----------

``XDG_CONFIG_HOME``
    Base directory for the config file.

``XDG_DATA_HOME``
    Base directory for the completion script. Falls back to
    ``~/.local/share``.

``BASH_COMPLETION_USER_DIR``
    Colon-separated completion directories. The first non-empty entry takes
    precedence over ``XDG_DATA_HOME``.

``NO_COLOR``, ``FORCE_COLOR``, ``TERM``
    Control color in ``--color=auto`` mode. ``--color=always`` and
    ``--color=never`` override them.

NOTES
-----

Bash completions need bash 4.4 or newer. Automatic loading needs
bash-completion 2.18 or newer. macOS ships bash 3.2 as ``/bin/bash``; install
a newer bash, for example with ``brew install bash``. Zsh is not supported.

SEE ALSO
--------

The project home page: https://github.com/8cylinder/dotfig
