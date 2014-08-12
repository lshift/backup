"""
Modified from http://snipplr.com/view/4023/

Usage: md5dir [options] [directories]

Without options it writes an 'md5sum' file in each of the specified directories
and compares it with its previous state. It writes the differences to standard
output.

-3/--mp3
  Enable MP3 mode: for files ending in .mp3, calculate a checksum
  which skips ID3v1 and ID3v2 tags.  This checksum differs from the
  normal one which is compatible with GNU md5sum.  The md5sum file is
  tagged so that md5dir will in future always use MP3 mode for the
  directory.  Consider using mp3md5.py instead, which keeps this
  tag-skipping checksum in the ID3v2 tag as a Unique File ID.

-h/--help
  Output this message then exit.

-o/--output=X
  Write the changes to the file specified as X

-c/--comparefiles
  Compares the two md5sum files specified as arguments.

-t/--twodir
  Creates md5sum files in the two directories specified and compares them.

-q/--quiet
  Does not output the changes. Suitable for initialising a directory.

-i/--ignore=X
  Specifies the YAML file with directories/files to be ignored.

--time
  Outputs the runtime of the program. Development purpose only.

--hashfile=X
  Specify the location of the md5sum. X can be a list if analyzing several
  directories.
"""

#pylint: disable=C0103,R0902,W0106

from getopt import getopt
import md5
import os
import os.path as op
import re
import struct
import sys
import errno
import dictdiff
import yaml
import fnmatch
import timeit


ARGS_DEFAULT = 0
ARGS_HELP = 1


