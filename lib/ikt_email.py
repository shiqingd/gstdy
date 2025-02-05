#!/usr/bin/env python3
'''
Convenience class to send emails

@author: pjnozisk


'''

import sys, os
from lib.dry_run import dryrunnable

class Email(object):

	"""
	Email envelope
	"""
	def __init__(self, _to, _from, _subject, _body, _cc=[], _attachments=[], _bodytype='plain'):
		"""
		:ivar _to:  List f Recipient email addresses
		:vartype _to: list
		:ivar _fron: Sender email address
		:vartype _from: str
		:ivar _subject: Subject line
		:vartype _subject: str
		:ivar _body: bosy of message
		:vartype _body: str
		:ivar _attachments: list of files to attach
		:vartype _attachments: list
		"""
		import smtplib
		self._to = _to
		self._from = _from
		self._subject = _subject
		self._body = _body
		self._bodytype = _bodytype
		self._cc = _cc
		self._attachments = _attachments
# Open relay server no longer works outside lab networks
#		self.server = smtplib.SMTP('smtp.intel.com')
		self.server = smtplib.SMTP('smtpauth.intel.com', port=587)
		self.server.starttls()
		# FIXME - this "plain" auth token is bound to 'sys_oak'
		# need logic here to generate per user
		self.server.docmd("AUTH PLAIN", 'AHN5c19vYWsAb3Rja2VybmVsMSE=')


	@dryrunnable()
	def send(self):
		import mimetypes
		from email import encoders
		from email.mime.base import MIMEBase
		from email.mime.text import MIMEText
		from email.mime.multipart import MIMEMultipart
		parts = []
		for filename in self._attachments:
			mtype , encoding = mimetypes.guess_type(filename)
			print(mtype , encoding)
			if mtype:
				mtypelist = mtype.split('/')
			else:
				print("Mime type of {} cannt be determined, Skipping".format(filename))
				continue
			print(mtypelist)
			part = MIMEBase(mtypelist[0], mtypelist[1], name=os.path.basename(filename))
			part["Content-Description"] = os.path.basename(filename)
			with open(filename, "rb") as attachment:
				part.set_payload(attachment.read())
			if mtypelist[0]  != 'text':
				encoders.encode_base64(part)
			part.add_header( "Contect-Disposition" , "attachment ; filename={}".format(os.path.basename(filename)) )
			parts.append(part)
		if parts:
			msg = MIMEMultipart()
			msg.attach(MIMEText(self._body, self._bodytype))
			for part in parts:
				msg.attach(part)
		else:
			msg = MIMEText(self._body, self._bodytype)
		msg["Subject"] = self._subject
		msg["From"] = self._from
		msg["To"] = ",".join(self._to)
		for addr in self._cc:
			if addr in self._to:
				self._cc.remove(addr)
		msg["Cc"] = ",".join(self._cc)

		self.server.sendmail(self._from, self._to, msg.as_string())

	def __repr__(self):
		return "Email from {} to {}".format(str(self._from),str(self._to))

