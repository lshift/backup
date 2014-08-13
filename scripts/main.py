"""
Usage: main [options] [directories]

"""


#!/usr/bin/python
import smtplib
import configReader
import argparse
import datetime
import os
import subprocess
import os.path as op

from email.mime.text import MIMEText


def main(directory, config, output, stdout=False):
    # Find the changes since last update and write to output.txt or standard
    # output.
    mdFilePath = op.join(op.dirname(op.realpath(__file__)), "md5dir.py")
    mdCommandArgs = ["python", mdFilePath, "-m", directory]
    if not stdout:
        # Read configuration file
        cf = configReader.ConfigReader(config)
        outputFile = open(output, "w+")
        changedFiles = subprocess.check_output(mdCommandArgs)
        outputFile.write(changedFiles)
        outputFile.write(str(datetime.datetime.now()))
        outputFile.close()
        # Send the emails to relevant people.
        emails = cf.emails
        sendEmail(emails, output)
    else:
        subprocess.call(mdCommandArgs)


def getFileContent(name):
    """Returns the content of the file with given name"""
    fp = open(name, 'r')
    content = fp.read()
    fp.close()
    return content


def sendEmail(addrs, fileName):
    """Sends an email to each of the addresses specified by addr with
    the content of the file with fileName."""
    msg = MIMEText(getFileContent(fileName))
    msg['Subject'] = "The content of %s" % fileName
    msg['From'] = "ela@lshift.net"
    msg['To'] = ', '.join(addrs)
    s = smtplib.SMTP('localhost')
    s.sendmail("ela@lshift.net", addrs, msg.as_string())
    s.quit()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dir", default=".", help=str("Directory on which you"
                        " want to perform the file comparison. Note the "
                        "directory needs to have the md5sum already."))
    parser.add_argument("-c", "--config", help=str("The location to the config"
                        " file. By default it's config.txt in the directory to"
                        " be analyzed."))
    parser.add_argument("-o", "--output", help=str("The location of the file "
                        "where you want to store the result of the "
                        "comparison."))
    parser.add_argument("--stdout", action="store_true", help=str("If set the "
                        "output of the comparison is not saved to file but is "
                        "written to standard output. It's pure purspose is "
                        "debugging."))
    args = parser.parse_args()

    # Config file location
    config = args.config if args.config else os.path.join(args.dir,
                                                          "config.txt")
    # Output file
    output = args.output if args.output else os.path.join(args.dir,
                                                          "output.txt")
    # Standard output
    if args.stdout:
        main(args.dir, config, output, stdout=True)
    else:
        main(args.dir, config, output)
        