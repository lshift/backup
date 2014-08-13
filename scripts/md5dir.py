"""
Modified from http://snipplr.com/view/4023/

Without options it writes an 'md5sum' file in each of the specified directories
and compares it with its previous state. It writes the differences to standard
output.
"""

#pylint: disable=C0103,R0902,W0106

import md5
import os
import os.path as op
import re
import struct
import sys
import errno
import yaml
import fnmatch
import tempfile
import shutil
import subprocess
import argparse

mp3_help = """Enable MP3 mode: for files ending in .mp3, calculate a checksum
  which skips ID3v1 and ID3v2 tags.  This checksum differs from the
  normal one which is compatible with GNU md5sum.  The md5sum file is
  tagged so that md5dir will in future always use MP3 mode for the
  directory.  Consider using mp3md5.py instead, which keeps this
  tag-skipping checksum in the ID3v2 tag as a Unique File ID."""
output_help = """Writes the changes to the specified file instead of the
  standard output."""
compare_help = """Compares the two md5sum files given as arguments."""
twodir_help = """Compares the two directories given as arguments. Creates the
  hashfiles for the directories only if their location is explicitly
  specified."""
suppress_help = """When set the program does not output the changes. Suitable
  for initialising a directory."""
ignore_help = """Specifies the YAML file with directories/files to be
  ignored."""
verbose_help = """When set the program will output progress status. By default
  it will ouput a message every 1000 files, this can be changed to any number
  by giving the optional parameter."""
dirs_help = """A list of directories to perform the analysis for. By default
  the program will create/read from md5sum inside each directory. This can be
  changed by adding an additional argument specifying the path in which the
  file should be found. Therefore each item of the list can bo of the form
  dirpath[:filepath]."""
description_msg = """By default it checks for differences between the current
  state of each directory specified as arguments and its previous version saved
  in the 'md5sum' files, subsequently updating the files. The 'md5sum' file
  stores the md5 checksums for each file in the directory and its
  subdirectories."""


