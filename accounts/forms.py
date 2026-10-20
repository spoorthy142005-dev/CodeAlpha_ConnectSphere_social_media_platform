from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from .models import Profile, validate_avatar_file


class UserRegistrationForm(forms.ModelForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'Enter your email address', 'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Create a secure password (min 8 characters)', 'class': 'form-control'}),
        label="Password"
    )
    password_confirm = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Confirm your password', 'class': 'form-control'}),
        label="Confirm Password"
    )

    class Meta:
        model = User
        fields = ['username', 'email']
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Choose a unique username', 'class': 'form-control'}),
        }
        help_texts = {
            'username': 'Letters, digits and @/./+/-/_ only. Maximum 150 characters.',
        }

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise ValidationError("This username is already taken. Please choose another.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email__iexact=email).exists():
            raise ValidationError("An account with this email address already exists.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password')
        p2 = cleaned_data.get('password_confirm')

        if p1 and p2:
            if p1 != p2:
                self.add_error('password_confirm', "Passwords do not match.")
            else:
                try:
                    validate_password(p1)
                except ValidationError as e:
                    self.add_error('password', e)
        return cleaned_data


class ProfileEditForm(forms.ModelForm):
    default_feed_mode = forms.ChoiceField(
        choices=[('following', 'Following'), ('discover', 'Discover')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = Profile
        fields = ['display_name', 'bio', 'avatar', 'is_private', 'low_bandwidth', 'default_feed_mode']
        widgets = {
            'display_name': forms.TextInput(attrs={'placeholder': 'Your display name', 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'placeholder': 'Tell the community about yourself...', 'rows': 4, 'class': 'form-control'}),
            'avatar': forms.FileInput(attrs={'class': 'form-control-file', 'accept': 'image/*'}),
            'is_private': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'low_bandwidth': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        labels = {
            'display_name': 'Display Name',
            'bio': 'Bio',
            'avatar': 'Profile Avatar',
            'is_private': 'Private Account (Only followers can view your posts)',
            'low_bandwidth': 'Low-Bandwidth Mode (Disable animations and heavy visual effects)',
            'default_feed_mode': 'Default Feed View (Preferred landing stream)',
        }

    def clean_default_feed_mode(self):
        val = self.cleaned_data.get('default_feed_mode')
        if not val or val not in ['following', 'discover']:
            return self.instance.default_feed_mode or 'following'
        return val


class PrivacySettingsForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = [
            'is_private',
            'default_post_audience',
            'default_feed_mode',
            'low_bandwidth',
            'notify_follows',
            'notify_likes',
            'notify_comments',
            'notify_communities',
            'notifications_paused',
            'quiet_hours_enabled',
            'quiet_hours_start',
            'quiet_hours_end',
        ]
        widgets = {
            'is_private': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'default_post_audience': forms.Select(attrs={'class': 'form-control'}),
            'default_feed_mode': forms.Select(attrs={'class': 'form-control'}),
            'low_bandwidth': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_follows': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_likes': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_comments': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notify_communities': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'notifications_paused': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'quiet_hours_enabled': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'quiet_hours_start': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'quiet_hours_end': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
        }


class AccountDeleteForm(forms.Form):
    confirmation_username = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={'placeholder': 'Type your username to confirm', 'class': 'form-control'}),
        label="Confirm Your Username"
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'placeholder': 'Enter your password', 'class': 'form-control'}),
        required=True,
        label="Password"
    )

    confirm_permanent_loss = forms.BooleanField(
        required=True,
        label="I understand that account deletion is permanent and cannot be undone.",
        widget=forms.CheckboxInput(attrs={'class': 'form-checkbox'})
    )

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_confirmation_username(self):
        entered = self.cleaned_data.get('confirmation_username')
        if not self.user or entered != self.user.username:
            raise ValidationError("The username entered does not match your account username.")
        return entered

    def clean_password(self):
        pwd = self.cleaned_data.get('password')
        if not self.user or not self.user.check_password(pwd):
            raise ValidationError("Incorrect password. Please verify and try again.")
        return pwd



