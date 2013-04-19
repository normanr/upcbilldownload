#!/usr/bin/python

import BeautifulSoup
import cookielib
import datetime
import json
import mechanize
import os
import re
import subprocess
import sys
import time
import urllib
import urlparse

# Create .upcbilldownload in your home directory like this:
# { "username": "user@example.com", "passsword": "letmein" }
with open(os.path.expanduser('~/.upcbilldownload')) as fp:
  config = json.load(fp)

if len(sys.argv) > 1:
  os.chdir(sys.argv[1])

# Browser
br = mechanize.Browser()
pdf = mechanize.Browser()

# Browser options
br.set_handle_robots(False)
pdf.set_handle_robots(False)

# Want debugging messages?
def debug():
  br.set_debug_http(True)
  br.set_debug_responses(True)
  pdf.set_debug_http(True)
  pdf.set_debug_responses(True)

cj = mechanize.CookieJar()
br.addheaders = [('User-Agent', 'upcbilldownload/0.1')]
br.set_cookiejar(cj)
pdf.addheaders = br.addheaders
pdf.set_cookiejar(cj)

# Index - Get php session cookie
br.open('https://service.upc.ie/cckservices/myupc/')

# Invoices
br.open('https://service.upc.ie/j_ebpp/ebp/action/invoice.do')

# Login
br.select_form(nr=0)
br.form['username'] = config['username']
br.form['password'] = config['password']

br.submit()

# Prepare form for downloading pdfs
br.select_form(nr=0)
br.form.action = 'https://service.upc.ie/j_ebpp/ebp/action/invoicedetails.do'
br.form.set_all_readonly(False)

# Parse html and download pdfs
html = br.response().read()
soup = BeautifulSoup.BeautifulSoup(html)

current_account = ''

for tr in soup.table('tr'):
  tds = tr('td')

  if len(tds) == 1:
    # Account Number
    current_account = tds[0].string.split()[-1]

  if len(tds) != 4:
    continue

  # Bill ref number, Statement Date, Payment Due Date, Amount to be Paid
  billref = tds[0].a.string.strip()
  statement_date = datetime.datetime.strptime(tds[1].string, '%d/%m/%Y')

  localPdf = 'upc-%s-%s.pdf' % (
      current_account, statement_date.strftime('%Y-%m'))

  if os.path.exists(localPdf):
    continue

  print 'Fetching %s...' % localPdf

  br.form['billref'] = billref

  pdf_data = pdf.open(br.click()).read()

  with open(localPdf, 'wb') as f:
    f.write(pdf_data)

  if 'postprocess' in config:
    subprocess.check_call([config['postprocess'], localPdf])