class Md5dir(object):
    """ Md5dir """

    hashfile = "md5sum"  # Default name for checksum file.
    output = None        # By default we output to stdout.
    mp3mode = False      # Whether to use tag-skipping checksum for MP3s.
    comparefiles = False
    twodir = False
    quiet = False        # By default the result of comparison is outputed.
    ignores = []         # By default don't ignore any files.
    time = False         # By default don't compute the runtime
    hashfiles = []
    beginning = None

    # Regular expression for lines in GNU md5sum file
    md5line = re.compile(r"^([0-9a-f]{32}) [\ \*](.*)$")


    def comparemd5dict(self, d1, d2, root):
        """ Compares two md5sum files. """
        diff = dictdiff.DictDiffer(d2, d1)
        added = diff.added()
        deleted = diff.removed()
        changed = diff.changed()
        unchanged = diff.unchanged()
        self.outputFileList("ADDED", added)
        self.outputFileList("DELETED", deleted)
        self.outputFileList("CHANGED", changed)
        self.log("LOCATION: %s" % root)
        self.log("STATUS: confirmed %d added %d deleted %d changed %d" % (
                 len(unchanged), len(added), len(deleted), len(changed)))


    def outputFileList(self, name, filelist):
        """ log files to output """
        [self.log("%s: %s" % (name, fname)) for fname in filelist
            if not self.ignore(fname)]


    def log(self, msg):
        """ Writes given message to the relevant output."""
        if self.quiet:
            return
        elif self.output:
            self.output.write(msg + "\n")
        else:
            print msg


    def getDictionary(self, filename):
        """ Converts the md5sum file into a dictionary of filename -> md5sum """
        d = {}
        # If file doesn't exists we return an empty dictionary.
        if not op.isfile(filename):
            return d
        with open(filename) as f:
            for line in f:
                match = self.md5line.match(line.rstrip(""))
                # Skip non-md5sum lines
                if not match:
                    continue
                d[match.group(2)] = match.group(1)

        return d


    def ignore(self, filename):
        """ Ignore when at least one matches pattern """
        return any([fnmatch.fnmatch(filename, i) for i in self.ignores])


    def masterList(self, start):
        """Return a list of files relative to start directory."""
        flist = []
        oldcwd = os.getcwd()
        os.chdir(start)
        # Collect all files under start (follow directory symbolic links).
        for root, _, files in os.walk(".", followlinks=True):
            if self.ignore(root):
                continue
            for fname in files:
                fname = op.join(root[2:], fname)
                if self.ignore(fname):
                    continue
                # Take care of symbolic links pointing to a file.
                try:
                    if op.islink(fname):
                        # We are using this command to check whether the link
                        # is not broken.
                        os.stat(fname)
                        fname = os.readlink(fname)
                        if not op.isabs(fname):
                            fname = op.join(root[2:], fname)
                    flist.append(fname)
                except OSError, e:
                    if e.errno == errno.ENOENT:
                        self.log('BROKEN: %s' % fname)
                    else:
                        raise e
        os.chdir(oldcwd)
        return flist


    def makesums(self, root):
        """Creates an md5sum file for the given directory and returns the
        dictionary."""
        checksums = {}
        for fname in self.masterList(root):
            newhash = self.calcsum(op.join(root, fname))
            if newhash != -1:
                checksums[fname] = newhash
        return checksums


    def calcsum(self, filepath):
        """Return md5 checksum for a file. Uses the tag-skipping algorithm
        for .mp3 files if in mp3mode."""
        if self.mp3mode and filepath.endswith(".mp3"):
            return self.calculateUID(filepath)

        h = md5.new()
        try:
            f = open(filepath, "rb")
            s = f.read(1048576)
            while s != "":
                h.update(s)
                s = f.read(1048576)
            f.close()
            return h.hexdigest()
        except IOError:
            self.log("Can't open %s" % filepath)
            return -1

    def compareFiles(self):
        """ Compare two md5sum files. """
        if len(args) != 2 or not op.isfile(args[0]) or not op.isfile(args[1]):
            return False

        self.comparemd5dict(self.getDictionary(args[0]),
                            self.getDictionary(args[1]),
                            op.abspath(op.dirname(args[0])))
        return True


    def compareDirs(self):
        """ Compare two directories. """
        if len(args) != 2 or not op.isdir(args[0]) or not op.isdir(args[1]):
            return False

        sums1 = self.makesums(args[0])
        sums2 = self.makesums(args[1])
        self.writesums(self.hashfile, args[0], sums1.iteritems())
        self.writesums(self.hashfile, args[1], sums2.iteritems())
        self.comparemd5dict(sums1, sums2, op.abspath(args[0]))
        return True


    def analyzeDirs(self):
        """ Analyze the given directories. """
        if self.hashfiles != [] and len(self.hashfiles) != len(args):
            return False

        # Treat each argument separately
        for index, start in enumerate(args):
            if not op.isdir(start):
                print "Argument %s is not a directory" % start
                continue
            if self.hashfiles != []:
                hashfile = op.abspath(self.hashfiles[index])
                sums1 = self.getDictionary(self.hashfile)
            else:
                sums1 = self.getDictionary(op.join(start, hashfile))
            sums2 = self.makesums(start)
            self.writesums(self.hashfile, start, sums2.iteritems())
            self.comparemd5dict(sums1, sums2, op.abspath(args[0]))

        return True


    def parseArgs(self, options):
        """ Parse command-line options """
        for opt, value in options:
            if opt in ["-3", "--mp3"]:
                self.mp3mode = True
            elif opt in ["-o", "--output"]:
                self.output = open(value, "w")
            elif opt in ["-h", "--help"]:
                return ARGS_HELP
            elif opt in ["-c", "--comparefiles"]:
                self.comparefiles = True
            elif opt in ["-t", "--twodir"]:
                self.twodir = True
            elif opt in ["-q", "--quiet"]:
                self.quiet = True
            elif opt in ["-i", "--ignore"]:
                self.ignores = self.getignores(value)
            elif opt in ["--time"]:
                self.time = True
                self.beginning = timeit.default_timer()
            elif opt in ["--hashfile"]:
                self.hashfiles = value.split(",")
                self.hashfile = op.abspath(self.hashfiles[0])

        return ARGS_DEFAULT


    @staticmethod
    def getignores(filepath):
        """ get list of ignores """
        with open(filepath, 'r') as f:
            doc = yaml.load(f)
        return doc["ignore"]


    @staticmethod
    def calculateUID(filepath):
        """Calculate MD5 for an MP3 excluding ID3v1 and ID3v2 tags if
        present. See www.id3.org for tag format specifications."""
        f = open(filepath, "rb")
        # Detect ID3v1 tag if present
        finish = os.stat(filepath).st_size
        f.seek(-128, 2)
        if f.read(3) == "TAG":
            finish -= 128
        # ID3 at the start marks ID3v2 tag (0-2)
        f.seek(0)
        start = f.tell()
        if f.read(3) == "ID3":
            # Bytes w major/minor version (3-4)
            # Flags byte (5)
            flags = struct.unpack("B", f.read(1))[0]
            # Flat bit 4 means footer is present (10 bytes)
            footer = flags & (1 << 4)
            # Size of tag body synchsafe integer (6-9)
            bs = struct.unpack("BBBB", f.read(4))
            bodysize = (bs[0] << 21) + (bs[1] << 14) + (bs[2] << 7) + bs[3]
            # Seek to end of ID3v2 tag
            f.seek(bodysize, 1)
            if footer:
                f.seek(10, 1)
            # Start of rest of the file
            start = f.tell()
        # Calculate MD5 using stuff between tags
        f.seek(start)
        h = md5.new()
        h.update(f.read(finish - start))
        f.close()
        return h.hexdigest()


    @staticmethod
    def writesums(hashfile, root, checksums):
        """Given a list of (filename,md5) in checksums, write them to
        filepath in md5sum format sorted by filename, with a #md5dir
        header"""
        pathname = hashfile if op.isabs(hashfile) else op.join(root, hashfile)
        with open(pathname, "w") as f:
            f.write("#md5dir %s\n" % root)
            for fname, md5sum in sorted(checksums, key=lambda x: x[0]):
                f.write("%s  %s\n" % (md5sum, fname))


if __name__ == "__main__":
    optlist, args = getopt(
        sys.argv[1:], "3cf:hlmnqru",
        ["mp3", "output=", "comparefiles", "twodir", "help", "quiet",
         "ignore=", "time", "hashfile="])

    md5dir = Md5dir()
    if md5dir.parseArgs(optlist) == ARGS_HELP:
        print __doc__
        sys.exit(0)
    elif len(args) == 0:
        print "Exiting because no directories given (use -h for help)"
        sys.exit(1)
    elif md5dir.comparefiles:
        if not md5dir.compareFiles():
            print "Exiting because two file pathnames expected."
            sys.exit(1)
    elif md5dir.twodir:
        if not md5dir.compareDirs():
            print "Exiting because two directory pathnames expected."
            sys.exit(1)
    else:
        if not md5dir.analyzeDirs():
            print str("The number of hashfiles is different to the number of "
                      "directories.")
            sys.exit(1)

    if md5dir.output:
        md5dir.output.close()

    if md5dir.time:
        total = timeit.default_timer() - md5dir.beginning
        print "%.5f" % total
