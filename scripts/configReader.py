#pylint: disable=C0103,C0111

import re

class ConfigReader(object):
    """ Read emails from config file on instantiation """

    def __init__(self, fileName):
        self.fileName = fileName
        self.emails = self.getEmails()

    def getEmails(self):
        emails = []
        with open(self.fileName, 'r') as fp:
            for line in fp:
                emails.append(line.strip())

        return emails

    def parseFile(self):
        patt = re.compile("# (User|Subscribe|Ignore)")

        with open(self.fileName, 'r') as fp:
            for line in fp:
                if line[:2] != "##":
                    continue

                line = line.next()
                mydict = {}
                while line[:2] != "##":
                    key = patt.match(line)
                    if key:
                        line = line.next()
                        setting = []
                        while line[0] != "#":
                            setting.append(line)
                            line = line.next()
                    mydict[key.group(1)] = setting
