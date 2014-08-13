import re
class ConfigReader:
	def __init__(self, fileName):
		self.fp = open(fileName, 'r')
		self.emails = self.getEmails()
		self.fp.close()

	def getEmails(self):
		emails = []
		for line in self.fp:
			emails.append(line.strip())
		return emails

	def parseFile(self):
		for line in self.fp:
			if line[:2] == "##":
				line = line.next()
				dict = {}
				patt = re.compile("# (User|Subscribe|Ignore)")
				while line[:2] != "##":
					key = patt.match(line)
					if key:
						line = line.next()
						setting = []
						while line[0] != "#":
							setting.append(line)
							line = line.next()
					dict[key.group(1)] = setting


					