class Md5dir(object):
    """ Md5dir """

    hashfile_name = "md5sum"     # Default name for checksum file.
    ignores = []                # By default don't ignore any files.
    dirs = []

    # Regular expression for lines in GNU md5sum file
    md5line = re.compile(r"^([0-9a-f]{32}) [\ \*](.*)$")

    def log(self, msg):
        """Writes given message to the relevant output."""
        if not self.suppress_changes:
            self.output.write(msg + "\n")

    def ignore(self, filename):
        """Ignore when at least one matches found."""
        return any([fnmatch.fnmatch(filename, i) for i in self.ignores])

    def get_dict(self, filename):
        """Converts the md5sum file into a dictionary of filename -> md5sum."""
        # If file doesn't exists we return an empty dictionary.
        if not op.isfile(filename):
            return
        with open(filename) as f:
            for line in f:
                match = self.md5line.match(line.rstrip(""))
                # Skip non-md5sum lines
                if not match:
                    continue
                yield {"file": match.group(2),
                       "md5": match.group(1)}

    def master_list(self, start):
        """Return a list of files relative to start directory."""
        # Collect all files under start (follow directory symbolic links).
        for root, dirs, files in os.walk(start, followlinks=True):
            if self.ignore(root):
                continue
            for fname in files:
                fname = op.join(root, fname)
                if self.ignore(fname):
                    continue
                try:
                    if op.islink(fname):
                        # We are using this command to check whether the link
                        # is not broken.
                        os.stat(fname)
                        fname = os.readlink(fname)
                        # os.readlink() may or maynot return absolute path. If
                        if not op.isabs(fname):
                            fname = op.join(root, fname)
                    yield op.relpath(fname, start)
                except OSError, e:
                    if e.errno == errno.ENOENT:
                        self.log('BROKEN: %s' % fname)
                    else:
                        raise e

    def make_sums(self, root, hashfile):
        """Creates an md5sum file for the given directory
        in the location specified."""
        self.progress("Creating md5sum file.")
        with open(hashfile, "w") as fp:
            for index, fname in enumerate(self.master_list(root)):
                if self.verbose and index % self.verbose == 0:
                    self.progress("Computing md5, %d files analyzed." % index)
                newhash = self.calc_sum(op.join(root, fname))
                if newhash != -1:
                    fp.write("%s  %s\n" % (newhash, fname))
        self.progress("Sorting the md5sum file.")
        subprocess.call(["sort", "-k", "2", "-o", hashfile, hashfile])
        self.progress("Finished sorting the md5sum file.")

    def calc_sum(self, filepath):
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
            self.log("BROKEN: %s" % filepath)
            return -1

    def compare(self, path1, path2, dirpath):
        """Compare two md5sum files and writes the differences to the
        relevant output."""
        # Helper functions for iterating, which returns -1 if there
        # are no elements left.
        def neckst(item):
            return next(item, -1)

        self.progress("Comparing the md5sum files.")
        confirmed = 0
        changed = 0
        added = 0
        deleted = 0
        old = self.get_dict(path1)
        new = self.get_dict(path2)
        dictold = neckst(old)
        dictnew = neckst(new)
        self.log("Analysis of %s" % dirpath)
        while True:
            if dictold == -1 or dictnew == -1:
                break
            # Match. Both proceed to next element.
            pathold = dictold["file"]
            pathnew = dictnew["file"]
            if self.ignore(pathold):
                dictold = neckst(old)
                continue
            if self.ignore(pathnew):
                dictnew = neckst(new)
                continue
            if pathold == pathnew:
                if dictold["md5"] != dictnew["md5"]:
                    self.log("CHANGED: %s" % pathold)
                    changed += 1
                else:
                    confirmed += 1
                dictold = neckst(old)
                dictnew = neckst(new)
            # File got deleted. Old proceed to next element.
            elif pathold < pathnew:
                self.log("DELETED: %s" % pathold)
                deleted += 1
                dictold = neckst(old)
            # File got added. New proceed to next element.
            else:
                self.log("ADDED: %s" % pathnew)
                added += 1
                dictnew = neckst(new)

        if dictold == -1:
            dictnew = neckst(new)
            while dictnew != -1:
                self.log("ADDED: %s" % dictnew["file"])
                added += 1
                dictnew = neckst(new)
        elif dictnew == -1:
            dictold = neckst(old)
            while dictold != -1:
                self.log("ADDED: %s" % dictold["file"])
                added += 1
                dictold = neckst(old)
        self.log("STATUS: confirmed %d added %d deleted %d changed %d" % (
            confirmed, added, deleted, changed))

    # TODO: Maybe with class easier way to do the counts.
    def progress(self, message):
        """If the verbose flag is set output progress message."""
        if self.verbose:
            print "PROGRESS: %s" % message

    def add_dirs(self, dirs):
        for item in dirs:
            pair = item.split(":")
            directory = {"path": op.abspath(pair[0])}
            directory["file"] = pair[1] if len(pair) == 2 else None
            self.dirs.append(directory)

    def analyze_dirs(self):
        # Treat each argument separately
            for arg in self.dirs:
                start = arg["path"]
                if not op.isdir(start):
                    print "Argument %s is not a directory" % start
                    continue
                if arg["file"]:
                    hashfile = op.abspath(arg["file"])
                else:
                    hashfile = op.join(op.abspath(start), self.hashfile_name)

                # Copy the content of md5sum into a temporary file.
                file1 = tempfile.NamedTemporaryFile(delete=False)
                if op.isfile(hashfile):
                    with open(hashfile, "r") as fp:
                        shutil.copyfileobj(fp, file1)
                file1.close()
                # Update the hashfile.
                self.make_sums(start, hashfile)
                # Compare the files.
                self.compare(file1.name, hashfile, start)
                os.unlink(file1.name)

    def two_dir_comp(self):
        arg1 = self.dirs[0]
        arg2 = self.dirs[1]
        if not op.isdir(arg1["path"]) or not op.isdir(arg2["path"]):
            return False
        file1 = arg1["file"] or \
            tempfile.NamedTemporaryFile(delete=False).name
        file2 = arg2["file"] or \
            tempfile.NamedTemporaryFile(delete=False).name
        self.make_sums(arg1["path"], file1)
        self.make_sums(arg2["path"], file2)
        self.compare(file1, file2, "%s, %s" % (arg1["path"], arg2["path"]))
        return True

    def set_ignores(self, filepath):
        if not filepath:
            self.ignores = []
            return
        with open(filepath, 'r') as f:
            doc = yaml.load(f)
        self.ignores = doc["ignore"]

    @staticmethod
    def calculateUID(filepath):
        """Calculate MD5 for an MP3 excluding ID3v1 and ID3v2 tags if
        present. See www.id3.org for tag format specifications.
        Function entirely taken from http://snipplr.com/view/4023/ and
        not tested."""
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


if __name__ == "__main__":
    md5dir = Md5dir()

    # Parse command-line options
    parser = argparse.ArgumentParser(description=description_msg)
    parser.add_argument("-c", "--comparefiles", nargs=2, help=compare_help)
    parser.add_argument("-3", "--mp3", action="store_true", help=mp3_help)
    parser.add_argument("-o", "--output", type=argparse.FileType("w"),
                        default=sys.stdout, help=output_help)
    parser.add_argument("-t", "--twodir", action="store_true",
                        help=twodir_help)
    parser.add_argument("--suppresschanges", action="store_true",
                        help=suppress_help)
    parser.add_argument("-v", "--verbose", nargs="?", const=1000, type=int,
                        help=verbose_help)
    parser.add_argument("dirs", nargs="*", help=dirs_help)
    parser.add_argument("-i", "--ignore")

    args = parser.parse_args()

    md5dir.output = args.output
    md5dir.mp3mode = args.mp3
    md5dir.suppress_changes = args.suppresschanges
    md5dir.verbose = args.verbose

    # Save files and directories to ignore.
    md5dir.set_ignores(args.ignore)

    # Compare two md5sum files.
    if args.comparefiles:
        file1 = op.abspath(args.comparefiles[0])
        file2 = op.abspath(args.comparefiles[1])
        if not op.isfile(file1) or not op.isfile(file2):
            print "Exiting because the arguments are not files."
            sys.exit(0)
        md5dir.compare(file1, file2, "%s, %s" % (file1, file2))

    # All other options use the dirs command line argument.
    else:
        md5dir.add_dirs(args.dirs)

        # Compare two directories
        if args.twodir:
            if len(md5dir.dirs) != 2:
                print "Two arguments expected."
                sys.exit(0)

            if not md5dir.two_dir_comp():
                print "Exiting because arguments are not directory pathnames."
                sys.exit()

        # Analyze the given directories.
        else:
            md5dir.analyze_dirs()
