import json

from django.conf import settings
from django.core.cache import cache

import mock
from nose.tools import eq_
from pyquery import PyQuery as pq

import amo
import amo.tests
from amo.urlresolvers import reverse


class Test404(amo.tests.TestCase):
    fixtures = ['base/users', 'webapps/337141-steamcube']

    def _test_404(self, url):
        r = self.client.get(url, follow=True)
        eq_(r.status_code, 404)
        self.assertTemplateUsed(r, 'site/404.html')
        return r

    def test_404(self):
        r = self._test_404('/xxx')
        eq_(pq(r.content)('#site-header .logo').text(), 'Firefox Marketplace')

    def test_404_devhub(self):
        # TODO: Remove log-in bit when we remove `request.can_view_consumer`.
        assert self.client.login(username='steamcube@mozilla.com',
                                 password='password')
        r = self._test_404('/developers/xxx')
        eq_(pq(r.content)('#site-header .logo').text(),
            'Firefox Marketplace Developers')

    def test_404_consumer_legacy(self):
        r = self._test_404('/xxx')
        eq_(pq(r.content)('#site-header .logo').text(), 'Firefox Marketplace')

    def test_404_consumer(self):
        # TODO: Remove log-in bit when we remove `request.can_view_consumer`.
        assert self.client.login(username='steamcube@mozilla.com',
                                 password='password')
        r = self._test_404('/xxx')
        eq_(pq(r.content)('#site-header .logo').text(), 'Firefox Marketplace')


class TestManifest(amo.tests.TestCase):

    def test_manifest(self):
        response = self.client.get(reverse('manifest.webapp'))
        eq_(response.status_code, 200)
        eq_(response['Content-Type'], 'application/x-web-app-manifest+json')
        content = json.loads(response.content)
        eq_(content['name'], 'Firefox Marketplace')
        eq_(content['default_locale'], 'en-US')
        url = reverse('manifest.webapp')
        assert 'en-US' not in url and 'firefox' not in url

    @mock.patch.object(settings, 'WEBAPP_MANIFEST_NAME', 'Mozilla Fruitstand')
    def test_manifest_name(self):
        response = self.client.get(reverse('manifest.webapp'))
        eq_(response.status_code, 200)
        content = json.loads(response.content)
        eq_(content['name'], 'Mozilla Fruitstand')


class TestMozmarketJS(amo.tests.TestCase):

    def setUp(self):
        cache.clear()

    def render(self):
        return self.client.get(reverse('site.mozmarket_js'))

    @mock.patch.object(settings, 'SITE_URL', 'https://secure-mkt.com/')
    @mock.patch.object(settings, 'MINIFY_MOZMARKET', False)
    def test_render(self):
        resp = self.render()
        self.assertContains(resp, "var server = 'https://secure-mkt.com/'")
        eq_(resp['Content-Type'], 'text/javascript')

    @mock.patch.object(settings, 'SITE_URL', 'https://secure-mkt.com/')
    @mock.patch.object(settings, 'MINIFY_MOZMARKET', True)
    def test_minify(self):
        resp = self.render()
        # Check for no space after equal sign.
        self.assertContains(resp, '="https://secure-mkt.com/"')

    @mock.patch.object(settings, 'MINIFY_MOZMARKET', True)
    @mock.patch.object(settings, 'UGLIFY_BIN', None)
    def test_minify_with_yui(self):
        self.render()  # no errors

    @mock.patch.object(settings, 'MINIFY_MOZMARKET', False)
    def test_receiptverifier(self):
        resp = self.render()
        self.assertContains(resp, 'exports.receipts.Verifier')

    @mock.patch.object(settings, 'MOZMARKET_VENDOR_EXCLUDE',
                       ['receiptverifier'])
    @mock.patch.object(settings, 'MINIFY_MOZMARKET', False)
    def test_exclude(self):
        resp = self.render()
        self.assertNotContains(resp, 'exports.receipts.Verifier')


class TestRobots(amo.tests.TestCase):

    @mock.patch.object(settings, 'ENGAGE_ROBOTS', True)
    def test_engage_robots(self):
        rs = self.client.get('/robots.txt')
        self.assertContains(rs, 'Allow: /')

    @mock.patch.object(settings, 'ENGAGE_ROBOTS', False)
    def test_do_not_engage_robots(self):
        rs = self.client.get('/robots.txt')
        self.assertContains(rs, 'Disallow: /')


class TestFooter(amo.tests.TestCase):
    fixtures = ['base/users', 'webapps/337141-steamcube']

    def test_developers_links_to_dashboard(self):
        # I've already submitted an app.
        assert self.client.login(username='steamcube@mozilla.com',
                                 password='password')
        r = self.client.get(reverse('home'))
        eq_(r.status_code, 200)
        links = pq(r.content)('#site-footer a[rel=external]')
        eq_(links.length, 1)
        eq_(links.attr('href'), reverse('mkt.developers.apps'))

    def test_developers_links_to_landing(self):
        # I've ain't got no apps.
        assert self.client.login(username='regular@mozilla.com',
                                 password='password')
        r = self.client.get(reverse('home'))
        eq_(r.status_code, 200)
        links = pq(r.content)('#site-footer a[rel=external]')
        eq_(links.length, 1)
        eq_(links.attr('href'), reverse('ecosystem.landing'))

    def test_language_selector(self):
        # TODO: Remove log-in bit when we remove `request.can_view_consumer`.
        assert self.client.login(username='steamcube@mozilla.com',
                                 password='password')
        r = self.client.get(reverse('home'))
        eq_(r.status_code, 200)
        eq_(pq(r.content)('#lang-form option[selected]').attr('value'),
            'en-us')

    def test_language_selector_variables(self):
        # TODO: Remove log-in bit when we remove `request.can_view_consumer`.
        assert self.client.login(username='steamcube@mozilla.com',
                                 password='password')
        r = self.client.get(reverse('home'), {'x': 'xxx', 'y': 'yyy'})
        doc = pq(r.content)('#lang-form')
        eq_(doc('input[type=hidden][name=x]').attr('value'), 'xxx')
        eq_(doc('input[type=hidden][name=y]').attr('value'), 'yyy')


class TestCSRF(amo.tests.TestCase):
    fixtures = ['base/users']

    def test_csrf(self):
        assert json.loads(self.client.post(reverse('csrf')).content)['csrf']

    def test_not_csrf(self):
        self.client.login(username='admin@mozilla.com', password='password')
        eq_(self.client.post(reverse('csrf')).status_code, 403)
