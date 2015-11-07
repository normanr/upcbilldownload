#!/usr/bin/python

import BeautifulSoup
import datetime
import getpass
import json
import mechanize
import os
import subprocess
import sys
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

def open_with_login(browser, url, data=None):
  result = browser.open(url, data)
  while '/login/' in browser.geturl():
    response_url = urlparse.urlparse(browser.geturl())
    qs = urlparse.parse_qs(response_url.query)

    if qs['TAM_OP'][0] == 'login':
      # Login
      browser.select_form(nr=0)
      browser.form['username'] = config['username']
      browser.form['password'] = config['password']

      browser.submit()

    elif qs['TAM_OP'][0] == 'login_success':
      result = browser.open(url, data)
      continue

    else:
      raise StandardError('Login failed: %s' % browser.geturl())
  return result

# Index - Get php session cookie
open_with_login(br, 'https://www.virginmedia.ie/myvirginmedia/portal/')

# Parse html for Account Number
html = br.response().read()
soup = BeautifulSoup.BeautifulSoup(html)

# Account Number
current_account_attrs = {'sorrisoid':"simple-form_customer_id.element.value"}
current_account = soup.find('span', attrs=current_account_attrs).string

# My Bills
open_with_login(br, br.click_link(predicate=lambda l: dict(l.attrs).get('id') == 'menu.billing.bill'))

# Parse html for billing periods
html = br.response().read()
soup = BeautifulSoup.BeautifulSoup(html)

# Billing periods
list_billing_periods_attrs = {'name':'list-billing_periods'}
list_billing_periods = soup.find('select', attrs=list_billing_periods_attrs)

# Prepare url for billing period select post
submit_form = soup.find('form', attrs={'method':'post'})
url = urlparse.urljoin(br.geturl(), submit_form.get('action'))
url += '&_internalMovement=V:CHOICE:link.update_MYUPC_bill.summary'

def fetchPdf(billing_period):
  statement_date = datetime.datetime.strptime(billing_period, '%Y%m%d')

  localPdf = 'upc-%s-%s.pdf' % (
      current_account, statement_date.strftime('%Y-%m'))

  if os.path.exists(localPdf):
    return

  print 'Fetching %s...' % localPdf

  data = urllib.urlencode({'list-billing_periods':billing_period})
  open_with_login(br, url, data=data)

  pdf_click = br.click_link(text='Bill as PDF')
  tries = 0
  while True:
    pdf_response = open_with_login(pdf, pdf_click)
    print pdf_response.info()['content-type']

    if pdf_response.info()['content-type'] == 'application/pdf':
      break

    tries += 1
    if tries > 3:
      print 'Skipping %s, exhausted retries.' % localPdf
      return

  pdf_data = pdf_response.read()
  with open(localPdf, 'wb') as f:
    f.write(pdf_data)

  if 'postprocess' in config:
    subprocess.check_call([config['postprocess'], localPdf])

for billing_period_option in list_billing_periods.findAll('option'):
  fetchPdf(billing_period_option.get('value'))
