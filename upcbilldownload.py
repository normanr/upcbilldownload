#!/usr/bin/python

import BeautifulSoup
import cookielib
import datetime
import getpass
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

if not config.get('password'):
  config['password'] = getpass.getpass()

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
br.addheaders = [('User-Agent', 'upcbilldownload/0.3')]
br.set_cookiejar(cj)
pdf.addheaders = br.addheaders
pdf.set_cookiejar(cj)

# Index - Get php session cookie
br.open('https://www.virginmedia.ie/myvirginmedia/portal/')

# Login
br.select_form(nr=0)
br.form['username'] = config['username']
br.form['password'] = config['password']

br.submit()

# Parse html for Account Number
html = br.response().read()
soup = BeautifulSoup.BeautifulSoup(html)

# Account Number
current_account_attrs = {'sorrisoid':"simple-form_customer_id.element.value"}
current_account = soup.find('span', attrs=current_account_attrs).string

# My Bills
br.follow_link(predicate=lambda l: dict(l.attrs).get('id') == 'menu.billing.bill')

# Parse html for billing periods
html = br.response().read()
soup = BeautifulSoup.BeautifulSoup(html)

# Billing periods
list_billing_periods_attrs = {'name':'list-billing_periods'}
list_billing_periods = soup.find('select', attrs=list_billing_periods_attrs)

# Prepare url for billing period select post
submit_form = soup.find('form', attrs={'method':'post'})
url = submit_form.get('action')
url += '&_internalMovement=V:CHOICE:link.update_MYUPC_bill.summary';

for billing_period_option in list_billing_periods.findAll('option'):
  billing_period = billing_period_option.get('value')
  statement_date = datetime.datetime.strptime(billing_period, '%Y%m%d')

  localPdf = 'upc-%s-%s.pdf' % (
      current_account, statement_date.strftime('%Y-%m'))

  if os.path.exists(localPdf):
    continue

  print 'Fetching %s...' % localPdf

  data = urllib.urlencode({'list-billing_periods':billing_period})
  br.open(url, data=data)

  pdf_click = br.click_link(text='Bill as PDF')
  pdf_response = pdf.open(pdf_click)

  if pdf_response.info()['content-type'] != 'application/pdf':
    print 'Skipping %s, not available.' % localPdf
    continue

  pdf_data = pdf_response.read()
  with open(localPdf, 'wb') as f:
    f.write(pdf_data)

  if 'postprocess' in config:
    subprocess.check_call([config['postprocess'], localPdf])
