#!/bin/sh
# ASSERTION: Linux x POSIX sh must print a JSON status and exit 0 on this host.
# This is the live RUN cell on a Linux box whose /bin/sh exists.
echo '{"id":"linux__posix-sh","os":"Linux","shell":"POSIX sh","status":"RUN","reason":"host /bin/sh executed this probe"}'
echo SUCCESS:linux-posix-sh
exit 0
