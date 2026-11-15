# dotfig

A CLI that keeps configuration files in a git-friendly root tree and links them back into `$HOME`.

## Language

**Dotfig root**:
The directory that mirrors `$HOME` and holds the stored copies. Commit it to git to move configs between machines.
_Avoid_: tree, repo (when the root itself is meant)

**Managed file**:
A file whose stored copy lives under the dotfig root and whose `$HOME` path is a regular copy of it.
_Avoid_: single file, linked file

**Managed directory**:
A directory stored under the dotfig root as one unit, copied to its `$HOME` path.
_Avoid_: dir sync, directory link

**Stored copy**:
The copy of a managed file inside the dotfig root. For a managed directory, the stored directory tree.
_Avoid_: backup, source

**Store path**:
The path of a stored copy inside the dotfig root.
_Avoid_: source, stored path

**Host path**:
The mirrored path under `$HOME` for a managed entry.
_Avoid_: destination, target

**Match status**:
Whether a managed entry's host copy has the same contents as its store copy: `✓` when they match, `✗` when they differ or the host copy is missing.
_Avoid_: link status, state, health
