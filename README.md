
# dotfig


## overview

Dotfig is an app that manages individual config files.  It stores them in a dir
that mirrors the path to the original config file and creates a symlink from the
dotfig dir to the source config dir.  This is similar to how gnu stow works.

The dotfig dir can be commited to git, and checked out on other machines.  This
way configs can be synced across machines.


## commands

### init
`dotfig init PATH`
create $HOME/.dotfig
if PATH doesn't exist:
  create PATH

### list
`dotfig list`
list all managed config files

### store
`dotfig store FILE`
if FILE isn't managed:
  duplicate path to FILE under dotfig root
  mv FILE to root
  symlink FILE back to source
elif FILE is managed and different:
  issue error and do nothing
elif FILE is managed and the same:
  issue notification that they are the same and do nothing

### restore
`dotfig restore FILE`
if FILE doesn't exist:
  make dir and symlink to source
elif FILE is a file and is the same:
  rm file and symlink FILE to config dir
elif FILE is a file and is different:
  stop and issue warning
elif FILE is a symlink to root:
  do nothing, FILE is already setup


## dotfig config file
Stores the location of the dotfig tree location.  It is in toml format,
butdoesn't have the `.toml` extention.

.dotfig
```
-*- mode: toml -*-
root = $HOME/bin/dotfig
```
