# Project

The purpose of this project is to create tool which checks for changes in files on the system and inform
the owners of the directories about the changes.

## Using it as a directory comparison tool.
You can use this tool for creating a file with md5 sums for each file present in a chosen directory.
Then use this file for comparing current version of the directory with a previous one. To do this run
the md5dir script with the following command:

 `python scripts/md5dir.py [options] [directories]`

 For first time usage on a directory I recommend to use the "--quiet" so that you don't end up with a
 massive list of added files.

 Standard usage:

 `python scripts/md5dir.py --hashfile=md5sum --ignore=example/config.yaml --verbose --output="compare.txt" dir`

 Add "--time" to see how long it took to run. 