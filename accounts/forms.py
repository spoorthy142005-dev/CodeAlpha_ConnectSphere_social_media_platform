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
    class Meta:
        model = Profile
        fields = ['display_name', 'bio', 'avatar', 'is_private', 'low_bandwidth']
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
        }
