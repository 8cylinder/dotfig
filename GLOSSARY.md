# dotfig

A CLI that keeps configuration files in a git-friendly root tree and links them back into `$HOME`.

## Language

**Dotfig root**:
The directory that mirrors `$HOME` and holds the stored copies. Commit it to git to move configs between machines.
_Avoid_: store, tree, repo (when the root itself is meant)

**Managed file**:
A file whose stored copy lives under the dotfig root and whose `$HOME` path is a symlink to that copy.
_Avoid_: single file, linked file

**Managed directory**:
A directory stored under the dotfig root as one unit, whose `$HOME` path is a single symlink to the stored directory.
_Avoid_: dir sync, directory link

**Stored copy**:
The copy of a managed file inside the dotfig root. For a managed directory, the stored directory tree.
_Avoid_: backup, source (for the stored side)

**Link status**:
The state of a managed entry's `$HOME` path: `linked`, `not linked`, `missing`, or `wrong link`.
_Avoid_: state, health
