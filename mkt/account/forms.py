import re

from django import forms

import commonware.log
import happyforms
from tower import ugettext_lazy as _lazy

import amo
from market.models import PriceCurrency
from users.forms import BaseAdminUserEditForm, UserRegisterForm
from users.models import UserProfile

log = commonware.log.getLogger('z.users')
admin_re = re.compile('(?=.*\d)(?=.*[a-zA-Z])')


class UserEditForm(UserRegisterForm):
    display_name = forms.CharField(label=_lazy(u'Display Name'), max_length=50,
        required=False,
        help_text=_lazy(u'This will be publicly displayed next to your '
                         'ratings, collections, and other contributions.'))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UserEditForm, self).__init__(*args, **kwargs)

        # TODO: We should inherit from a base form not UserRegisterForm.
        if self.fields.get('recaptcha'):
            del self.fields['recaptcha']

    class Meta:
        model = UserProfile
        fields = ('email', 'display_name')

    def save(self):
        u = super(UserEditForm, self).save(commit=False)

        log.debug(u'User (%s) updated their profile' % u)

        u.save()
        return u


class AdminUserEditForm(BaseAdminUserEditForm, UserEditForm):
    """
    This extends from the old `AdminUserEditForm` but using our new fancy
    `UserEditForm`.
    """
    admin_log = forms.CharField(required=True, label='Reason for change',
                                widget=forms.Textarea(attrs={'rows': 4}))
    notes = forms.CharField(required=False, label='Notes',
                            widget=forms.Textarea(attrs={'rows': 4}))
    anonymize = forms.BooleanField(required=False)
    restricted = forms.BooleanField(required=False)

    def save(self, *args, **kw):
        profile = super(AdminUserEditForm, self).save()
        if self.cleaned_data['anonymize']:
            amo.log(amo.LOG.ADMIN_USER_ANONYMIZED, self.instance,
                    self.cleaned_data['admin_log'])
            profile.anonymize()  # This also logs.
        else:
            if ('restricted' in self.changed_data and
                self.cleaned_data['restricted']):
                amo.log(amo.LOG.ADMIN_USER_RESTRICTED, self.instance,
                        self.cleaned_data['admin_log'])
                profile.restrict()
            else:
                amo.log(amo.LOG.ADMIN_USER_EDITED, self.instance,
                        self.cleaned_data['admin_log'], details=self.changes())
                log.info('Admin edit user: %s changed fields: %s' %
                         (self.instance, self.changed_fields()))
        return profile


class UserDeleteForm(forms.Form):
    confirm = forms.BooleanField(
        label=_lazy(u'I understand this step cannot be undone.'))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UserDeleteForm, self).__init__(*args, **kwargs)

    def clean(self):
        amouser = self.request.user.get_profile()
        if amouser.is_developer:
            # This is tampering because the form isn't shown on the page if
            # the user is a developer.
            log.warning(u'[Tampering] Attempt to delete developer account (%s)'
                                                          % self.request.user)
            raise forms.ValidationError('Developers cannot delete their '
                                        'accounts.')


class CurrencyForm(happyforms.Form):
    currency = forms.ChoiceField(widget=forms.RadioSelect)

    def __init__(self, *args, **kw):
        super(CurrencyForm, self).__init__(*args, **kw)
        choices = [u'USD'] + list((PriceCurrency.objects
                                        .values_list('currency', flat=True)
                                        .distinct()))
        self.fields['currency'].choices = [(k, amo.PAYPAL_CURRENCIES[k])
                                              for k in choices if k]
