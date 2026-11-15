# Copy files between the store and the host

**Status**: accepted

`dotfig store` copies a host file into the dotfig root, and `dotfig restore`
copies a stored file back to its host path. Both sides stay regular files.
`dotfig list` hashes each pair and shows `✓` when the contents match and `✗`
when they differ or the host copy is missing. A temporary hidden
`dotfig break ID` command replaces an existing managed symlink with a regular
copy so users can migrate from the previous symlink model.

**Considered options**:

- Symlinks (previous): one canonical copy and automatic updates, but edits on
  either side write through to the other and the host is not an independent
  file.
- Copies (chosen): the store and host can differ, `list` reports whether they
  match, and `store` or `restore` decides which side wins. The cost is hashing
  files during `list` and requiring an explicit command to resolve differences.
