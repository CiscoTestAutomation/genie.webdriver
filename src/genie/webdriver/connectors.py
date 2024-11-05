from importlib import import_module

from selenium import webdriver

from pyats.connections import BaseConnection

from string import Template

import logging

import requests

import selenium

import random

import json

import os

log = logging.getLogger(os.path.basename(__file__))
log.setLevel(logging.INFO)

selenium_box_url = "https://seleniumbox.cisco.com/wd/hub"

# REST API End point to get browser details.
selenium_box_browser_details = "https://seleniumbox.cisco.com/e34/" \
                               "api/browser/details?name=$browser"

# Change this to set the last n browsers
browser_limit = -3

browsers = ['chrome', 'firefox']


class WebDriverConnector(BaseConnection):

    def __init__(self, *args, **kwargs):
        '''__init__

        instantiate a single connection instance.
        '''

        # instantiate parent BaseConnection
        super().__init__(*args, **kwargs)

        self.driver = None

    def connect(self):

        # do nothing if already connected
        if self.connected:
            return

        # get all connection information
        connection_info = self.connection_info.copy()

        # remove credentials block if present
        credentials = connection_info.pop('credentials', None)
        browser_name = None
        browser_version = None
        driver = None
        # rename ip -> host, cast to str type
        try:
            driver_name = connection_info.pop('driver')
            if 'any' == str(driver_name).lower():
                driver_name = random.choice(browsers)
                driver = getattr(webdriver, driver_name.title())
            else:
                driver = getattr(webdriver, driver_name.title())
            browser_name = str(driver_name)
        except KeyError:
            log.info('Missing driver: definition in YAML connection section')
        except AttributeError:
            log.info('No such driver type: %s' % driver)

        # remove class
        connection_info.pop('class')

        # check if 'token' is passed to connect()
        # if passed, add to connection_info
        try:
            token = connection_info['token']
            if token:
                version = connection_info['version']
                supported_browsers = WebDriverConnector.__supported_browsers__()
                log.info(supported_browsers)
                if 'any' == version.lower():
                    browser_version = random.choice(supported_browsers[
                                                        browser_name]["versions"])
                else:
                    browser_version = version
            log.info(f"Chosen Browser Name : {browser_name}")
            log.info(f"Chosen Browser version : {browser_version}")
            if browser_name and browser_version:
                if selenium.__version__ == "3.141.0":
                    self.driver = webdriver.Remote(desired_capabilities={
                        "browserName": browser_name,
                        "e34:token": token,
                        "e34:video": True,
                        "acceptInsecureCerts": True,
                        "e34:l_testName": connection_info['testname'],
                        "e34:per_test_timeout_ms": 1800000,
                        "version": str(browser_version)},
                        command_executor=selenium_box_url)
        except KeyError:
            log.info("Token not found.")
            # check if 'service' and 'options' is passed to connect()
            # if passed, add to connection_info
            if hasattr(self, 'service'):
                connection_info['service'] = self.service
            if hasattr(self, 'options'):
                connection_info['options'] = self.options
            elif 'options' in connection_info:
                # derive 'options' from testbed yaml
                connection_options = connection_info.pop('options')
                options = import_module(f"selenium.webdriver.{driver_name.lower()}.options")
                connect_options = options.Options()
                for k, v in connection_options.items():
                    setattr(connect_options, k, v)
                connection_info['options'] = connect_options

            # create class
            self.driver = driver(**connection_info)

    def disconnect(self):
        self.driver.quit()

    @property
    def connected(self):
        try:
            return bool(self.driver.title) or True
        except Exception:
            return False

    def __getattr__(self, attr):
        # redirect get attribute to self.driver
        if hasattr(self.driver, attr):
            return getattr(self.driver, attr)
        else:
            raise AttributeError("'%s' object has no attribute '%s"
                                 % (type(self).__name__, attr))

    def __dir__(self):
        return sorted(super().__dir__() + dir(self.driver))

    @property
    def execute(self):
        # chain this execute to driver's execute
        return self.driver.execute

    def configure(self, *args, **kwargs):
        raise RuntimeError("'%s' class does not support configure command"
                           % type(self).__name__)

    @staticmethod
    def __supported_browsers__():
        """
        constructs
         chrome:
            versions: ['83', '86', '88']
         firefox:
            versions: ['77', '82', '85']
         MicrosoftEdge:
            versions: ['94', '95', '96']
        :returns: Latest supported browsers from seleniumbox
        """
        url = Template(selenium_box_browser_details)
        supported_browsers = dict()
        supported_browsers.update({'chrome': {'versions': list()}})
        supported_browsers.update({'firefox': {'versions': list()}})
        supported_browsers.update({'edge': {'versions': list()}})
        try:
            for browser in supported_browsers.keys():
                browser_versions = requests.get(
                    url.substitute(browser=browser))
                result = json.loads(browser_versions.text)
                browser_version_lst = result['tags']
                supported_browsers[browser].update(
                    {'versions': sorted([int(browser_version[:browser_version.find('.')])
                                         for browser_version in browser_version_lst])[browser_limit:]})
        except Exception as e:
            supported_browsers = None
            log.error("Connection Failed: seleniumbox.cisco.com")

        return supported_browsers
