from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import authenticate
from account.models import Account


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(
        max_length=255, help_text='Required. Add a valid email address.')

    class Meta:
        model = Account
        fields = ('email', 'username', 'password1', 'password2')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()

        try:
            account = Account.objects.exclude(
                pk=self.instance.pk).get(email=email)
        except Account.DoesNotExist:
            return email
        raise forms.ValidationError(
            'Email "%s" is already in use.' % account)

    def clean_username(self):
        username = self.cleaned_data['username']

        try:
            account = Account.objects.exclude(
                pk=self.instance.pk).get(username=username)
        except Account.DoesNotExist:
            return username
        raise forms.ValidationError(
            'username "%s" is already in use.' % username)


class AccountAuthenticationForm(forms.ModelForm):

    password = forms.CharField(label='Password', widget=forms.PasswordInput)

    class Meta:
        model = Account
        fields = ('email', 'password')

    def clean(self):
        if self.is_valid():
            email = self.cleaned_data['email']
            password = self.cleaned_data['password']
            user = authenticate(email=email, password=password)
            if not user:
                raise forms.ValidationError("Invalid login")
            if not user.is_active:
                raise forms.ValidationError('Not Activated')


class AccountUpdateForm(forms.ModelForm):

    class Meta:
        model = Account
        fields = ('username', 'email', 'profile_image', 'hide_email')

    def clean_email(self):
        email = self.cleaned_data['email'].lower()

        try:
            account = Account.objects.exclude(
                pk=self.instance.pk).get(email=email)
        except Account.DoesNotExist:
            return email
        raise forms.ValidationError(
            f'Email {email} is already in use.')

    def clean_username(self):
        username = self.cleaned_data['username']

        try:
            account = Account.objects.exclude(
                pk=self.instance.pk).get(username=username)
        except Account.DoesNotExist:
            return username
        raise forms.ValidationError(
            f'username {username} is already in use.')

    def save(self, commit=True):
        account = super(AccountUpdateForm, self).save(commit=True)
        account.username = self.cleaned_data['username']
        account.email = self.cleaned_data['email']
        account.profile_image = self.cleaned_data['profile_image']
        account.hide_email = self.cleaned_data['hide_email']

        if commit:
            account.save()
        return account
