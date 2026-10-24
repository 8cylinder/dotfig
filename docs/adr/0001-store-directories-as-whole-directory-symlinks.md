# Store directories as whole-directory symlinks

**Status**: accepted

When `dotfig store` is given a directory, it stores the directory in the dotfig root as one unit and replaces the `$HOME` path with a single symlink to that stored directory. The alternative was to recurse and manage each file individually, which keeps file-level conflict handling but makes a stored directory a snapshot: new files are not picked up until the next `store`. The whole-directory link makes new and deleted files follow the link automatically, at the cost of coarser listing and conflict handling.

**Considered options**:

- Recursive per-file: preserves the existing file-only model and `list`, but requires re-running `store` for new files and cannot represent an empty managed directory.
- Whole-directory symlink (chosen): one managed entry, automatic new/deleted files, but `list` and `restore` need directory-aware behavior.
