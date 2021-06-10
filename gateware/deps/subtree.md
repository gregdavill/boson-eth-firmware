# Subtree Guide
https://www.atlassian.com/git/tutorials/git-subtree

## Tutorial 
### Add subtree
```
git remote add -f <remote name> <remote url>
git subtree add --prefix <local dir> <remote name> <branch> --squash
```

### Pull Subtree
```
git fetch <remote name> <branch>
git subtree pull --prefix <local dir> <remote name> <branch> --squash
```

## Example
### Add
```
git remote add -f enjoy-digital-litex https://github.com/enjoy-digital/litex.git
git subtree add --prefix gateware/deps/litex enjoy-digital-litex master --squash
```