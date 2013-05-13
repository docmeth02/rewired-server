#!/bin/bash
if ! which git >/dev/null; then
   exit 0
fi
branch=$(git branch | sed -n -e 's/^\* \(.*\)/\1/p')
commitid=$(git rev-parse HEAD)
shortid=${commitid: -10}
version=(git-$branch-$shortid)
echo $version > includes/.gitversion
exit 1
