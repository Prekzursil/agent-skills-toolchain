#!/bin/sh
# Procedure for no-remote repositories: create remotes first.
git remote add origin git@github.com:example/estate.git
git push -u origin HEAD
